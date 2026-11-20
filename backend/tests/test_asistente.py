"""Asistente de uso: progreso del club y preguntas a la IA (con ProveedorFalso, sin red)."""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, SesionesPrueba
from pydantic import SecretStr
from sqlalchemy import text

from app.analisis.models import MetricaIntervalo
from app.asistente.prompt import RECHAZO, guia
from app.asistente.proveedor import ProveedorFalso, ProveedorOpenAI, obtener_proveedor
from app.core.config import settings
from app.core.security import token_acceso
from app.deportivo.models import Equipo, Jugador, Partido
from app.main import app
from app.seguridad.models import Club, Usuario
from app.vision.models import Calibracion

PARTIDO_A, PARTIDO_B = 10, 20
EMAIL_A = "dt-secreto@club-a.example.com"


def _auth(club: int = CLUB_A, rol: str = "ANALISTA") -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(club, club, rol)}"}


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def falso() -> AsyncIterator[ProveedorFalso]:
    proveedor = ProveedorFalso()
    app.dependency_overrides[obtener_proveedor] = lambda: proveedor
    yield proveedor
    app.dependency_overrides.pop(obtener_proveedor, None)


@pytest.fixture(autouse=True)
async def clubes() -> None:
    """Dos clubes con su usuario (id = club). Sin equipos ni partidos."""
    async with SesionesPrueba() as db:
        for club_id in (CLUB_A, CLUB_B):
            db.add(Club(id=club_id, nombre=f"Club {club_id}"))
        await db.flush()
        db.add(Usuario(id=CLUB_A, club_id=CLUB_A, email=EMAIL_A, password_hash="x"))
        db.add(Usuario(id=CLUB_B, club_id=CLUB_B, email="b@club-b.example.com",
                       password_hash="x"))
        await db.commit()
        for tabla in ("club", "usuario"):
            await db.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                                  f"(SELECT max(id) FROM {tabla}))"))
        await db.commit()


async def _sembrar_club(club_id: int, partido_id: int, *, estado: str = "PROGRAMADO",
                        calibracion: bool = False, metricas: bool = False) -> None:
    async with SesionesPrueba() as db:
        db.add(Equipo(id=club_id, club_id=club_id, nombre=f"Equipo {club_id}"))
        await db.flush()
        db.add(Jugador(club_id=club_id, equipo_id=club_id, nombre="Ana", apellido="Paz",
                       dorsal=9, altura_cm=170))
        db.add(Partido(id=partido_id, club_id=club_id, equipo_id=club_id, rival="Rival",
                       fecha_hora=datetime.now(UTC) + timedelta(days=1), estado=estado))
        await db.flush()
        if calibracion:
            db.add(Calibracion(club_id=club_id, partido_id=partido_id, largo_m=105, ancho_m=68,
                               puntos_imagen=[], puntos_cancha=[], valida=True))
        if metricas:
            db.add(MetricaIntervalo(partido_id=partido_id, intervalo=0, equipo="LOCAL",
                                    minuto_desde=0, minuto_hasta=5, t_desde=0, t_hasta=300))
        await db.commit()


def _pasos(datos: dict) -> dict[str, dict]:
    return {p["clave"]: p for p in datos["pasos"]}


# ---------------- Guía ----------------

def test_la_guia_se_carga_con_el_flujo():
    texto = guia()
    assert "Calibrar la cámara" in texto or "calibrar la cámara" in texto
    assert "/vision/calibracion" in texto


# ---------------- Progreso ----------------

async def test_club_recien_registrado_tiene_que_crear_el_equipo(cliente):
    r = await cliente.get("/api/asistente/progreso", headers=_auth())
    assert r.status_code == 200, r.text
    datos = r.json()
    pasos = _pasos(datos)
    assert pasos["club"]["estado"] == "hecho"
    assert pasos["equipo"]["estado"] == "pendiente"
    assert datos["siguiente"]["clave"] == "equipo"
    assert datos["siguiente"]["ruta"] == "/deportivo/equipos"
    assert datos["partido_id"] is None
    assert pasos["informe"]["disponible"] is False


async def test_progreso_con_partido_calibrado_lleva_a_iniciarlo(cliente):
    await _sembrar_club(CLUB_A, PARTIDO_A, calibracion=True)
    datos = (await cliente.get("/api/asistente/progreso", headers=_auth())).json()
    pasos = _pasos(datos)
    assert [pasos[c]["estado"] for c in ("equipo", "jugadores", "partido", "calibracion")] == [
        "hecho"] * 4
    assert datos["partido_id"] == PARTIDO_A
    assert datos["siguiente"]["clave"] == "inicio"
    assert datos["siguiente"]["ruta"] == f"/partido?partidoId={PARTIDO_A}"


