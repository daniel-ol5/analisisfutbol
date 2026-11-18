"""Línea de tiempo y red de pases  —  T-103 (CU-47, CU-48).

Mismo escenario sintético que las pruebas de métricas: lo que muestran la línea
de tiempo y la red tiene que coincidir con los pases de CU-42.
"""

from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from escenarios_analisis import partido_sintetico
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, SesionesPrueba, sembrar_partidos
from sqlalchemy import update

from app.analisis.motor.motor import ContextoPartido, MotorPartido
from app.analisis.motor.muestras import muestra_de_mensaje
from app.analisis.vivo import AnalisisEnVivo, reiniciar_analisis_en_vivo
from app.core.security import token_acceso
from app.deportivo.models import Jugador, Posicion
from app.deportivo.schemas import EstadoPartido
from app.main import app
from app.partido import service as partido_service
from app.partido.models import AsignacionTrack, EventoManual
from app.partido.service import AnalisisDelProceso, PosicionesEnLote

BASE = "/api/analisis/partidos"


@pytest.fixture(autouse=True)
async def entorno() -> AsyncIterator[None]:
    await sembrar_partidos(EstadoPartido.EN_CURSO)
    partido_service.limpiar_memoria_tracks()
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba))
    yield
    reiniciar_analisis_en_vivo()
    partido_service.limpiar_memoria_tracks()


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(club: int = CLUB_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, club, 'ADMIN')}"}


async def _jugar(hasta: float = 400) -> None:
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    for m in partido_sintetico(PARTIDO_A, 0, hasta):
        await almacen.agregar(m)
        await partido_service.registrar_tracks_ingesta(CLUB_A, m, SesionesPrueba)
    await almacen.vaciar()


async def _asignar_todos() -> None:
    """Track N → jugador N (los 22 tracks del escenario)."""
    async with SesionesPrueba() as db:
        for n in range(1, 23):
            db.add(Jugador(id=n, club_id=CLUB_A, equipo_id=1, nombre=f"J{n}", apellido="Prueba",
                           dorsal=n, posicion="MED", altura_cm=175))
            await db.execute(update(AsignacionTrack)
                             .where(AsignacionTrack.partido_id == PARTIDO_A,
                                    AsignacionTrack.track_id == n).values(jugador_id=n))
        await db.commit()


async def _evento_manual(tipo: str, minuto: int, equipo: str = "LOCAL", *,
                         anulado: bool = False) -> None:
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        db.add(EventoManual(
            club_id=CLUB_A, partido_id=PARTIDO_A, uuid=f"{tipo}-{minuto}-{equipo}", tipo=tipo,
            equipo=equipo, minuto=minuto, origen="MANUAL",
            capturado_en=ahora, creado_en=ahora, creado_por_id=1,
            anulado_en=ahora if anulado else None))
        await db.commit()


# ---------------- El motor guarda los pases ----------------

def test_el_motor_guarda_cada_pase_con_la_posicion_del_balon():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    for m in partido_sintetico(1, 0, 120):
        motor.procesar(muestra_de_mensaje(m))
    total = motor.total.equipos
    assert len(motor.pases) == sum(e.pases_intentados for e in total.values()) > 0
    assert sum(p.completado for p in motor.pases) == sum(
        e.pases_completados for e in total.values())
    assert all(p.origen_xy != p.destino_xy for p in motor.pases)
    assert [p.t for p in motor.pases] == sorted(p.t for p in motor.pases)


# ---------------- CU-47 · Línea de tiempo ----------------

async def test_la_linea_de_tiempo_esta_ordenada_y_coincide_con_cu42(cliente):
    await _jugar()
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", headers=_auth())
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["t"] for i in items] == sorted(i["t"] for i in items)
    assert {i["origen"] for i in items} == {"CAMARA"}
    por_tipo = Counter(i["tipo"] for i in items)

    m = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    a = m["acumulado_local"], m["acumulado_visitante"]
    assert por_tipo["PASE"] == sum(e["pases_completados"] for e in a) > 0
    perdidas = sum(e["pases_intentados"] - e["pases_completados"] for e in a)
    assert por_tipo["PERDIDA"] == por_tipo["RECUPERACION"] == perdidas > 0


