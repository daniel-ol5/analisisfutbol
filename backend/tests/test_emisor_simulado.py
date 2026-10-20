"""Pruebas del emisor simulado  —  T-034.

La simulación se prueba sin red. Al final, una prueba de punta a punta manda
la simulación por /ingesta y comprueba que llega a un cliente de /vivo.
"""

import math
from collections.abc import Iterator
from contextlib import ExitStack

import pytest
from starlette.testclient import TestClient

from app.core.realtime import HubMemoria, obtener_hub
from app.core.security import token_acceso, token_ingesta
from app.main import app
from app.partido.schemas import MensajeWorker
from app.partido.service import PartidosSinTabla, obtener_repositorio_partidos
from scripts.emisor_simulado import (
    ACEL_MAX,
    VEL_MAX,
    Simulacion,
    argumentos,
    emitir,
    url_ws,
)

LARGO, ANCHO = 105.0, 68.0
DT = 0.2


def _simular(segundos: float, semilla: int = 1, **kw) -> tuple[Simulacion, list[dict]]:
    sim = Simulacion(partido=7, semilla=semilla, **kw)
    return sim, [sim.paso(DT) for _ in range(round(segundos / DT))]


# ---------------- Contrato ----------------

def test_cada_mensaje_cumple_el_contrato():
    _, mensajes = _simular(60)
    for m in mensajes:
        MensajeWorker.model_validate(m)


def test_22_jugadores_11_por_equipo_y_el_balon():
    _, mensajes = _simular(30)
    for m in mensajes:
        equipos = [j["equipo"] for j in m["jugadores"]]
        assert equipos.count("LOCAL") == 11
        assert equipos.count("VISITANTE") == 11
        assert len({j["tid"] for j in m["jugadores"]}) == 22, "los tid deben ser estables y únicos"
    assert sum(m["balon"] is not None for m in mensajes) > 0.8 * len(mensajes)


def test_t_avanza_a_la_frecuencia_pedida():
    _, mensajes = _simular(10, t0=600.0)
    assert mensajes[0]["t"] == pytest.approx(600.2)
    assert mensajes[-1]["t"] == pytest.approx(610.0)


# ---------------- Realismo ----------------

def test_todo_dentro_de_la_cancha():
    for medidas in [(LARGO, ANCHO), (90.0, 55.0)]:
        _, mensajes = _simular(120, largo=medidas[0], ancho=medidas[1])
        for m in mensajes:
            for p in m["jugadores"] + ([m["balon"]] if m["balon"] else []):
                assert 0 <= p["x"] <= medidas[0] and 0 <= p["y"] <= medidas[1], p


def test_velocidades_y_aceleraciones_humanas():
    sim = Simulacion(partido=7, semilla=3)
    previo = {j.tid: (j.x, j.y, 0.0, 0.0) for j in sim.jugadores}
    for _ in range(round(120 / DT)):
        sim.paso(DT)
        for j in sim.jugadores:
            x0, y0, vx0, vy0 = previo[j.tid]
            vx, vy = (j.x - x0) / DT, (j.y - y0) / DT
            assert math.hypot(vx, vy) <= VEL_MAX + 1e-9, f"jugador {j.tid} a {math.hypot(vx, vy):.1f} m/s"
            # La aceleración se acota sobre la velocidad interna; al chocar con
            # la línea la componente se anula, por eso se mide con margen.
            assert math.hypot(j.vx - vx0, j.vy - vy0) <= ACEL_MAX * DT + 1e-9 or j.vx == 0 or j.vy == 0
            previo[j.tid] = (j.x, j.y, j.vx, j.vy)


def test_distancia_recorrida_plausible():
    """Un jugador de campo recorre entre 8 y 13 km en 90 minutos."""
    sim = Simulacion(partido=7, semilla=5)
    previo = {j.tid: (j.x, j.y) for j in sim.jugadores}
    recorrido = dict.fromkeys(previo, 0.0)
    for _ in range(round(300 / DT)):
        sim.paso(DT)
        for j in sim.jugadores:
            recorrido[j.tid] += math.hypot(j.x - previo[j.tid][0], j.y - previo[j.tid][1])
            previo[j.tid] = (j.x, j.y)
    de_campo = [d for j, d in ((j, recorrido[j.tid]) for j in sim.jugadores) if not j.es_arquero]
    km_90 = sum(de_campo) / len(de_campo) * (90 * 60 / 300) / 1000
    assert 8 <= km_90 <= 13, f"{km_90:.1f} km por partido"