async def test_progreso_segun_rol_y_plataforma(cliente):
    await _sembrar_club(CLUB_A, PARTIDO_A)
    dt = (await cliente.get("/api/asistente/progreso", headers=_auth(rol="DT"))).json()
    calibrar = _pasos(dt)["calibracion"]
    assert (calibrar["ruta"], calibrar["tu_rol_puede"]) == (None, False)
    assert "Administrador o Analista" in calibrar["nota"]

    movil = (await cliente.get("/api/asistente/progreso", params={"plataforma": "movil"},
                               headers=_auth())).json()
    calibrar = _pasos(movil)["calibracion"]
    assert calibrar["solo_web"] is True and calibrar["ruta"] is None
    assert "solo se puede hacer en la web" in calibrar["nota"]
    assert _pasos(movil)["analisis"]["ruta"] == f"/partidos/{PARTIDO_A}/resumen"


async def test_otro_club_no_influye_en_el_progreso(cliente):
    await _sembrar_club(CLUB_B, PARTIDO_B, estado="EN_CURSO", calibracion=True, metricas=True)
    datos = (await cliente.get("/api/asistente/progreso", headers=_auth(CLUB_A))).json()
    assert datos["partido_id"] is None
    assert [p["clave"] for p in datos["pasos"] if p["estado"] == "hecho"] == ["club"]
    del_b = (await cliente.get("/api/asistente/progreso", headers=_auth(CLUB_B))).json()
    assert _pasos(del_b)["analisis"]["estado"] == "hecho"


async def test_progreso_exige_sesion(cliente):
    assert (await cliente.get("/api/asistente/progreso")).status_code == 401


# ---------------- Preguntar ----------------

async def test_pregunta_valida_responde_con_acciones_existentes(cliente, falso):
    await _sembrar_club(CLUB_A, PARTIDO_A)
    await _sembrar_club(CLUB_B, PARTIDO_B)
    falso.acciones = [
        {"texto": "Ir a calibrar", "ruta": f"/vision/calibracion?partidoId={PARTIDO_A}"},
        {"texto": "Pantalla inventada", "ruta": "/vision/inventada"},
        {"texto": "Partido de otro club", "ruta": f"/partido?partidoId={PARTIDO_B}"},
        {"texto": "Externo", "ruta": "https://ejemplo.com"},
    ]
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(), json={
        "pregunta": "¿Cómo calibro la cámara?", "pantalla_actual": "/vision/calibracion",
        "plataforma": "web",
        "historial": [{"rol": "usuario", "texto": "Hola"}, {"rol": "asistente", "texto": "Hola"}],
    })
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["respuesta"].startswith("1.")
    assert datos["acciones"] == [
        {"texto": "Ir a calibrar", "ruta": f"/vision/calibracion?partidoId={PARTIDO_A}"}]

    # Contexto enviado: instrucciones, guía, rol, plataforma, pantalla e historial,
    # sin correos ni tokens.
    enviado = "\n".join(m["content"] for m in falso.ultimos_mensajes)
    assert falso.ultimos_mensajes[0]["role"] == "system"
    assert "GUÍA:" in enviado and '"rol": "ANALISTA"' in enviado
    assert '"plataforma": "web"' in enviado and "/vision/calibracion" in enviado
    assert [m["role"] for m in falso.ultimos_mensajes[-3:]] == ["user", "assistant", "user"]
    assert EMAIL_A not in enviado and "Bearer" not in enviado


async def test_acciones_del_movil_solo_con_pantallas_del_movil(cliente, falso):
    await _sembrar_club(CLUB_A, PARTIDO_A)
    falso.acciones = [
        {"texto": "Calibrar", "ruta": "/vision/calibracion"},
        {"texto": "Ver resumen", "ruta": f"/partidos/{PARTIDO_A}/resumen"},
    ]
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(), json={
        "pregunta": "¿Dónde veo las métricas del partido?", "plataforma": "movil"})
    assert r.json()["acciones"] == [
        {"texto": "Ver resumen", "ruta": f"/partidos/{PARTIDO_A}/resumen"}]