async def test_una_perdida_es_recuperacion_del_rival(cliente):
    await _jugar(200)
    items = (await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", headers=_auth())).json()["items"]
    perdidas = [i for i in items if i["tipo"] == "PERDIDA"]
    recuperaciones = {(i["t"], i["equipo"]) for i in items if i["tipo"] == "RECUPERACION"}
    assert perdidas
    for p in perdidas:
        rival = "VISITANTE" if p["equipo"] == "LOCAL" else "LOCAL"
        assert (p["t"], rival) in recuperaciones


async def test_filtros_por_tipo_y_equipo(cliente):
    await _jugar(200)
    url = f"{BASE}/{PARTIDO_A}/linea-tiempo"
    solo_pases = (await cliente.get(url, params={"tipo": "pase"}, headers=_auth())).json()["items"]
    assert solo_pases and {i["tipo"] for i in solo_pases} == {"PASE"}
    local = (await cliente.get(url, params={"equipo": "LOCAL"}, headers=_auth())).json()["items"]
    assert local and {i["equipo"] for i in local} == {"LOCAL"}
    ambos = (await cliente.get(url, params={"tipo": "PASE", "equipo": "VISITANTE"},
                               headers=_auth())).json()["items"]
    assert ambos and {(i["tipo"], i["equipo"]) for i in ambos} == {("PASE", "VISITANTE")}


async def test_filtros_invalidos_dan_422(cliente):
    url = f"{BASE}/{PARTIDO_A}/linea-tiempo"
    assert (await cliente.get(url, params={"tipo": "OFFSIDE"}, headers=_auth())).status_code == 422
    assert (await cliente.get(url, params={"equipo": "ARBITRO"}, headers=_auth())).status_code == 422


async def test_los_eventos_manuales_se_mezclan_sin_confundirse_con_los_de_camara(cliente):
    await _jugar(200)
    await _evento_manual("GOL", 2)
    await _evento_manual("AMARILLA", 1, "VISITANTE")
    await _evento_manual("ROJA", 3, anulado=True)     # anulado: no aparece
    items = (await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", headers=_auth())).json()["items"]
    manuales = [i for i in items if i["origen"] == "MANUAL"]
    assert [(i["tipo"], i["minuto"], i["t"]) for i in manuales] == [
        ("AMARILLA", 1, 60.0), ("GOL", 2, 120.0)]
    assert any(i["origen"] == "CAMARA" for i in items)
    assert [i["t"] for i in items] == sorted(i["t"] for i in items)

    solo_gol = (await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", params={"tipo": "GOL"},
                                  headers=_auth())).json()["items"]
    assert [i["tipo"] for i in solo_gol] == ["GOL"]


async def test_con_jugadores_asignados_la_descripcion_lleva_nombres(cliente):
    await _jugar(200)
    await _asignar_todos()
    items = (await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo",
                               params={"tipo": "PASE"}, headers=_auth())).json()["items"]
    assert items[0]["jugador_id"] is not None
    assert " J" in items[0]["descripcion"] and "#" not in items[0]["descripcion"]


async def test_linea_de_tiempo_sin_datos_es_vacia_y_de_otro_club_404(cliente):
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", headers=_auth())
    assert r.status_code == 200 and r.json()["items"] == []
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", headers=_auth(CLUB_B))
    assert r.status_code == 404


# ---------------- CU-48 · Red de pases ----------------

async def test_la_red_cuenta_solo_pases_completados_entre_jugadores_asignados(cliente):
    await _jugar()
    await _asignar_todos()
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/red-pases", headers=_auth())
    assert r.status_code == 200, r.text
    red = r.json()
    assert red["desde_minuto"] == 0 and red["hasta_minuto"] == 90
    assert red["nodos"] and red["aristas"]

    m = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    completados = m["acumulado_local"]["pases_completados"] \
        + m["acumulado_visitante"]["pases_completados"]
    assert sum(a["pases"] for a in red["aristas"]) <= completados
    assert sum(n["pases"] for n in red["nodos"]) == sum(a["pases"] for a in red["aristas"])
    ids = {n["jugador_id"] for n in red["nodos"]}
    assert all(a["origen_id"] in ids and a["destino_id"] in ids for a in red["aristas"])
    assert all(a["origen_id"] != a["destino_id"] for a in red["aristas"])
    assert all(0 <= n["x_medio"] <= 105 and 0 <= n["y_medio"] <= 68 for n in red["nodos"])
    assert {n["equipo"] for n in red["nodos"]} == {"LOCAL", "VISITANTE"}


async def _red(cliente, **params) -> dict:
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/red-pases", params=params, headers=_auth())
    assert r.status_code == 200, r.text
    return r.json()


async def test_cada_pase_enviado_es_un_pase_recibido_por_otro_nodo(cliente):
    await _jugar()
    await _asignar_todos()
    red = await _red(cliente)
    assert sum(n["pases_recibidos"] for n in red["nodos"]) == sum(n["pases"] for n in red["nodos"])
    for n in red["nodos"]:
        entran = sum(a["pases"] for a in red["aristas"] if a["destino_id"] == n["jugador_id"])
        salen = sum(a["pases"] for a in red["aristas"] if a["origen_id"] == n["jugador_id"])
        assert (n["pases_recibidos"], n["pases"]) == (entran, salen)


