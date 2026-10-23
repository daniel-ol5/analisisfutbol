"""Pruebas de la ingesta del worker  —  T-033.

Criterio de finalización: los mensajes se validan contra el contrato
(`MensajeWorker`) y la inserción es masiva (un solo INSERT por lote).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack

import pytest
from modelos_falsos import (
    CLUB_A,
    CLUB_B,
    INEXISTENTE,
    PARTIDO_A,
    PARTIDO_B,
    PartidoFalso,
    PosicionFalsa,
    SesionesPrueba,
    borrar_tablas_falsas,
    crear_tablas_falsas,
    motor,
)
from sqlalchemy import event, func, select
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.realtime import HubMemoria, obtener_hub
from app.core.security import token_acceso, token_ingesta
from app.core.ws import Cierre
from app.main import app
from app.partido import router as partido_router
from app.partido.service import (
    PartidosEnTabla,
    PosicionesDescartadas,
    PosicionesEnLote,
    obtener_almacen_posiciones,
    obtener_repositorio_partidos,
)

PUNTOS_POR_MENSAJE = 23   # 22 jugadores + balón


def _mensaje(partido: int = PARTIDO_A, t: float = 0.0) -> dict:
    jugadores = [
        {"tid": i, "equipo": "LOCAL" if i <= 11 else "VISITANTE",
         "x": 10.0 + i, "y": 5.0 + i, "conf": 0.9}
        for i in range(1, 23)
    ]
    return {
        "partido": partido, "t": t, "jugadores": jugadores,
        "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 52.5, "y": 34.0, "conf": 0.7},
        "calidad": {"worker_conectado": True, "fps": 5.0, "jugadores_detectados": 22,
                    "balon_visible": True, "retraso_s": 0.2, "degradado": False},
    }


# ---------------- Fixtures ----------------

@pytest.fixture
async def tablas_falsas():
    await crear_tablas_falsas()
    yield
    await borrar_tablas_falsas()


@pytest.fixture
def hub() -> HubMemoria:
    return HubMemoria()


@pytest.fixture
def cliente(hub, tablas_falsas) -> Iterator[TestClient]:
    """Hub aislado, verificación real con `tenancy` y persistencia real por
    lotes, todo sobre los modelos falsos."""
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[obtener_repositorio_partidos] = lambda: PartidosEnTabla(PartidoFalso, SesionesPrueba)
    app.dependency_overrides[obtener_almacen_posiciones] = lambda: PosicionesEnLote(PosicionFalsa, SesionesPrueba)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


Abrir = Callable[[str, int, str], object]


@pytest.fixture
def abrir(cliente) -> Iterator[Abrir]:
    """Abre un canal (`vivo` o `ingesta`) y manda la autenticación."""
    with ExitStack() as pila:
        def _abrir(canal: str, partido_id: int, token: str):
            ws = pila.enter_context(cliente.websocket_connect(f"/api/partido/{partido_id}/{canal}"))
            ws.send_json({"tipo": "auth", "token": token})
            return ws
        yield _abrir


@pytest.fixture
def inserts() -> Iterator[list[tuple[str, bool, int]]]:
    """Registra cada INSERT en posicion_falsa: (sql, executemany, filas)."""
    registro: list[tuple[str, bool, int]] = []

    def espiar(conn, cursor, sql, parametros, contexto, executemany):
        if "INSERT INTO posicion_falsa" in sql:
            filas = len(parametros) if executemany else 1
            registro.append((sql, executemany, filas))

    event.listen(motor.sync_engine, "before_cursor_execute", espiar)
    yield registro
    event.remove(motor.sync_engine, "before_cursor_execute", espiar)


def _cierre(ws) -> WebSocketDisconnect:
    with pytest.raises(WebSocketDisconnect) as e:
        ws.receive_json()
    return e.value


async def _contar_filas() -> int:
    async with SesionesPrueba() as db:
        return (await db.execute(select(func.count()).select_from(PosicionFalsa))).scalar_one()


def _esperar_filas(cliente: TestClient, esperadas: int, segundos: float = 3.0) -> int:
    limite = time.monotonic() + segundos
    while True:
        filas = cliente.portal.call(_contar_filas)
        if filas >= esperadas or time.monotonic() > limite:
            return filas
        time.sleep(0.02)


# ---------------- Autenticación del worker ----------------

async def test_worker_se_conecta_con_su_token(abrir):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    assert ws.receive_json() == {"tipo": "listo", "partido": PARTIDO_A}


async def test_token_de_usuario_no_sirve_para_ingestar(abrir):
    ws = abrir("ingesta", PARTIDO_A, token_acceso(1, CLUB_A, "ADMIN"))
    assert _cierre(ws).code == Cierre.NO_AUTENTICADO


async def test_token_de_ingesta_no_sirve_para_escuchar(abrir):
    ws = abrir("vivo", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    assert _cierre(ws).code == Cierre.NO_AUTENTICADO


async def test_token_de_otro_partido(abrir):
    ws = abrir("ingesta", INEXISTENTE, token_ingesta(CLUB_A, PARTIDO_A))
    assert _cierre(ws).code == Cierre.NO_ENCONTRADO


async def test_token_para_un_partido_de_otro_club(abrir):
    ws = abrir("ingesta", PARTIDO_B, token_ingesta(CLUB_A, PARTIDO_B))
    assert _cierre(ws).code == Cierre.NO_ENCONTRADO


# ---------------- Validación contra el contrato ----------------

async def test_mensaje_valido_no_genera_respuesta(abrir):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()
    ws.send_json(_mensaje())
    ws.send_text("{}")   # el único que responde es este, inválido
    assert ws.receive_json()["tipo"] == "error"


async def test_mensaje_invalido_responde_error_y_sigue_conectado(abrir):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()

    malo = _mensaje()
    malo["jugadores"][0]["conf"] = 1.5          # fuera de [0, 1]
    del malo["calidad"]
    ws.send_json(malo)

    error = ws.receive_json()
    assert error["tipo"] == "error"
    assert error["invalidos_seguidos"] == 1
    campos = {tuple(e["loc"]) for e in error["detalle"]}
    assert ("jugadores", 0, "conf") in campos
    assert ("calidad",) in campos

    ws.send_text("no es json")
    assert ws.receive_json()["invalidos_seguidos"] == 2
    ws.send_bytes(b"\x00")
    assert ws.receive_json()["detalle"][0]["type"] == "binario"


async def test_mensaje_de_otro_partido_es_invalido(abrir):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()
    ws.send_json(_mensaje(partido=PARTIDO_B))
    assert ws.receive_json()["detalle"][0]["type"] == "partido_distinto"


async def test_cierra_tras_demasiados_invalidos_seguidos(abrir):
    limite = partido_router.MAX_INVALIDOS_SEGUIDOS
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()

    for _ in range(limite - 1):
        ws.send_text("{}")
        assert ws.receive_json()["tipo"] == "error"
    ws.send_text("{}")
    cierre = _cierre(ws)
    assert cierre.code == Cierre.MENSAJE_INVALIDO
    assert str(limite) in cierre.reason


async def test_un_mensaje_valido_reinicia_la_cuenta(abrir):
    limite = partido_router.MAX_INVALIDOS_SEGUIDOS
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()

    for _ in range(limite - 1):
        ws.send_text("{}")
        ws.receive_json()
    ws.send_json(_mensaje())
    ws.send_text("{}")
    assert ws.receive_json()["invalidos_seguidos"] == 1


# ---------------- Difusión a /vivo ----------------

async def test_lo_recibido_se_difunde_al_canal_vivo(abrir):
    dt = abrir("vivo", PARTIDO_A, token_acceso(1, CLUB_A, "DT"))
    otro_club = abrir("vivo", PARTIDO_B, token_acceso(2, CLUB_B, "DT"))
    worker = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    for ws in (dt, otro_club, worker):
        assert ws.receive_json()["tipo"] == "listo"

    worker.send_json(_mensaje(t=12.4))

    recibido = dt.receive_json()
    assert recibido["tipo"] == "posiciones"
    assert recibido["datos"]["t"] == 12.4
    assert len(recibido["datos"]["jugadores"]) == 22

    otro_club.send_json({"tipo": "ping"})
    assert otro_club.receive_json() == {"tipo": "pong"}


async def test_los_invalidos_no_se_difunden(abrir):
    dt = abrir("vivo", PARTIDO_A, token_acceso(1, CLUB_A, "DT"))
    worker = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    dt.receive_json()
    worker.receive_json()

    worker.send_text("{}")
    worker.receive_json()
    dt.send_json({"tipo": "ping"})
    assert dt.receive_json() == {"tipo": "pong"}


# ---------------- Inserción masiva (criterio de finalización) ----------------

async def test_un_lote_se_inserta_con_un_solo_insert(cliente, abrir, inserts):
    lote = PosicionesEnLote.TAMANO_LOTE
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()

    for i in range(lote):
        ws.send_json(_mensaje(t=i * 0.2))

    assert _esperar_filas(cliente, lote * PUNTOS_POR_MENSAJE) == lote * PUNTOS_POR_MENSAJE
    assert len(inserts) == 1, f"Se esperaba 1 INSERT masivo, hubo {len(inserts)}"


async def test_no_inserta_antes_de_completar_el_lote(cliente, abrir, inserts):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()
    for i in range(PosicionesEnLote.TAMANO_LOTE - 1):
        ws.send_json(_mensaje(t=i * 0.2))
    ws.send_text("{}")          # sincroniza: cuando llega el error, ya procesó todo
    ws.receive_json()

    assert inserts == []
    assert cliente.portal.call(_contar_filas) == 0


async def test_al_desconectarse_vacia_lo_pendiente(cliente, abrir, inserts):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()
    for i in range(3):
        ws.send_json(_mensaje(t=i * 0.2))
    ws.close()

    assert _esperar_filas(cliente, 3 * PUNTOS_POR_MENSAJE) == 3 * PUNTOS_POR_MENSAJE
    assert len(inserts) == 1


async def test_filas_siguen_el_modelo_de_datos(cliente, abrir):
    ws = abrir("ingesta", PARTIDO_A, token_ingesta(CLUB_A, PARTIDO_A))
    ws.receive_json()
    ws.send_json(_mensaje(t=7.5))
    ws.close()
    _esperar_filas(cliente, PUNTOS_POR_MENSAJE)

    async def balon():
        async with SesionesPrueba() as db:
            return (await db.execute(select(PosicionFalsa).where(PosicionFalsa.track_id == 0))
                    ).scalar_one()

    fila = cliente.portal.call(balon)
    assert (fila.partido_id, fila.t, fila.x_m, fila.y_m, fila.confianza) == (
        PARTIDO_A, 7.5, 52.5, 34.0, 0.7)


async def test_sin_tabla_las_posiciones_se_descartan():
    almacen = PosicionesDescartadas()
    from app.partido.schemas import MensajeWorker
    await almacen.agregar(MensajeWorker.model_validate(_mensaje()))
    await almacen.vaciar()   # no falla ni guarda nada


# ---------------- Emisión del token ----------------

@pytest.mark.parametrize("rol", ["ADMIN", "ANALISTA"])
async def test_emitir_token_de_ingesta(cliente, abrir, rol):
    r = cliente.post(f"/api/partido/{PARTIDO_A}/token-ingesta",
                     headers={"Authorization": f"Bearer {token_acceso(1, CLUB_A, rol)}"})
    assert r.status_code == 201, r.text
    datos = r.json()
    assert datos["partido_id"] == PARTIDO_A

    ws = abrir("ingesta", PARTIDO_A, datos["token"])
    assert ws.receive_json()["tipo"] == "listo"


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_otros_roles_no_emiten_token(cliente, rol):
    r = cliente.post(f"/api/partido/{PARTIDO_A}/token-ingesta",
                     headers={"Authorization": f"Bearer {token_acceso(1, CLUB_A, rol)}"})
    assert r.status_code == 403


async def test_emitir_token_sin_autenticacion(cliente):
    assert cliente.post(f"/api/partido/{PARTIDO_A}/token-ingesta").status_code == 401


async def test_no_emite_token_para_partido_de_otro_club(cliente):
    r = cliente.post(f"/api/partido/{PARTIDO_B}/token-ingesta",
                     headers={"Authorization": f"Bearer {token_acceso(1, CLUB_A, 'ADMIN')}"})
    assert r.status_code == 404
