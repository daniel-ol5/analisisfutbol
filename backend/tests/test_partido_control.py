"""Pruebas de control del partido, cronómetro y dirección de ataque  —  CU-30, CU-31 (T-065)."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta

import pytest
from datos_calibracion import cuerpo_valido
from httpx import ASGITransport, AsyncClient
from modelos_falsos import SesionesPrueba
from sqlalchemy import select
from starlette.testclient import TestClient

from app.core.database import SessionLocal, get_db
from app.core.realtime import HubMemoria, obtener_hub
from app.core.security import token_acceso
from app.deportivo.models import Partido
from app.main import app
from app.partido.models import RelojPartido
from app.partido.service import (
    PartidosEnTabla,
    normalizar_coordenadas,
    obtener_reloj,
    obtener_repositorio_partidos,
)

BASE = "http://test"


class RelojFalso:
    """Reloj controlable en pruebas: permite avanzar el tiempo sin usar sleep."""

    def __init__(self, inicial: datetime | None = None) -> None:
        self.actual = inicial or datetime(2026, 11, 7, 15, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.actual

    def avanzar(self, segundos: float) -> datetime:
        self.actual = self.actual + timedelta(seconds=segundos)
        return self.actual


@pytest.fixture
def reloj() -> RelojFalso:
    r = RelojFalso()
    app.dependency_overrides[obtener_reloj] = lambda: r
    yield r
    app.dependency_overrides.pop(obtener_reloj, None)


@pytest.fixture
async def cliente(reloj):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fecha_futura(dias: int = 5) -> str:
    return (datetime.now(UTC) + timedelta(days=dias)).replace(microsecond=0).isoformat()


async def _crear_club_y_partido(cliente: AsyncClient, sufijo: str) -> dict:
    reg = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": f"Club {sufijo}",
            "email": f"admin_{sufijo}@test.com",
            "password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    sesion = reg.json()
    auth = _auth(sesion["access_token"])

    eq = await cliente.post(
        "/api/deportivo/equipos",
        headers=auth,
        json={"nombre": f"Equipo {sufijo}", "categoria": "Primera", "temporada": "2026"},
    )
    assert eq.status_code == 201, eq.text
    equipo_id = eq.json()["id"]

    part = await cliente.post(
        "/api/deportivo/partidos",
        headers=auth,
        json={
            "equipo_id": equipo_id,
            "rival": "Club Rival",
            "es_local": True,
            "fecha_hora": _fecha_futura(),
            "sede": "Estadio Principal",
        },
    )
    assert part.status_code == 201, part.text

    return {
        "sesion": sesion,
        "auth": auth,
        "club_id": sesion["usuario"]["club_id"],
        "usuario_id": sesion["usuario"]["id"],
        "equipo_id": equipo_id,
        "partido_id": part.json()["id"],
    }


async def _auth_rol(cliente: AsyncClient, ctx: dict, rol: str, sufijo: str) -> dict[str, str]:
    email = f"{rol.lower()}_{sufijo}@test.com"
    r = await cliente.post(
        "/api/seguridad/usuarios",
        headers=ctx["auth"],
        json={"email": email, "password": "password123", "rol": rol},
    )
    assert r.status_code == 201, r.text
    login = await cliente.post(
        "/api/seguridad/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


async def _calibrar_valido(cliente: AsyncClient, ctx: dict) -> None:
    r = await cliente.post(
        f"/api/vision/partidos/{ctx['partido_id']}/calibracion",
        headers=ctx["auth"],
        json=cuerpo_valido(),
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["valida"] is True


async def _calibrar_invalido(cliente: AsyncClient, ctx: dict) -> None:
    cuerpo = cuerpo_valido()
    # Desplazar fuertemente dos puntos en metros para superar el umbral de 2 m sin colinealidad
    cuerpo["puntos_cancha"][0] = {"x": 25.0, "y": 20.0}
    cuerpo["puntos_cancha"][1] = {"x": 80.0, "y": 22.0}
    r = await cliente.post(
        f"/api/vision/partidos/{ctx['partido_id']}/calibracion",
        headers=ctx["auth"],
        json=cuerpo,
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["valida"] is False


# ---------------- CU-31 · Normalización de coordenadas ----------------


def test_normalizar_coordenadas_cuatro_combinaciones():
    largo, ancho = 105.0, 68.0
    x, y = 30.0, 20.0

    # Parte 1 y DER: no cambia
    assert normalizar_coordenadas(x, y, largo, ancho, "DER", 1) == (30.0, 20.0)
    # Parte 1 e IZQ: rota 180° (largo - x, ancho - y)
    assert normalizar_coordenadas(x, y, largo, ancho, "IZQ", 1) == (75.0, 48.0)
    # Parte 2 y DER: rota 180° (en el 2do tiempo cambiaron de arco)
    assert normalizar_coordenadas(x, y, largo, ancho, "DER", 2) == (75.0, 48.0)
    # Parte 2 e IZQ: no cambia (en el 2do tiempo atacan hacia +x)
    assert normalizar_coordenadas(x, y, largo, ancho, "IZQ", 2) == (30.0, 20.0)


@pytest.mark.parametrize("ataca_hacia", ["DER", "IZQ"])
@pytest.mark.parametrize("parte", [1, 2])
def test_normalizar_coordenadas_involucion_y_cambio_de_lado(ataca_hacia, parte):
    """Aplicarla dos veces con la misma inversión o cambiar de lado devuelve el punto original."""
    largo, ancho = 100.0, 64.0
    x, y = 18.4, 41.2

    # Un jugador en la misma posición relativa a su arco en el 1er tiempo (x, y)
    # está en (largo - x, ancho - y) en coordenadas crudas de cancha en el 2do tiempo:
    # al normalizar ambos tiempos deben coincidir.
    norm_1 = normalizar_coordenadas(x, y, largo, ancho, ataca_hacia, 1)
    norm_2 = normalizar_coordenadas(largo - x, ancho - y, largo, ancho, ataca_hacia, 2)
    assert norm_1 == pytest.approx(norm_2)

    # Y aplicar la transformación del tiempo donde rota dos veces devuelve el punto original
    parte_que_rota = 1 if ataca_hacia == "IZQ" else 2
    x1, y1 = normalizar_coordenadas(x, y, largo, ancho, ataca_hacia, parte_que_rota)
    x2, y2 = normalizar_coordenadas(x1, y1, largo, ancho, ataca_hacia, parte_que_rota)
    assert (x2, y2) == pytest.approx((x, y))


def test_normalizar_coordenadas_rechaza_parte_o_direccion_invalida():
    with pytest.raises(ValueError):
        normalizar_coordenadas(10.0, 10.0, 105.0, 68.0, "DER", 0)
    with pytest.raises(ValueError):
        normalizar_coordenadas(10.0, 10.0, 105.0, 68.0, "DER", 3)
    with pytest.raises(ValueError):
        normalizar_coordenadas(10.0, 10.0, 105.0, 68.0, "NORTE", 1)


# ---------------- CU-30, CU-31 · Calibración y dirección obligatorias al iniciar ----------------


async def test_iniciar_sin_calibracion_responde_409(cliente: AsyncClient):
    ctx = await _crear_club_y_partido(cliente, "sin_cal")
    r = await cliente.post(
        f"/api/partido/{ctx['partido_id']}/iniciar",
        headers=ctx["auth"],
        json={"ataca_hacia": "DER"},
    )
    assert r.status_code == 409
    assert "no hay calibración" in r.json()["detail"].lower()


async def test_iniciar_con_calibracion_no_valida_responde_409_con_error_medio(
    cliente: AsyncClient,
):
    ctx = await _crear_club_y_partido(cliente, "cal_invalida")
    await _calibrar_invalido(cliente, ctx)

    r = await cliente.post(
        f"/api/partido/{ctx['partido_id']}/iniciar",
        headers=ctx["auth"],
        json={"ataca_hacia": "IZQ"},
    )
    assert r.status_code == 409
    detalle = r.json()["detail"].lower()
    assert "calibración no válida" in detalle
    assert "error medio" in detalle


async def test_iniciar_exige_ataca_hacia_valido(cliente: AsyncClient):
    ctx = await _crear_club_y_partido(cliente, "ataca_hacia")
    await _calibrar_valido(cliente, ctx)

    sin_campo = await cliente.post(
        f"/api/partido/{ctx['partido_id']}/iniciar",
        headers=ctx["auth"],
        json={},
    )
    assert sin_campo.status_code == 422

    valor_invalido = await cliente.post(
        f"/api/partido/{ctx['partido_id']}/iniciar",
        headers=ctx["auth"],
        json={"ataca_hacia": "CENTRO"},
    )
    assert valor_invalido.status_code == 422


# ---------------- Flujo completo y cronómetro persistido con «ahora» inyectado ----------------


async def test_flujo_completo_partido_y_cronometro_persistido(
    cliente: AsyncClient, reloj: RelojFalso
):
    ctx = await _crear_club_y_partido(cliente, "flujo")
    await _calibrar_valido(cliente, ctx)
    pid = ctx["partido_id"]

    # Estado inicial antes de arrancar: PROGRAMADO -> parte 0, 00:00, en_curso False
    e0 = await cliente.get(f"/api/partido/{pid}/estado", headers=ctx["auth"])
    assert e0.status_code == 200
    assert e0.json()["parte"] == 0
    assert e0.json()["minuto"] == 0
    assert e0.json()["segundo"] == 0
    assert e0.json()["en_curso"] is False
    assert e0.json()["calidad"]["worker_conectado"] is False

    # 1. Iniciar el partido con dirección IZQ
    r_ini = await cliente.post(
        f"/api/partido/{pid}/iniciar",
        headers=ctx["auth"],
        json={"ataca_hacia": "IZQ"},
    )
    assert r_ini.status_code == 200, r_ini.text
    assert r_ini.json()["parte"] == 1
    assert r_ini.json()["minuto"] == 0
    assert r_ini.json()["segundo"] == 0
    assert r_ini.json()["en_curso"] is True

    # Verificar que Partido.estado y Partido.ataca_hacia se persistieron en BD
    p_detalle = await cliente.get(f"/api/deportivo/partidos/{pid}", headers=ctx["auth"])
    assert p_detalle.json()["estado"] == "EN_CURSO"
    assert p_detalle.json()["ataca_hacia"] == "IZQ"
    assert p_detalle.json()["parte"] == 1

    # Avanzar el reloj 2705 s (45 min 05 s) y agregar 2 min de descuento en el 1er tiempo
    reloj.avanzar(2705)
    r_desc1 = await cliente.post(
        f"/api/partido/{pid}/descuento",
        headers=ctx["auth"],
        json={"minutos": 2},
    )
    assert r_desc1.status_code == 200
    assert r_desc1.json()["parte"] == 1
    assert r_desc1.json()["minuto"] == 45
    assert r_desc1.json()["segundo"] == 5
    assert r_desc1.json()["en_curso"] is True

    # 2. Primera llamada a /entretiempo: PAUSA el primer tiempo (parte=1, en_curso=False)
    reloj.avanzar(115)  # total 2820 s = 47 min 00 s
    r_ent1 = await cliente.post(f"/api/partido/{pid}/entretiempo", headers=ctx["auth"])
    assert r_ent1.status_code == 200
    assert r_ent1.json()["parte"] == 1
    assert r_ent1.json()["minuto"] == 47
    assert r_ent1.json()["segundo"] == 0
    assert r_ent1.json()["en_curso"] is False

    # Mientras está pausado en entretiempo, aunque pasen 15 minutos reales el cronómetro no se mueve
    reloj.avanzar(15 * 60)
    e_pausa = await cliente.get(f"/api/partido/{pid}/estado", headers=ctx["auth"])
    assert e_pausa.json()["parte"] == 1
    assert e_pausa.json()["minuto"] == 47
    assert e_pausa.json()["segundo"] == 0
    assert e_pausa.json()["en_curso"] is False

    # 3. Segunda llamada a /entretiempo: ARRANCA el segundo tiempo (parte=2, minuto 45, en_curso=True)
    r_ent2 = await cliente.post(f"/api/partido/{pid}/entretiempo", headers=ctx["auth"])
    assert r_ent2.status_code == 200
    assert r_ent2.json()["parte"] == 2
    assert r_ent2.json()["minuto"] == 45
    assert r_ent2.json()["segundo"] == 0
    assert r_ent2.json()["en_curso"] is True

    # Avanzar 45 min 30 s en el segundo tiempo y agregar 3 min de descuento
    reloj.avanzar(45 * 60 + 30)
    r_desc2 = await cliente.post(
        f"/api/partido/{pid}/descuento",
        headers=ctx["auth"],
        json={"minutos": 3},
    )
    assert r_desc2.status_code == 200
    assert r_desc2.json()["parte"] == 2
    assert r_desc2.json()["minuto"] == 90
    assert r_desc2.json()["segundo"] == 30
    assert r_desc2.json()["en_curso"] is True

    # 4. Finalizar el partido tras 2 min 30 s adicionales (minuto 93:00)
    reloj.avanzar(150)
    r_fin = await cliente.post(f"/api/partido/{pid}/finalizar", headers=ctx["auth"])
    assert r_fin.status_code == 200
    assert r_fin.json()["parte"] == 2
    assert r_fin.json()["minuto"] == 93
    assert r_fin.json()["segundo"] == 0
    assert r_fin.json()["en_curso"] is False

    # Verificar persistencia en tablas partido y reloj_partido
    async with SessionLocal() as db:
        partido_db = await db.get(Partido, pid)
        reloj_db = (
            await db.execute(select(RelojPartido).where(RelojPartido.partido_id == pid))
        ).scalar_one()
        assert partido_db.estado == "FINALIZADO"
        assert partido_db.parte == 2
        assert partido_db.minuto_actual == 93
        assert reloj_db.en_curso is False
        assert reloj_db.inicio_utc is None
        assert reloj_db.descuento_1_min == 2
        assert reloj_db.descuento_2_min == 3


# ---------------- Transiciones inválidas (409) ----------------


async def test_transiciones_invalidas_responden_409(cliente: AsyncClient):
    ctx = await _crear_club_y_partido(cliente, "invalidas")
    await _calibrar_valido(cliente, ctx)
    pid = ctx["partido_id"]
    h = ctx["auth"]

    # Sin iniciar (PROGRAMADO): no se puede entretiempo, descuento ni finalizar
    assert (await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h)).status_code == 409
    assert (
        await cliente.post(f"/api/partido/{pid}/descuento", headers=h, json={"minutos": 1})
    ).status_code == 409
    assert (await cliente.post(f"/api/partido/{pid}/finalizar", headers=h)).status_code == 409

    # Iniciar y volver a iniciar ya EN_CURSO -> 409
    assert (
        await cliente.post(f"/api/partido/{pid}/iniciar", headers=h, json={"ataca_hacia": "DER"})
    ).status_code == 200
    assert (
        await cliente.post(f"/api/partido/{pid}/iniciar", headers=h, json={"ataca_hacia": "DER"})
    ).status_code == 409

    # Pausar en entretiempo -> con el reloj pausado NO se acepta descuento (409)
    assert (await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h)).status_code == 200
    assert (
        await cliente.post(f"/api/partido/{pid}/descuento", headers=h, json={"minutos": 2})
    ).status_code == 409

    # Arrancar 2do tiempo -> una tercera llamada a /entretiempo en parte=2 es inválida (409)
    assert (await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h)).status_code == 200
    assert (await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h)).status_code == 409

    # Finalizar -> ya FINALIZADO no permite iniciar, entretiempo, descuento ni volver a finalizar
    assert (await cliente.post(f"/api/partido/{pid}/finalizar", headers=h)).status_code == 200
    assert (
        await cliente.post(f"/api/partido/{pid}/iniciar", headers=h, json={"ataca_hacia": "DER"})
    ).status_code == 409
    assert (await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h)).status_code == 409
    assert (
        await cliente.post(f"/api/partido/{pid}/descuento", headers=h, json={"minutos": 1})
    ).status_code == 409
    assert (await cliente.post(f"/api/partido/{pid}/finalizar", headers=h)).status_code == 409


async def test_partido_cancelado_no_se_puede_iniciar(cliente: AsyncClient):
    ctx = await _crear_club_y_partido(cliente, "cancelado")
    await _calibrar_valido(cliente, ctx)
    pid = ctx["partido_id"]

    canc = await cliente.post(
        f"/api/deportivo/partidos/{pid}/cancelar",
        headers=ctx["auth"],
        json={"motivo": "Tormenta eléctrica"},
    )
    assert canc.status_code == 200

    r = await cliente.post(
        f"/api/partido/{pid}/iniciar",
        headers=ctx["auth"],
        json={"ataca_hacia": "DER"},
    )
    assert r.status_code == 409


# ---------------- Aislamiento entre clubes (404) y roles (403) ----------------


async def test_aislamiento_entre_clubes_responde_404(cliente: AsyncClient):
    club_a = await _crear_club_y_partido(cliente, "aisla_a")
    club_b = await _crear_club_y_partido(cliente, "aisla_b")
    await _calibrar_valido(cliente, club_a)
    pid_a = club_a["partido_id"]
    h_b = club_b["auth"]

    assert (
        await cliente.post(
            f"/api/partido/{pid_a}/iniciar", headers=h_b, json={"ataca_hacia": "DER"}
        )
    ).status_code == 404
    assert (await cliente.post(f"/api/partido/{pid_a}/entretiempo", headers=h_b)).status_code == 404
    assert (
        await cliente.post(f"/api/partido/{pid_a}/descuento", headers=h_b, json={"minutos": 1})
    ).status_code == 404
    assert (await cliente.post(f"/api/partido/{pid_a}/finalizar", headers=h_b)).status_code == 404
    assert (await cliente.get(f"/api/partido/{pid_a}/estado", headers=h_b)).status_code == 404


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_roles_dt_y_asistente_no_operan_reloj_pero_ven_estado(
    cliente: AsyncClient, rol: str
):
    ctx = await _crear_club_y_partido(cliente, f"rol_{rol.lower()}")
    await _calibrar_valido(cliente, ctx)
    pid = ctx["partido_id"]
    h_rol = await _auth_rol(cliente, ctx, rol, "op")

    assert (
        await cliente.post(
            f"/api/partido/{pid}/iniciar", headers=h_rol, json={"ataca_hacia": "DER"}
        )
    ).status_code == 403
    assert (
        await cliente.post(f"/api/partido/{pid}/entretiempo", headers=h_rol)
    ).status_code == 403
    assert (
        await cliente.post(f"/api/partido/{pid}/descuento", headers=h_rol, json={"minutos": 2})
    ).status_code == 403
    assert (
        await cliente.post(f"/api/partido/{pid}/finalizar", headers=h_rol)
    ).status_code == 403

    # GET /estado sí está permitido para cualquier usuario del club
    r_estado = await cliente.get(f"/api/partido/{pid}/estado", headers=h_rol)
    assert r_estado.status_code == 200


async def test_rol_analista_puede_operar_el_partido(cliente: AsyncClient):
    ctx = await _crear_club_y_partido(cliente, "rol_analista")
    await _calibrar_valido(cliente, ctx)
    pid = ctx["partido_id"]
    h_analista = await _auth_rol(cliente, ctx, "ANALISTA", "op")

    r = await cliente.post(
        f"/api/partido/{pid}/iniciar", headers=h_analista, json={"ataca_hacia": "DER"}
    )
    assert r.status_code == 200


# ---------------- Difusión por WebSocket /vivo coincide con GET /estado ----------------


def test_difusion_en_vivo_coincide_con_get_estado(reloj: RelojFalso):
    async def _db_nullpool():
        async with SesionesPrueba() as session:
            yield session

    hub = HubMemoria()
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[get_db] = _db_nullpool
    app.dependency_overrides[obtener_repositorio_partidos] = lambda: PartidosEnTabla(
        Partido, SesionesPrueba
    )
    try:
        with TestClient(app) as tc, ExitStack() as pila:
            reg = tc.post(
                "/api/seguridad/registro",
                json={
                    "nombre_club": "Club WS",
                    "email": "admin_ws@test.com",
                    "password": "password123",
                },
            )
            assert reg.status_code == 201
            sesion = reg.json()
            auth = _auth(sesion["access_token"])
            club_id = sesion["usuario"]["club_id"]

            eq = tc.post(
                "/api/deportivo/equipos",
                headers=auth,
                json={"nombre": "Equipo WS", "categoria": "Primera", "temporada": "2026"},
            )
            part = tc.post(
                "/api/deportivo/partidos",
                headers=auth,
                json={
                    "equipo_id": eq.json()["id"],
                    "rival": "Rival WS",
                    "es_local": True,
                    "fecha_hora": _fecha_futura(),
                    "sede": "Sede WS",
                },
            )
            pid = part.json()["id"]

            cal = tc.post(
                f"/api/vision/partidos/{pid}/calibracion",
                headers=auth,
                json=cuerpo_valido(),
            )
            assert cal.status_code == 201

            # El DT se conecta al canal /vivo
            ws = pila.enter_context(tc.websocket_connect(f"/api/partido/{pid}/vivo"))
            ws.send_json({"tipo": "auth", "token": token_acceso(1, club_id, "DT")})
            assert ws.receive_json() == {"tipo": "listo", "partido": pid}

            # Cada transición difunde {"tipo": "estado", "datos": EstadoEnVivo} idéntico a GET /estado
            transiciones = [
                lambda: tc.post(
                    f"/api/partido/{pid}/iniciar", headers=auth, json={"ataca_hacia": "DER"}
                ),
                lambda: (reloj.avanzar(120), tc.post(
                    f"/api/partido/{pid}/descuento", headers=auth, json={"minutos": 1}
                ))[1],
                lambda: (reloj.avanzar(2580), tc.post(
                    f"/api/partido/{pid}/entretiempo", headers=auth
                ))[1],
                lambda: tc.post(f"/api/partido/{pid}/entretiempo", headers=auth),
                lambda: (reloj.avanzar(2700), tc.post(
                    f"/api/partido/{pid}/finalizar", headers=auth
                ))[1],
            ]

            for ejecutar in transiciones:
                resp_post = ejecutar()
                assert resp_post.status_code == 200
                difundido = ws.receive_json()
                resp_get = tc.get(f"/api/partido/{pid}/estado", headers=auth)
                assert resp_get.status_code == 200
                assert difundido == {"tipo": "estado", "datos": resp_get.json()}
                assert resp_post.json() == resp_get.json()
    finally:
        app.dependency_overrides.pop(obtener_hub, None)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(obtener_repositorio_partidos, None)
