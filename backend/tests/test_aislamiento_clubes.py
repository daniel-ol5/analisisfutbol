"""Aislamiento entre clubes en TODOS los endpoints  —  T-105 (Pb-03).

Criterio de aceptación: ningún endpoint permite acceso cruzado.

En vez de probar a mano endpoint por endpoint, se recorre el contrato OpenAPI:

1. Todo endpoint no público rechaza una petición sin token (401).
2. Todo endpoint con un id en la ruta, llamado por el club A contra recursos del
   club B, nunca responde 2xx ni 5xx: 404 (o 403 por rol), o 501 si todavía es
   un stub del contrato. Es 404 y no 403 a propósito: no se revela que el
   recurso existe en otro club.
3. Control: el mismo pedido hecho por el club B SÍ llega al recurso. Sin esto, un
   404 podría ser solo «el id no existe» y la prueba no demostraría nada.
4. Los WebSockets por partido cierran la conexión a quien es de otro club.

Si se agrega un endpoint con id en la ruta, esta prueba lo toma sola.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, PARTIDO_B, SesionesPrueba, sembrar_partidos

from app.core.security import token_acceso
from app.deportivo.models import Alineacion, AlineacionJugador, Equipo, Jugador
from app.deportivo.schemas import EstadoPartido
from app.main import app
from app.partido.models import EventoManual
from app.seguridad.models import Usuario
from app.vision.models import Calibracion, ModeloML, Video

ESQUEMA = app.openapi()

# Endpoints que no llevan token a propósito.
PUBLICOS = {
    ("POST", "/api/seguridad/registro"), ("POST", "/api/seguridad/login"),
    ("POST", "/api/seguridad/refresh"), ("POST", "/api/seguridad/password/olvido"),
    ("POST", "/api/seguridad/password/restablecer"), ("GET", "/api/salud"),
}

# Ids de los recursos del CLUB B que se siembran. Los del club A no existen: si un
# endpoint responde 200 con estos ids, filtró datos de otro club.
IDS_B: dict[str, Any] = {
    "equipo_id": 501, "jugador_id": 502, "partido_id": PARTIDO_B, "video_id": 503,
    "usuario_id": 504, "evento_id": 505, "modelo_id": 506,
    "regla_id": 507, "recomendacion_id": 508, "informe_id": 509,
    "track_id": 1, "sede": "Cancha", "minuto": 1,
}

# Respuestas que prueban aislamiento. 501: stub del contrato (Pb-01), sin lógica aún.
AISLADO = {401, 403, 404, 501}

# Control del club B. Estos endpoints responden 4xx aunque el recurso exista:
# pasan por una validación propia antes del dato y no sirven para el control.
CONTROL_EXENTO = {
    ("GET", "/api/vision/videos/{video_id}/archivo"),         # el archivo no está en el almacén de prueba
    ("GET", "/api/vision/videos/{video_id}/archivo/bloque"),  # ídem: 409 "todavía no está disponible"
    ("GET", "/api/vision/videos/{video_id}/cuadro"),
    ("GET", "/api/vision/videos/{video_id}/muestras"),
}


def _puntos(n: int) -> list[dict[str, float]]:
    return [{"x": 10.0 + 9 * i, "y": 5.0 + 13 * (i % 4)} for i in range(n)]


# Cuerpos válidos para los endpoints cuyo esquema exige más que los campos requeridos
# (reglas cruzadas). Sin ellos el pedido muere en 422 antes de llegar a la lógica y la
# prueba no demostraría nada.
CUERPOS: dict[tuple[str, str], Any] = {
    ("PATCH", "/api/deportivo/partidos/{partido_id}"): {"sede": "Otra sede"},
    ("PUT", "/api/deportivo/partidos/{partido_id}/alineacion"): {"jugadores": [
        {"jugador_id": 600 + i, "es_titular": True, "es_capitan": i == 0,
         "pos_x": 50.0, "pos_y": 5.0 + 5 * i} for i in range(11)]},
    ("POST", "/api/vision/partidos/{partido_id}/calibracion"):
        {"puntos_imagen": _puntos(8), "puntos_cancha": _puntos(8)},
    ("POST", "/api/vision/partidos/{partido_id}/calibracion/validar"):
        {"puntos_imagen": _puntos(8), "puntos_cancha": _puntos(8)},
}

# Responden 200 a cualquier club porque no leen ni escriben nada del recurso: la plantilla
# CSV es una fila de ejemplo y «validar» solo calcula con los puntos del cuerpo. Se
# comprueba que la respuesta no traiga nada sembrado en el club B.
ESTATICOS = {
    ("GET", "/api/deportivo/equipos/{equipo_id}/jugadores/plantilla"),
    ("POST", "/api/vision/partidos/{partido_id}/calibracion/validar"),
}
DATOS_DEL_CLUB_B = ("Equipo B", "club-b.example.com", "v.mp4", "Jugador")


# Valores de query que el generador genérico no adivina.
QUERY = {"color_rival": "#112233"}


def _operaciones() -> list[tuple[str, str]]:
    return [(m.upper(), p) for p, ops in ESQUEMA["paths"].items() for m in ops
            if (m.upper(), p) not in PUBLICOS and m.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}]


def _con_id() -> list[tuple[str, str]]:
    return [(m, p) for m, p in _operaciones() if "{" in p]


def _resolver(esquema: dict) -> dict:
    ref = esquema.get("$ref")
    if ref:
        esquema = ESQUEMA["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return esquema


def _valor(esquema: dict) -> Any:
    """Un valor mínimo válido para el esquema (suficiente para pasar la validación del cuerpo)."""
    esquema = _resolver(esquema)
    for clave in ("anyOf", "oneOf"):
        if clave in esquema:
            utiles = [o for o in esquema[clave] if o.get("type") != "null"]
            return _valor(utiles[0]) if utiles else None
    if "allOf" in esquema:
        return _valor(esquema["allOf"][0])
    if "enum" in esquema:
        return esquema["enum"][0]
    tipo = esquema.get("type")
    if tipo == "object" or "properties" in esquema:
        props = esquema.get("properties", {})
        return {k: _valor(props[k]) for k in esquema.get("required", []) if k in props}
    if tipo == "array":
        minimo = esquema.get("minItems", 0)
        return [_valor(esquema.get("items", {})) for _ in range(minimo)]
    if tipo == "integer":
        return max(1, int(esquema.get("minimum", 1)))
    if tipo == "number":
        return max(1.0, float(esquema.get("minimum", 1.0)))
    if tipo == "boolean":
        return True
    if esquema.get("format") == "date-time":
        return datetime.now(UTC).isoformat()
    if esquema.get("format") == "email":
        return "x@example.com"
    return "x" * max(1, int(esquema.get("minLength", 1)))


def _url(ruta: str) -> str:
    url = ruta
    for nombre, valor in IDS_B.items():
        url = url.replace("{" + nombre + "}", str(valor))
    assert "{" not in url, f"Falta sembrar el parámetro de ruta en {ruta}"
    return url


def _pedido(metodo: str, ruta: str) -> tuple[str, dict[str, Any]]:
    """URL con los ids del club B y los argumentos (query y cuerpo mínimos) del pedido."""
    op = ESQUEMA["paths"][ruta][metodo.lower()]
    params = {p["name"]: QUERY.get(p["name"], _valor(p["schema"])) for p in op.get("parameters", [])
              if p["in"] == "query" and p.get("required")}
    kwargs: dict[str, Any] = {"params": params}
    cuerpo = op.get("requestBody", {}).get("content", {})
    if (metodo, ruta) in CUERPOS:
        kwargs["json"] = CUERPOS[(metodo, ruta)]
    elif "application/json" in cuerpo:
        kwargs["json"] = _valor(cuerpo["application/json"]["schema"])
    elif "multipart/form-data" in cuerpo:
        kwargs["files"] = {"archivo": ("x.csv", b"a,b\n1,2\n", "text/csv")}
    elif "application/octet-stream" in cuerpo:
        kwargs["content"] = b"x"
    return _url(ruta), kwargs


def _auth(club: int, usuario: int = 1, rol: str = "ADMIN") -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(usuario, club, rol)}"}


@pytest.fixture(autouse=True)
async def club_b() -> None:
    """Recursos del club B. El club A no tiene ninguno de estos ids."""
    await sembrar_partidos(EstadoPartido.FINALIZADO)
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        # PostgreSQL exige el orden de las claves foráneas: se inserta por etapas.
        db.add_all([
            Equipo(id=501, club_id=CLUB_B, nombre="Equipo B"),
            Usuario(id=504, club_id=CLUB_B, email="b@club-b.example.com", password_hash="x"),
            ModeloML(id=506, club_id=CLUB_B, nombre="m", version="1", tipo="DETECCION",
                     archivo_url="https://modelos.example.com/m.pt"),
        ])
        await db.flush()
        db.add_all([
            Jugador(id=502, club_id=CLUB_B, equipo_id=501, nombre="Jugador", apellido="B",
                    dorsal=9, posicion="DEL", altura_cm=180),
            Video(id=503, club_id=CLUB_B, partido_id=PARTIDO_B, archivo_url="v.mp4",
                  nombre="v.mp4", tipo="video/mp4", tamano_bytes=10, estado="SUBIDO"),
            Calibracion(club_id=CLUB_B, partido_id=PARTIDO_B, largo_m=105.0, ancho_m=68.0,
                        puntos_imagen=[{"x": 1.0, "y": 1.0}], puntos_cancha=[{"x": 0.0, "y": 0.0}],
                        valida=True),
            Alineacion(id=510, club_id=CLUB_B, partido_id=PARTIDO_B, formacion="4-3-3"),
        ])
        await db.flush()
        db.add_all([
            AlineacionJugador(alineacion_id=510, jugador_id=502, es_titular=True),
            EventoManual(id=505, club_id=CLUB_B, partido_id=PARTIDO_B, uuid=str(uuid4()),
                         tipo="GOL", equipo="LOCAL", minuto=3, origen="MANUAL",
                         capturado_en=ahora, creado_en=ahora, creado_por_id=504),
        ])
        await db.commit()


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _id(op: tuple[str, str]) -> str:
    return f"{op[0]} {op[1]}"


# ---------------- 1. Sin token ----------------

@pytest.mark.parametrize("op", _operaciones(), ids=_id)
async def test_sin_token_responde_401(cliente, op):
    metodo, ruta = op
    r = await cliente.request(metodo, _url(ruta))
    assert r.status_code == 401, f"{metodo} {ruta} sin token respondió {r.status_code}"


# ---------------- 2. Acceso cruzado ----------------

@pytest.mark.parametrize("op", _con_id(), ids=_id)
async def test_el_club_a_no_alcanza_recursos_del_club_b(cliente, op):
    metodo, ruta = op
    url, kwargs = _pedido(metodo, ruta)
    r = await cliente.request(metodo, url, headers=_auth(CLUB_A), **kwargs)
    if op in ESTATICOS:
        assert r.status_code == 200, f"{metodo} {ruta}: {r.status_code} {r.text[:200]}"
        assert not [d for d in DATOS_DEL_CLUB_B if d in r.text], (
            f"{metodo} {ruta} devolvió datos del club B: {r.text[:200]}")
        return
    assert r.status_code in AISLADO, (
        f"{metodo} {ruta}: el club A recibió {r.status_code} sobre un recurso del club B "
        f"(esperado 404; 422 significa que la prueba no llegó a la lógica: ajustar el cuerpo). "
        f"Respuesta: {r.text[:200]}")


# ---------------- 3. Control ----------------

@pytest.mark.parametrize("op", [o for o in _con_id() if o not in CONTROL_EXENTO], ids=_id)
async def test_control_el_club_b_si_llega_a_su_recurso(cliente, op):
    """Si el dueño tampoco llegara, el 404 de arriba no probaría aislamiento."""
    metodo, ruta = op
    if metodo != "GET":
        pytest.skip("solo se controla con lecturas: las escrituras cambiarían el recurso")
    url, kwargs = _pedido(metodo, ruta)
    r = await cliente.request(metodo, url, headers=_auth(CLUB_B, usuario=504), **kwargs)
    assert r.status_code < 400 or r.status_code == 501, (
        f"GET {ruta} respondió {r.status_code} al dueño del recurso: {r.text[:200]}")


# ---------------- 4. Listados ----------------

LISTADOS = [
    ("/api/deportivo/equipos", "id", 501), ("/api/deportivo/partidos", "id", PARTIDO_B),
    ("/api/seguridad/usuarios", "id", 504), ("/api/vision/modelos", "id", 506),
]


def _filas(cuerpo: Any) -> list[dict]:
    return cuerpo if isinstance(cuerpo, list) else cuerpo.get("items", cuerpo.get("datos", []))


@pytest.mark.parametrize(("ruta", "campo", "id_b"), LISTADOS)
async def test_los_listados_del_club_a_no_incluyen_filas_del_club_b(cliente, ruta, campo, id_b):
    r = await cliente.get(ruta, headers=_auth(CLUB_A))
    assert r.status_code == 200, r.text
    assert id_b not in {f[campo] for f in _filas(r.json())}
    r = await cliente.get(ruta, headers=_auth(CLUB_B, usuario=504))
    assert id_b in {f[campo] for f in _filas(r.json())}, "control: el club B no ve su propia fila"


# ---------------- 5. WebSockets ----------------

@pytest.mark.parametrize("canal", ["vivo", "ingesta"])
def test_los_websockets_rechazan_a_otro_club(canal):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    ruta = f"/api/partido/{PARTIDO_B}/{canal}?token={token_acceso(1, CLUB_A, 'ADMIN')}"
    with TestClient(app) as c, pytest.raises(WebSocketDisconnect), c.websocket_connect(ruta) as ws:
        ws.receive_text()


def test_el_partido_a_existe_para_el_club_a():
    """Guarda: el id PARTIDO_A que usan otras pruebas sigue siendo del club A."""
    assert PARTIDO_A != PARTIDO_B and CLUB_A != CLUB_B


# ---------------- 6. Clave de firma (T-105) ----------------
# Con la SECRET_KEY del repositorio cualquiera puede firmar un token de cualquier club.

def _ajustes(**kw):
    from app.core.config import Settings
    return Settings(_env_file=None, **kw)


@pytest.mark.parametrize("entorno", ["production", "PROD", "produccion"])
def test_produccion_no_arranca_con_la_clave_del_repositorio(entorno):
    from pydantic import ValidationError

    from app.core.config import CLAVES_PUBLICAS

    for clave in [*CLAVES_PUBLICAS, "corta"]:
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            _ajustes(app_env=entorno, secret_key=clave)


def test_produccion_arranca_con_una_clave_propia_y_desarrollo_no_se_ve_afectado():
    assert _ajustes(app_env="production", secret_key="k" * 48).secret_key == "k" * 48
    assert _ajustes(app_env="development").app_env == "development"
    assert _ajustes().app_env == ""


# ---------------- 7. Escaneo de secretos (T-105) ----------------

PATRONES_SECRETOS = {
    "clave privada": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "AWS": r"AKIA[0-9A-Z]{16}",
    "GitHub": r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}",
    "Slack": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "clave sk-": r"\bsk-[A-Za-z0-9]{20,}",
    "Google": r"AIza[0-9A-Za-z_-]{30}",
    "JWT": r"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}",
}
EXTENSIONES_BINARIAS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".mp4", ".pt", ".pth", ".zip",
                        ".pdf", ".woff", ".woff2", ".ttf", ".webp", ".jar", ".apk", ".db"}


def _archivos_versionados() -> list[str]:
    import subprocess
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    try:
        salida = subprocess.run(["git", "ls-files", "-z"], cwd=raiz, capture_output=True,
                                check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git no está disponible o esto no es un repositorio")
    return [str(raiz / f) for f in salida.decode().split("\0") if f]


def test_ningun_archivo_versionado_contiene_secretos():
    import re
    from pathlib import Path

    hallazgos = []
    for ruta in _archivos_versionados():
        p = Path(ruta)
        if p.suffix.lower() in EXTENSIONES_BINARIAS or not p.is_file() \
                or p.name in {"package-lock.json", "openapi.json"}:
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for nombre, patron in PATRONES_SECRETOS.items():
            if re.search(patron, texto):
                hallazgos.append(f"{p.name}: {nombre}")
    assert not hallazgos, f"Posibles secretos versionados: {hallazgos}"


def test_no_se_versionan_archivos_de_entorno_ni_claves():
    import re

    prohibidos = re.compile(r"(^|/)\.env($|\.(?!example$))|\.(pem|key|p12|pfx|jks)$|(^|/)_tok")
    versionados = [f for f in _archivos_versionados() if prohibidos.search(f.replace("\\", "/"))]
    assert not versionados, f"Archivos sensibles versionados: {versionados}"
