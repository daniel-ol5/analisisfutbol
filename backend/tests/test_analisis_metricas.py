"""Métricas en vivo de punta a punta  —  T-074, T-075, T-076 (CU-42, CU-43, CU-46).

Almacén de posiciones → motor en vivo → tablas de métricas, Hub y endpoints,
con la base de pruebas. Las posiciones entran por `PosicionesEnLote.agregar`,
el mismo punto por el que pasan /ingesta, /resultados y el respaldo local.

Criterio de T-076: los intervalos se calculan durante el partido y no al finalizarlo.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from escenarios_analisis import partido_sintetico
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, SesionesPrueba, sembrar_partidos
from sqlalchemy import func, select, update

from app.analisis.models import MetricaIntervalo, MetricaTrackIntervalo
from app.analisis.motor.motor import ContextoPartido, MotorPartido
from app.analisis.motor.muestras import muestra_de_mensaje
from app.analisis.vivo import AnalisisEnVivo, reiniciar_analisis_en_vivo
from app.core.security import token_acceso
from app.deportivo.models import Jugador, Posicion
from app.deportivo.schemas import EstadoPartido
from app.main import app
from app.partido import service as partido_service
from app.partido.models import AsignacionTrack
from app.partido.service import AnalisisDelProceso, PosicionesEnLote

BASE = "/api/analisis/partidos"


class HubGrabador:
    """Hub de prueba: registra lo difundido y simula un cliente conectado."""

    def __init__(self) -> None:
        self.mensajes: list[tuple[str, dict[str, Any]]] = []

    async def suscribir(self, canal, ws) -> None: ...

    async def desuscribir(self, canal, ws) -> None: ...

    async def difundir(self, canal: str, mensaje: dict[str, Any]) -> None:
        self.mensajes.append((canal, mensaje))

    async def conectados(self, canal: str) -> int:
        return 1

    def de_tipo(self, tipo: str) -> list[dict[str, Any]]:
        return [m["datos"] for _, m in self.mensajes if m["tipo"] == tipo]


@pytest.fixture
def hub() -> HubGrabador:
    return HubGrabador()


@pytest.fixture(autouse=True)
async def entorno(hub) -> AsyncIterator[None]:
    await sembrar_partidos(EstadoPartido.EN_CURSO)
    partido_service.limpiar_memoria_tracks()
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba, hub=hub))
    yield
    reiniciar_analisis_en_vivo()
    partido_service.limpiar_memoria_tracks()


@pytest.fixture
def almacen() -> PosicionesEnLote:
    """Como el del proceso, pero con las sesiones de prueba."""
    return PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(club: int = CLUB_A, rol: str = "ADMIN") -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, club, rol)}"}


async def _jugar(almacen: PosicionesEnLote, desde: float, hasta: float,
                 tracks: bool = True) -> list:
    """Manda el partido sintético por el almacén, como /ingesta (posiciones + tracks)."""
    mensajes = partido_sintetico(PARTIDO_A, desde, hasta)
    for m in mensajes:
        await almacen.agregar(m)
        if tracks:
            await partido_service.registrar_tracks_ingesta(CLUB_A, m, SesionesPrueba)
    await almacen.vaciar()
    return mensajes


async def _contar(modelo) -> int:
    async with SesionesPrueba() as db:
        return (await db.execute(select(func.count()).select_from(modelo))).scalar_one()


async def _asignar(track_id: int, jugador_id: int, posicion: str = "MED") -> None:
    async with SesionesPrueba() as db:
        if await db.get(Jugador, jugador_id) is None:
            db.add(Jugador(id=jugador_id, club_id=CLUB_A, equipo_id=1, nombre=f"J{jugador_id}",
                           apellido="Prueba", dorsal=jugador_id, posicion=posicion,
                           altura_cm=175))
        await db.execute(update(AsignacionTrack)
                         .where(AsignacionTrack.partido_id == PARTIDO_A,
                                AsignacionTrack.track_id == track_id)
                         .values(jugador_id=jugador_id))
        await db.commit()


# ---------------- T-074 · Posesión ----------------

async def test_la_posicion_del_balon_se_guarda_con_es_balon(almacen):
    mensajes = await _jugar(almacen, 0, 10, tracks=False)
    async with SesionesPrueba() as db:
        balones = (await db.execute(select(func.count()).select_from(Posicion)
                                    .where(Posicion.es_balon.is_(True)))).scalar_one()
        jugadores = (await db.execute(select(func.count()).select_from(Posicion)
                                      .where(Posicion.es_balon.is_(False)))).scalar_one()
    assert balones == sum(1 for m in mensajes if m.balon is not None) > 0
    assert jugadores == 22 * len(mensajes)


async def test_mensaje_posesion_cada_segundo_de_partido(almacen, hub):
    await _jugar(almacen, 0, 12)
    posesion = hub.de_tipo("posesion")
    assert [round(p["t"]) for p in posesion] == list(range(12))
    ultimo = posesion[-1]
    acumulado = ultimo["acumulado"]
    assert acumulado["local_pct"] + acumulado["visitante_pct"] + acumulado["disputa_pct"] \
        == pytest.approx(100, abs=0.01)
    assert ultimo["intervalo"]["minuto_desde"] == 0
    assert ultimo["intervalo"]["minuto_hasta"] == 5
    assert set(ultimo) == {"partido_id", "t", "acumulado", "intervalo", "estado", "poseedor"}
    # El canal es el del club del partido.
    assert {c for c, _ in hub.mensajes} == {f"club:{CLUB_A}:partido:{PARTIDO_A}"}


async def test_criterio_disputa_en_el_endpoint(almacen, cliente):
    """Con el balón lejos de todos, el endpoint lo informa como disputa."""
    lejos = []
    for m in partido_sintetico(PARTIDO_A, 0, 10):
        lejos.append(m.model_copy(update={"balon": m.balon.model_copy(
            update={"x": 52.5, "y": 66.0})} if m.balon else {}))
    for m in lejos:
        await almacen.agregar(m)
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["posesion_disputa_pct"] == 100.0
    assert datos["acumulado_local"]["posesion_pct"] == 0
    assert datos["acumulado_visitante"]["posesion_pct"] == 0
    assert datos["ultimos_5_min_local"]["posesion_pct"] == 0


async def test_metricas_acumuladas_y_ultimos_5_minutos(almacen, cliente):
    await _jugar(almacen, 0, 400)
    datos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    local, visitante = datos["acumulado_local"], datos["acumulado_visitante"]
    assert local["posesion_pct"] + visitante["posesion_pct"] + datos["posesion_disputa_pct"] \
        == pytest.approx(100, abs=0.01)
    assert local["posesion_pct"] > 0 and visitante["posesion_pct"] > 0
    assert local["pases_intentados"] >= local["pases_completados"] > 0
    assert local["distancia_m"] > 0 and local["altura_linea_m"] is not None
    assert datos["ultimos_5_min_local"]["distancia_m"] < local["distancia_m"]


async def test_sin_datos_todo_en_cero(cliente):
    datos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    assert datos["acumulado_local"]["posesion_pct"] == 0
    assert datos["posesion_disputa_pct"] == 0
    assert datos["ultimos_5_min_local"] is None


@pytest.mark.parametrize("ruta", ["/metricas", "/metricas/intervalos", "/metricas/jugadores",
                                  "/metricas/jugadores/intervalos"])
async def test_otro_club_recibe_404(almacen, cliente, ruta):
    await _jugar(almacen, 0, 5)
    r = await cliente.get(f"{BASE}/{PARTIDO_A}{ruta}", headers=_auth(CLUB_B))
    assert r.status_code == 404


async def test_partido_no_en_curso_no_se_analiza(almacen, hub):
    async with SesionesPrueba() as db:
        await db.execute(update(partido_service.MODELO_PARTIDO)
                         .where(partido_service.MODELO_PARTIDO.id == PARTIDO_A)
                         .values(estado=EstadoPartido.PROGRAMADO.value))
        await db.commit()
    await _jugar(almacen, 0, 5)
    assert hub.mensajes == []
    assert await _contar(Posicion) > 0   # las posiciones se guardan igual


# ---------------- T-075 · Métricas físicas ----------------

async def test_metricas_por_jugador_solo_de_tracks_asignados(almacen, cliente):
    await _jugar(almacen, 0, 2)
    await _asignar(7, 107)      # el que hace piques
    await _asignar(3, 103)
    await _asignar(14, 114)     # visitante: el analista también puede etiquetarlo
    await _jugar(almacen, 2, 130)

    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/jugadores", headers=_auth())
    assert r.status_code == 200, r.text
    jugadores = r.json()
    assert [j["jugador_id"] for j in jugadores] == [107, 114, 103] or \
        {j["jugador_id"] for j in jugadores} == {103, 107, 114}
    distancias = [j["distancia_m"] for j in jugadores]
    assert distancias == sorted(distancias, reverse=True)
    j7 = next(j for j in jugadores if j["jugador_id"] == 107)
    assert j7["track_id"] == 7 and j7["nombre"] == "J107 Prueba" and j7["dorsal"] == 107
    assert j7["sprints"] == 4           # ida y vuelta a 8 m/s en cada minuto
    assert j7["velocidad_max_kmh"] > 21
    assert j7["minutos_jugados"] == 2   # 129,8 s

    solo_local = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/jugadores",
                                    params={"equipo": "LOCAL"}, headers=_auth())).json()
    assert {j["jugador_id"] for j in solo_local} == {103, 107}
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/jugadores", params={"equipo": "X"},
                          headers=_auth())
    assert r.status_code == 422


async def test_track_sin_asignar_suma_al_equipo_pero_no_aparece(almacen, cliente):
    await _jugar(almacen, 0, 30)
    jugadores = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/jugadores",
                                   headers=_auth())).json()
    assert jugadores == []
    datos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    assert datos["acumulado_local"]["distancia_m"] > 0


async def test_reasignacion_respeta_las_vigencias(almacen, cliente):
    """El track 7 es del jugador 70 hasta t = 400 y del 71 después."""
    await _jugar(almacen, 0, 2)
    await _asignar(7, 70)
    async with SesionesPrueba() as db:
        db.add(Jugador(id=71, club_id=CLUB_A, equipo_id=1, nombre="J71", apellido="Prueba",
                       dorsal=71, posicion="MED", altura_cm=175))
        await db.execute(update(AsignacionTrack).where(AsignacionTrack.track_id == 7)
                         .values(hasta_t=400.0))
        db.add(AsignacionTrack(club_id=CLUB_A, partido_id=PARTIDO_A, track_id=7,
                               jugador_id=71, equipo_detectado="LOCAL", desde_t=400.0))
        await db.commit()
    await _jugar(almacen, 2, 620)

    por_intervalo = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/jugadores/intervalos",
                                       headers=_auth())).json()
    minutos = {j["jugador_id"]: [i["minuto_desde"] for i in j["intervalos"]]
               for j in por_intervalo}
    assert minutos == {70: [0], 71: [5]}   # el intervalo 5-10 es mayormente de 71
    entrada = por_intervalo[0]["intervalos"][0]
    assert set(entrada) == {"minuto_desde", "minuto_hasta", "distancia_m",
                            "velocidad_max_kmh", "sprints", "minutos_jugados"}


async def test_mensaje_metricas_jugadores_cada_minuto(almacen, hub):
    await _jugar(almacen, 0, 2)
    await _asignar(7, 107)
    await _jugar(almacen, 2, 185)
    mensajes = hub.de_tipo("metricas_jugadores")
    assert [int(m["t"] // 60) for m in mensajes] == [0, 1, 2, 3]
    ultimo = mensajes[-1]
    assert ultimo["visitante"] == []
    assert [j["jugador_id"] for j in ultimo["local"]] == [107]
    assert ultimo["local"][0]["distancia_m"] > 0


# ---------------- T-076 · Intervalos ----------------

async def test_criterio_intervalos_guardados_durante_el_partido(almacen, cliente, hub):
    await _jugar(almacen, 0, 310)
    async with SesionesPrueba() as db:
        estado = (await db.get(partido_service.MODELO_PARTIDO, PARTIDO_A)).estado
    assert estado == EstadoPartido.EN_CURSO.value
    assert await _contar(MetricaIntervalo) == 2           # intervalo 0, local y visitante
    assert await _contar(MetricaTrackIntervalo) == 22

    intervalos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/intervalos",
                                    headers=_auth())).json()
    assert [(i["minuto_desde"], i["minuto_hasta"]) for i in intervalos] == [(0, 5)]
    i0 = intervalos[0]
    assert i0["local"]["posesion_pct"] + i0["visitante"]["posesion_pct"] \
        + i0["posesion_disputa_pct"] == pytest.approx(100, abs=0.01)
    assert hub.de_tipo("intervalo") == intervalos


async def test_al_finalizar_el_ultimo_intervalo_queda_parcial(almacen, cliente, hub):
    await _jugar(almacen, 0, 400)
    r = await cliente.post(f"/api/partido/{PARTIDO_A}/finalizar", headers=_auth())
    assert r.status_code == 200, r.text

    intervalos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/intervalos",
                                    headers=_auth())).json()
    assert [(i["minuto_desde"], i["minuto_hasta"]) for i in intervalos] == [(0, 5), (5, 7)]
    async with SesionesPrueba() as db:
        parciales = (await db.execute(select(MetricaIntervalo.parcial)
                                      .order_by(MetricaIntervalo.intervalo))).scalars().all()
    assert parciales == [False, False, True, True]
    assert hub.de_tipo("intervalo")[-1]["minuto_hasta"] == 7

    # Ya finalizado, una posición tardía no reabre el motor.
    mensajes_antes = len(hub.mensajes)
    await _jugar(almacen, 400, 402)
    assert len(hub.mensajes) == mensajes_antes


async def test_recalcular_da_lo_mismo_que_en_vivo(almacen, cliente):
    await _jugar(almacen, 0, 2)
    await _asignar(1, 101, posicion="ARQ")
    await _asignar(7, 107)
    await _jugar(almacen, 2, 640)
    await cliente.post(f"/api/partido/{PARTIDO_A}/finalizar", headers=_auth())

    async def foto() -> tuple:
        rutas = ["/metricas", "/metricas/intervalos", "/metricas/jugadores",
                 "/metricas/jugadores/intervalos"]
        return tuple([(await cliente.get(f"{BASE}/{PARTIDO_A}{r}", headers=_auth())).json()
                      for r in rutas])

    en_vivo = await foto()
    r = await cliente.post(f"{BASE}/{PARTIDO_A}/metricas/recalcular", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json() == en_vivo[0]
    assert await foto() == en_vivo
    assert len(en_vivo[1]) == 3


async def test_recalcular_permisos_y_estado(almacen, cliente):
    await _jugar(almacen, 0, 5)
    r = await cliente.post(f"{BASE}/{PARTIDO_A}/metricas/recalcular", headers=_auth())
    assert r.status_code == 409          # EN_CURSO: lo calcula el motor en vivo
    r = await cliente.post(f"{BASE}/{PARTIDO_A}/metricas/recalcular", headers=_auth(rol="DT"))
    assert r.status_code == 403
    r = await cliente.post(f"{BASE}/{PARTIDO_A}/metricas/recalcular",
                           headers=_auth(CLUB_B, "ANALISTA"))
    assert r.status_code == 404


async def test_reconstruccion_tras_reinicio_de_la_api(almacen, hub):
    """La API se reinicia en t = 200 con el partido EN_CURSO: al llegar la siguiente
    posición el motor se reconstruye desde `posicion` y el resultado es el mismo
    que sin reinicio."""
    mensajes = await _jugar(almacen, 0, 200)

    # Reinicio: se pierden los motores (y el almacén vacío, ya se guardó todo).
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba, hub=hub))
    almacen_nuevo = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    mensajes += await _jugar(almacen_nuevo, 200, 330)

    esperado = MotorPartido(ContextoPartido(partido_id=PARTIDO_A))
    for m in mensajes:
        esperado.procesar(muestra_de_mensaje(m))

    async with SesionesPrueba() as db:
        filas = (await db.execute(select(MetricaIntervalo)
                                  .where(MetricaIntervalo.intervalo == 0))).scalars().all()
    guardado = {f.equipo: f for f in filas}
    for equipo, acum in esperado.intervalos[0].equipos.items():
        assert guardado[equipo].posesion_s == pytest.approx(acum.posesion_s)
        assert guardado[equipo].distancia_m == pytest.approx(acum.distancia_m)
        assert guardado[equipo].pases_intentados == acum.pases_intentados
        assert guardado[equipo].n_altura == acum.n_altura
    assert filas[0].disputa_s == pytest.approx(esperado.intervalos[0].disputa_s)


async def test_reconstruccion_guarda_lo_pendiente_antes_de_leer(hub):
    """Si el almacén tenía filas sin guardar al crear el motor, las guarda primero."""
    async with SesionesPrueba() as db:
        await db.execute(update(partido_service.MODELO_PARTIDO)
                         .where(partido_service.MODELO_PARTIDO.id == PARTIDO_A)
                         .values(estado=EstadoPartido.PROGRAMADO.value))
        await db.commit()
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, tamano_lote=1000,
                               inactividad_s=60, analisis=AnalisisDelProceso())
    mensajes = partido_sintetico(PARTIDO_A, 0, 4)
    for m in mensajes[:10]:
        await almacen.agregar(m)            # no está EN_CURSO: quedan en el buffer
    assert almacen.pendientes(PARTIDO_A) == 230
    async with SesionesPrueba() as db:
        await db.execute(update(partido_service.MODELO_PARTIDO)
                         .where(partido_service.MODELO_PARTIDO.id == PARTIDO_A)
                         .values(estado=EstadoPartido.EN_CURSO.value))
        await db.commit()
    analisis = AnalisisEnVivo(sesiones=SesionesPrueba, hub=hub)
    reiniciar_analisis_en_vivo(analisis)
    await almacen.agregar(mensajes[10])
    assert await _contar(Posicion) == 230
    motor = analisis.motor(PARTIDO_A)
    assert motor is not None and motor.t == mensajes[10].t
    await almacen.vaciar()