def test_los_equipos_mantienen_su_lado_y_la_pelota_circula():
    sim, mensajes = _simular(300, semilla=2)
    # El arquero local nunca cruza la mitad; el visitante tampoco
    for m in mensajes:
        arquero_local = next(j for j in m["jugadores"] if j["tid"] == 1)
        arquero_visitante = next(j for j in m["jugadores"] if j["tid"] == 12)
        assert arquero_local["x"] < LARGO / 4
        assert arquero_visitante["x"] > 3 * LARGO / 4
    # Hubo cambios de posesión (pases interceptados, robos, remates)
    cambios, anterior = 0, None
    sim = Simulacion(partido=7, semilla=2)
    for _ in range(round(300 / DT)):
        sim.paso(DT)
        actual = sim.equipo_con_posesion()
        if actual and anterior and actual != anterior:
            cambios += 1
        anterior = actual or anterior
    assert cambios >= 5


def test_misma_semilla_misma_simulacion():
    _, a = _simular(20, semilla=42)
    _, b = _simular(20, semilla=42)
    _, c = _simular(20, semilla=43)
    assert a == b
    assert a != c


# ---------------- Línea de comandos ----------------

def test_url_ws():
    assert url_ws("http://localhost:8000/api", 3) == "ws://localhost:8000/api/partido/3/ingesta"
    assert url_ws("https://x.com/api/", 3) == "wss://x.com/api/partido/3/ingesta"


def test_argumentos_por_defecto():
    args = argumentos(["--partido", "4", "--token", "t"])
    assert (args.frecuencia, args.largo, args.ancho, args.url) == (
        5.0, 105.0, 68.0, "http://localhost:8000/api")


def test_argumentos_exigen_credenciales():
    with pytest.raises(SystemExit):
        argumentos(["--partido", "4"])
    with pytest.raises(SystemExit):
        argumentos(["--partido", "4", "--token", "t", "--frecuencia", "0"])


async def test_emitir_respeta_la_cantidad_de_mensajes():
    enviados: list[str] = []

    async def enviar(texto: str) -> None:
        enviados.append(texto)

    resumen = await emitir(enviar, Simulacion(7, frecuencia=5.0, semilla=1), duracion=3,
                           tiempo_real=False)
    assert resumen.enviados == len(enviados) == 15


# ---------------- De punta a punta ----------------

@pytest.fixture
def cliente() -> Iterator[TestClient]:
    hub = HubMemoria()
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[obtener_repositorio_partidos] = PartidosSinTabla
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


async def test_la_simulacion_alimenta_el_panel_en_vivo(cliente):
    """Lo que manda el emisor por /ingesta llega, válido, a /vivo."""
    with ExitStack() as pila:
        panel = pila.enter_context(cliente.websocket_connect("/api/partido/7/vivo"))
        panel.send_json({"tipo": "auth", "token": token_acceso(1, 1, "DT")})
        assert panel.receive_json()["tipo"] == "listo"

        worker = pila.enter_context(cliente.websocket_connect("/api/partido/7/ingesta"))
        worker.send_json({"tipo": "auth", "token": token_ingesta(1, 7)})
        assert worker.receive_json()["tipo"] == "listo"

        async def enviar(texto: str) -> None:
            worker.send_text(texto)

        await emitir(enviar, Simulacion(7, semilla=1), duracion=2, tiempo_real=False)

        recibidos = [panel.receive_json() for _ in range(10)]
        assert all(r["tipo"] == "posiciones" for r in recibidos)
        assert [r["datos"]["t"] for r in recibidos] == pytest.approx(
            [round(0.2 * i, 2) for i in range(1, 11)])
        # Ningún mensaje fue rechazado: lo siguiente que responde es el error de este
        worker.send_text("{}")
        assert worker.receive_json()["invalidos_seguidos"] == 1