async def test_se_destacan_los_que_mas_pases_reciben_de_cada_equipo(cliente):
    await _jugar()
    await _asignar_todos()
    red = await _red(cliente)
    for lado in ("LOCAL", "VISITANTE"):
        equipo = [n for n in red["nodos"] if n["equipo"] == lado]
        destacados = [n for n in equipo if n["mayor_recepcion"]]
        assert destacados   # tres puestos; los empatados en el corte también entran
        minimo = min(n["pases_recibidos"] for n in destacados)
        assert minimo > 0
        assert all(n["pases_recibidos"] < minimo for n in equipo if not n["mayor_recepcion"])


async def test_los_jugadores_que_no_entran_al_circuito_salen_como_aislados(cliente):
    """En el escenario, los tracks 1, 12, 13, 16, 17 y 22 nunca tienen el balón."""
    await _jugar()
    await _asignar_todos()
    red = await _red(cliente)
    por_id = {n["jugador_id"]: n for n in red["nodos"]}
    assert len(por_id) == 22   # también aparecen los que no pasaron: se ven, no se esconden
    for jid in (1, 12, 13, 16, 17, 22):
        n = por_id[jid]
        if n["pases"] == 0 and n["pases_recibidos"] == 0:
            assert n["aislado"] is True
    assert any(n["aislado"] for n in red["nodos"])
    # Los protagonistas del circuito nunca figuran como aislados.
    assert not any(n["aislado"] for n in red["nodos"] if n["mayor_recepcion"])


async def test_el_nodo_va_en_la_posicion_media_del_jugador_normalizada(cliente):
    """Arquero local (track 1, base x = 5) y visitante (track 12, base x = 100): ambos cerca de su arco."""
    await _jugar()
    await _asignar_todos()
    por_id = {n["jugador_id"]: n for n in (await _red(cliente))["nodos"]}
    assert por_id[1]["x_medio"] < 12 and por_id[12]["x_medio"] < 12   # el visitante se espeja
    assert 25 < por_id[1]["y_medio"] < 43                              # centrado
    assert por_id[11]["x_medio"] > 55                                  # delantero local, arriba


async def test_un_jugador_con_poco_tiempo_a_la_vista_no_se_marca_como_aislado(cliente):
    await _jugar(150)   # 2 min 30 s: en el minuto 2 cada jugador está a la vista 30 s
    await _asignar_todos()
    red = await _red(cliente, desde_minuto=2, hasta_minuto=2)
    assert red["nodos"] and not any(n["aislado"] for n in red["nodos"])


async def test_filtros_de_la_red_por_equipo_y_minutos(cliente):
    await _jugar()
    await _asignar_todos()
    url = f"{BASE}/{PARTIDO_A}/red-pases"
    todo = (await cliente.get(url, headers=_auth())).json()
    local = (await cliente.get(url, params={"equipo": "LOCAL"}, headers=_auth())).json()
    assert {n["equipo"] for n in local["nodos"]} == {"LOCAL"}
    assert sum(a["pases"] for a in local["aristas"]) < sum(a["pases"] for a in todo["aristas"])
    # Los jugadores del local son los tracks 1 a 11 del escenario.
    assert all(n["jugador_id"] <= 11 for n in local["nodos"])

    primeros = (await cliente.get(url, params={"desde_minuto": 0, "hasta_minuto": 1},
                                  headers=_auth())).json()
    assert 0 < sum(a["pases"] for a in primeros["aristas"]) < sum(
        a["pases"] for a in todo["aristas"])
    fuera = (await cliente.get(url, params={"desde_minuto": 60, "hasta_minuto": 70},
                               headers=_auth())).json()
    assert fuera["nodos"] == [] and fuera["aristas"] == []


async def test_sin_jugadores_asignados_la_red_queda_vacia(cliente):
    await _jugar(200)
    red = (await cliente.get(f"{BASE}/{PARTIDO_A}/red-pases", headers=_auth())).json()
    assert red["nodos"] == [] and red["aristas"] == []


async def test_red_con_rango_invertido_422_y_de_otro_club_404(cliente):
    url = f"{BASE}/{PARTIDO_A}/red-pases"
    assert (await cliente.get(url, params={"desde_minuto": 10, "hasta_minuto": 5},
                              headers=_auth())).status_code == 422
    assert (await cliente.get(url, params={"equipo": "X"}, headers=_auth())).status_code == 422
    assert (await cliente.get(url, headers=_auth(CLUB_B))).status_code == 404
