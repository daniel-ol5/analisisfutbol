"""Pruebas del canal en vivo  —  T-032.

La tabla `partido` todavía no existe (T-047). Para probar el aislamiento real
se usa un modelo falso con `club_id` (tests/modelos_falsos.py).
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
    SesionesPrueba,
    borrar_tablas_falsas,
    crear_tablas_falsas,
)
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import ws as ws_auth
from app.core.realtime import HubMemoria, canal_partido, obtener_hub
from app.core.security import token_acceso, token_refresco
from app.core.ws import Cierre
from app.main import app
from app.partido.service import (
    PartidosEnTabla,
    PartidosSinTabla,
    obtener_repositorio_partidos,
)


def _token(club_id: int, usuario_id: int = 1, rol: str = "DT") -> str:
    return token_acceso(usuario_id, club_id, rol)


@pytest.fixture
async def partidos_falsos():
    await crear_tablas_falsas()
    yield
    await borrar_tablas_falsas()


@pytest.fixture
def hub() -> HubMemoria:
    return HubMemoria()


@pytest.fixture
def cliente(hub, partidos_falsos) -> Iterator[TestClient]:
    """Cliente con el repositorio real (`tenancy`) sobre el modelo falso."""
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[obtener_repositorio_partidos] = lambda: PartidosEnTabla(PartidoFalso, SesionesPrueba)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


Conectar = Callable[[int, str], object]


def _fabrica_de_conexiones(cliente: TestClient, pila: ExitStack) -> Conectar:
    def conectar(partido_id: int, token: str):
        """Abre el canal y manda la autenticación. La pila cierra la sesión al
        final de la prueba, antes que el cliente, para no dejar tareas vivas."""
        ws = pila.enter_context(cliente.websocket_connect(f"/api/partido/{partido_id}/vivo"))
        ws.send_json({"tipo": "auth", "token": token})
        return ws
    return conectar


@pytest.fixture
def conectar(cliente) -> Iterator[Conectar]:
    with ExitStack() as pila:
        yield _fabrica_de_conexiones(cliente, pila)


def _cierre(ws) -> WebSocketDisconnect:
    with pytest.raises(WebSocketDisconnect) as e:
        ws.receive_json()
    return e.value


def _esperar(condicion, segundos: float = 2.0) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


# ---------------- Autenticación ----------------

async def test_conecta_con_token_valido(conectar):
    ws = conectar(PARTIDO_A, _token(CLUB_A))
    assert ws.receive_json() == {"tipo": "listo", "partido": PARTIDO_A}
    ws.close()


async def test_primer_mensaje_que_no_es_auth(cliente):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        ws.send_json({"tipo": "hola"})
        assert _cierre(ws).code == Cierre.MENSAJE_INVALIDO


async def test_primer_mensaje_que_no_es_json(cliente):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        ws.send_text("esto no es json")
        assert _cierre(ws).code == Cierre.MENSAJE_INVALIDO


async def test_sin_token(cliente):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        ws.send_json({"tipo": "auth"})
        cierre = _cierre(ws)
        assert cierre.code == Cierre.NO_AUTENTICADO
        assert cierre.reason == "Falta el token de acceso"


async def test_token_invalido(cliente):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        ws.send_json({"tipo": "auth", "token": "no.es.un-jwt"})
        cierre = _cierre(ws)
        assert cierre.code == Cierre.NO_AUTENTICADO
        assert cierre.reason == "Token inválido o expirado"


async def test_token_de_refresco_no_sirve(cliente):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        ws.send_json({"tipo": "auth", "token": token_refresco(1)})
        assert _cierre(ws).code == Cierre.NO_AUTENTICADO


async def test_sin_autenticacion_a_tiempo(cliente, monkeypatch):
    monkeypatch.setattr(ws_auth, "TIEMPO_AUTENTICACION_S", 0.2)
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/vivo") as ws:
        assert _cierre(ws).code == Cierre.TIEMPO_AGOTADO


# ---------------- Aislamiento entre clubes (criterio de finalización) ----------------

async def test_usuario_de_otro_club_no_puede_conectarse(cliente, conectar, hub):
    """T-032: el partido B existe, pero es de otro club."""
    ws = conectar(PARTIDO_B, _token(CLUB_A))
    cierre = _cierre(ws)
    assert cierre.code == Cierre.NO_ENCONTRADO
    assert cliente.portal.call(hub.conectados, canal_partido(CLUB_A, PARTIDO_B)) == 0
    assert cliente.portal.call(hub.conectados, canal_partido(CLUB_B, PARTIDO_B)) == 0


async def test_otro_club_e_inexistente_no_se_distinguen(conectar):
    """Mismo código y mismo motivo: no se revela que el partido existe."""
    otro_club = _cierre(conectar(PARTIDO_B, _token(CLUB_A)))
    inexistente = _cierre(conectar(INEXISTENTE, _token(CLUB_A)))
    assert otro_club.code == inexistente.code == Cierre.NO_ENCONTRADO
    assert otro_club.reason == inexistente.reason


# ---------------- Difusión ----------------

async def test_difunde_solo_a_los_del_mismo_partido(cliente, conectar, hub):
    uno = conectar(PARTIDO_A, _token(CLUB_A, usuario_id=1))
    dos = conectar(PARTIDO_A, _token(CLUB_A, usuario_id=2, rol="ANALISTA"))
    otro_partido = conectar(PARTIDO_B, _token(CLUB_B, usuario_id=3))
    for ws in (uno, dos, otro_partido):
        assert ws.receive_json()["tipo"] == "listo"

    mensaje = {"tipo": "estado", "datos": {"minuto": 12}}
    cliente.portal.call(hub.difundir, canal_partido(CLUB_A, PARTIDO_A), mensaje)

    assert uno.receive_json() == mensaje
    assert dos.receive_json() == mensaje
    # Si le hubiera llegado la difusión, sería lo primero en su cola, antes del pong
    otro_partido.send_json({"tipo": "ping"})
    assert otro_partido.receive_json() == {"tipo": "pong"}

    for ws in (uno, dos, otro_partido):
        ws.close()


async def test_desconexion_libera_el_canal(cliente, conectar, hub):
    canal = canal_partido(CLUB_A, PARTIDO_A)
    ws = conectar(PARTIDO_A, _token(CLUB_A))
    ws.receive_json()
    assert cliente.portal.call(hub.conectados, canal) == 1

    ws.close()
    assert _esperar(lambda: cliente.portal.call(hub.conectados, canal) == 0)


async def test_mensajes_basura_del_cliente_se_ignoran(conectar):
    ws = conectar(PARTIDO_A, _token(CLUB_A))
    ws.receive_json()
    ws.send_text("basura")
    ws.send_bytes(b"\x00\x01")
    ws.send_json({"tipo": "ping"})
    assert ws.receive_json() == {"tipo": "pong"}
    ws.close()


# ---------------- Hub ----------------

class _WsQueFalla:
    async def send_json(self, mensaje):
        raise RuntimeError("cliente caído")


class _WsQueRecibe:
    def __init__(self):
        self.recibidos = []

    async def send_json(self, mensaje):
        self.recibidos.append(mensaje)


async def test_hub_descarta_clientes_caidos_sin_cortar_la_difusion():
    hub = HubMemoria()
    sano, caido = _WsQueRecibe(), _WsQueFalla()
    await hub.suscribir("c", sano)
    await hub.suscribir("c", caido)

    await hub.difundir("c", {"n": 1})

    assert sano.recibidos == [{"n": 1}]
    assert await hub.conectados("c") == 1


# ---------------- Mientras no exista la tabla partido ----------------

async def test_sin_tabla_otro_club_cae_en_un_canal_aislado(hub):
    """Con `PartidosSinTabla` se acepta cualquier número, pero el canal lleva
    el club del token: el mismo `partido_id` en otro club no recibe nada."""
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[obtener_repositorio_partidos] = PartidosSinTabla
    try:
        with TestClient(app) as cliente, ExitStack() as pila:
            conectar = _fabrica_de_conexiones(cliente, pila)
            propio = conectar(5, _token(CLUB_A))
            intruso = conectar(5, _token(CLUB_B))
            propio.receive_json()
            intruso.receive_json()

            cliente.portal.call(hub.difundir, canal_partido(CLUB_A, 5), {"tipo": "estado"})

            assert propio.receive_json() == {"tipo": "estado"}
            intruso.send_json({"tipo": "ping"})
            assert intruso.receive_json() == {"tipo": "pong"}
            propio.close()
            intruso.close()
    finally:
        app.dependency_overrides.clear()