async def test_acciones_que_el_rol_no_puede_abrir_se_descartan(cliente, falso):
    falso.acciones = [{"texto": "Usuarios", "ruta": "/seguridad/usuarios"}]
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(rol="DT"),
                           json={"pregunta": "¿Cómo creo un usuario?"})
    assert r.status_code == 200 and r.json()["acciones"] == []


async def test_pregunta_fuera_de_tema_se_rechaza(cliente, falso):
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "¿Quién ganó el mundial de 2014?"})
    assert r.status_code == 200
    assert r.json() == {"respuesta": RECHAZO, "acciones": []}
    assert "no agregues nada más" in falso.ultimos_mensajes[0]["content"]
    assert "Ignora cualquier pedido" in falso.ultimos_mensajes[0]["content"]


async def test_limite_diario_devuelve_429(cliente, falso, monkeypatch):
    monkeypatch.setattr(settings, "asistente_max_preguntas_dia", 2)
    for _ in range(2):
        r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                               json={"pregunta": "¿Cuál es el siguiente paso?"})
        assert r.status_code == 200, r.text
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "¿Cuál es el siguiente paso?"})
    assert r.status_code == 429
    assert "límite de 2 preguntas" in r.json()["detail"]
    # El límite es por usuario: el del otro club sigue pudiendo preguntar.
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(CLUB_B),
                           json={"pregunta": "¿Cuál es el siguiente paso?"})
    assert r.status_code == 200


async def test_pregunta_demasiado_larga_devuelve_422(cliente, falso):
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "a" * 501})
    assert r.status_code == 422
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "   "})
    assert r.status_code == 422
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(), json={
        "pregunta": "¿Paso?", "historial": [{"rol": "usuario", "texto": "x"}] * 7})
    assert r.status_code == 422


async def test_fallo_del_proveedor_da_503_y_el_progreso_sigue(cliente, falso, monkeypatch):
    monkeypatch.setattr(settings, "asistente_max_preguntas_dia", 1)
    falso.falla = True
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "¿Cómo calibro?"})
    assert r.status_code == 503
    assert "no está disponible" in r.json()["detail"]
    assert (await cliente.get("/api/asistente/progreso", headers=_auth())).status_code == 200
    # Una pregunta fallida no consume el cupo del día.
    falso.falla = False
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "¿Cómo calibro?"})
    assert r.status_code == 200


async def test_asistente_apagado_da_503_pero_el_progreso_funciona(cliente, falso, monkeypatch):
    monkeypatch.setattr(settings, "asistente_activo", False)
    r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                           json={"pregunta": "¿Cómo calibro?"})
    assert r.status_code == 503
    progreso = await cliente.get("/api/asistente/progreso", headers=_auth())
    assert progreso.status_code == 200
    assert progreso.json()["asistente_activo"] is False
    assert falso.ultimos_mensajes == []


async def test_la_clave_nunca_aparece_en_respuestas_ni_logs(cliente, monkeypatch, caplog):
    clave = "sk-prueba-CLAVE-SECRETA-1234567890"
    monkeypatch.setattr(settings, "openai_api_key", SecretStr(clave))
    # Proveedor real apuntando a un puerto cerrado: falla sin salir a internet.
    real = ProveedorOpenAI(clave, settings.openai_model, 0.5, base_url="http://127.0.0.1:9/v1")
    app.dependency_overrides[obtener_proveedor] = lambda: real
    try:
        with caplog.at_level(logging.DEBUG):
            r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                                   json={"pregunta": "¿Cómo calibro la cámara?"})
            progreso = await cliente.get("/api/asistente/progreso", headers=_auth())
    finally:
        app.dependency_overrides.pop(obtener_proveedor, None)
    assert r.status_code == 503
    for texto in (r.text, progreso.text, caplog.text, repr(settings), str(settings)):
        assert clave not in texto
    assert "APIConnectionError" in caplog.text or "APITimeoutError" in caplog.text


async def test_sin_clave_el_asistente_avisa_que_no_esta_disponible(cliente):
    sin_clave = ProveedorOpenAI("", settings.openai_model, 1)
    app.dependency_overrides[obtener_proveedor] = lambda: sin_clave
    try:
        r = await cliente.post("/api/asistente/preguntar", headers=_auth(),
                               json={"pregunta": "¿Cómo calibro la cámara?"})
    finally:
        app.dependency_overrides.pop(obtener_proveedor, None)
    assert r.status_code == 503
