"""Tabla `evento_derivado`  —  T-103 (CU-47).

Los eventos de cámara (PASE, PERDIDA, RECUPERACION) se guardan al cerrarse cada intervalo, al
finalizar el partido y al recalcular; la línea de tiempo los lee de la tabla y los distingue de
los manuales por `origen`.
"""

from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from escenarios_analisis import partido_sintetico
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, PARTIDO_A, SesionesPrueba, sembrar_partidos
from sqlalchemy import delete, select, update

from app.analisis import eventos
from app.analisis.models import EventoDerivado
from app.analisis.motor.posesion import Pase
from app.analisis.vivo import AnalisisEnVivo, obtener_analisis_en_vivo, reiniciar_analisis_en_vivo
from app.core.security import token_acceso
from app.deportivo.models import Jugador, Partido, Posicion
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


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, CLUB_A, 'ADMIN')}"}


async def _jugar(hasta: float = 400) -> None:
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    for m in partido_sintetico(PARTIDO_A, 0, hasta):
        await almacen.agregar(m)
        await partido_service.registrar_tracks_ingesta(CLUB_A, m, SesionesPrueba)
    await almacen.vaciar()


async def _filas() -> list[EventoDerivado]:
    async with SesionesPrueba() as db:
        return list((await db.execute(
            select(EventoDerivado).order_by(EventoDerivado.t, EventoDerivado.id))).scalars())


async def _finalizar_y_olvidar_el_motor() -> None:
    """El partido termina y el proceso se reinicia: ya no hay motor en memoria."""
    async with SesionesPrueba() as db:
        await db.execute(update(Partido).where(Partido.id == PARTIDO_A)
                         .values(estado=EstadoPartido.FINALIZADO.value))
        await db.commit()
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba))


async def _asignar_todos() -> None:
    async with SesionesPrueba() as db:
        for n in range(1, 23):
            db.add(Jugador(id=n, club_id=CLUB_A, equipo_id=1, nombre=f"J{n}", apellido="Prueba",
                           dorsal=n, posicion="MED", altura_cm=175))
            await db.execute(update(AsignacionTrack)
                             .where(AsignacionTrack.partido_id == PARTIDO_A,
                                    AsignacionTrack.track_id == n).values(jugador_id=n))
        await db.commit()


async def _linea(cliente: AsyncClient, **params) -> list[dict]:
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/linea-tiempo", params=params, headers=_auth())
    assert r.status_code == 200, r.text
    return r.json()["items"]


# ---------------- Los eventos salen de los pases ----------------

def test_de_pases_un_pase_completado_es_un_pase_exitoso():
    e, = eventos.de_pases([Pase(10.0, "LOCAL", 3, 5, True, (10.0, 20.0), (30.0, 25.0))])
    assert (e.tipo, e.equipo, e.resultado) == ("PASE", "LOCAL", "EXITOSO")
    assert (e.track_origen, e.track_destino) == (3, 5)
    assert (e.x_o, e.y_o, e.x_d, e.y_d) == (10.0, 20.0, 30.0, 25.0)


def test_de_pases_una_perdida_es_tambien_recuperacion_del_rival():
    perdida, recuperacion = eventos.de_pases(
        [Pase(75.5, "LOCAL", 3, 15, False, (10.0, 20.0), (40.0, 30.0))])
    assert (perdida.tipo, perdida.equipo, perdida.resultado) == ("PERDIDA", "LOCAL", "FALLIDO")
    assert (recuperacion.tipo, recuperacion.equipo, recuperacion.resultado) == (
        "RECUPERACION", "VISITANTE", "EXITOSO")
    assert recuperacion.track_origen == perdida.track_destino == 15   # quien recupera
    assert (recuperacion.x_o, recuperacion.y_o) == (40.0, 30.0)        # donde recibió el balón
    assert recuperacion.minuto == perdida.minuto == 1


# ---------------- Escritura ----------------

async def test_al_cerrarse_un_intervalo_en_vivo_se_guardan_los_eventos(cliente):
    assert await _filas() == []
    await _jugar(400)   # el intervalo 0 se cierra al llegar t = 300
    filas = await _filas()
    assert filas
    assert {f.origen for f in filas} == {"CAMARA"}
    assert {f.tipo for f in filas} <= {"PASE", "PERDIDA", "RECUPERACION"}
    assert max(f.t for f in filas) <= 300.5   # lo posterior sigue solo en el motor
    en_memoria = eventos.de_pases(obtener_analisis_en_vivo().motor(PARTIDO_A).pases)
    assert len(filas) < len(en_memoria)


async def test_al_finalizar_el_partido_quedan_todos_los_eventos(cliente):
    await _jugar(400)
    pases = list(obtener_analisis_en_vivo().motor(PARTIDO_A).pases)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    assert len(await _filas()) == len(eventos.de_pases(pases))


async def test_los_eventos_guardados_coinciden_con_las_metricas_de_cu42(cliente):
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    cuenta = Counter(f.tipo for f in await _filas())
    m = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    local, visitante = m["acumulado_local"], m["acumulado_visitante"]
    completados = local["pases_completados"] + visitante["pases_completados"]
    intentados = local["pases_intentados"] + visitante["pases_intentados"]
    assert cuenta["PASE"] == completados > 0
    assert cuenta["PERDIDA"] == intentados - completados > 0
    assert cuenta["RECUPERACION"] == cuenta["PERDIDA"]


async def test_cada_perdida_tiene_su_recuperacion_del_rival_en_el_mismo_instante(cliente):
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    filas = await _filas()
    perdidas = [f for f in filas if f.tipo == "PERDIDA"]
    recuperaciones = {(f.t, f.track_origen_id, f.equipo) for f in filas if f.tipo == "RECUPERACION"}
    assert perdidas
    for p in perdidas:
        rival = "VISITANTE" if p.equipo == "LOCAL" else "LOCAL"
        assert (p.t, p.track_destino_id, rival) in recuperaciones
        assert p.resultado == "FALLIDO" and p.confianza is None


async def test_recalcular_reemplaza_los_eventos_sin_duplicar(cliente):
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    al_cerrar = len(await _filas())
    await _finalizar_y_olvidar_el_motor()
    url = f"{BASE}/{PARTIDO_A}/metricas/recalcular"
    for _ in range(2):
        assert (await cliente.post(url, headers=_auth())).status_code == 200
        assert len(await _filas()) == al_cerrar   # mismos pases, mismas filas, sin duplicar


# ---------------- Lectura (CU-47) ----------------

async def test_la_linea_de_tiempo_lee_de_la_tabla(cliente):
    """Sin posiciones ni motor, lo único que queda es la tabla: de ahí salen los eventos."""
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    en_tabla = len(await _filas())
    async with SesionesPrueba() as db:
        await db.execute(delete(Posicion))
        await db.commit()
    await _finalizar_y_olvidar_el_motor()

    items = await _linea(cliente)
    assert len(items) == en_tabla > 0
    assert {i["origen"] for i in items} == {"CAMARA"}
    assert Counter(i["tipo"] for i in items) == Counter(f.tipo for f in await _filas())


async def test_un_partido_anterior_a_la_tabla_se_deriva_de_sus_posiciones(cliente):
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    esperado = len(await _filas())
    async with SesionesPrueba() as db:
        await db.execute(delete(EventoDerivado))
        await db.commit()
    await _finalizar_y_olvidar_el_motor()
    assert len(await _linea(cliente)) == esperado


async def test_un_partido_en_juego_muestra_tambien_los_eventos_del_intervalo_abierto(cliente):
    await _jugar(400)
    guardados = len(await _filas())
    items = await _linea(cliente)
    assert len(items) == len(eventos.de_pases(obtener_analisis_en_vivo().motor(PARTIDO_A).pases))
    assert len(items) > guardados


async def test_una_reasignacion_posterior_se_refleja_sin_reescribir_la_tabla(cliente):
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    assert all(f.jugador_origen_id is None for f in await _filas())   # todavía sin asignar
    await _finalizar_y_olvidar_el_motor()
    await _asignar_todos()
    pases = await _linea(cliente, tipo="PASE")
    assert pases and all(" J" in i["descripcion"] and "#" not in i["descripcion"] for i in pases)
    assert all(i["jugador_id"] is not None for i in pases)


async def test_los_eventos_manuales_no_se_guardan_ahi_y_siguen_siendo_manuales(cliente):
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        db.add(EventoManual(club_id=CLUB_A, partido_id=PARTIDO_A, uuid="gol-10", tipo="GOL",
                            equipo="LOCAL", minuto=10, origen="MANUAL", capturado_en=ahora,
                            creado_en=ahora, creado_por_id=1))
        await db.commit()
    await _jugar(400)
    await obtener_analisis_en_vivo().cerrar_partido(PARTIDO_A)
    assert {f.origen for f in await _filas()} == {"CAMARA"}
    items = await _linea(cliente)
    assert {i["origen"] for i in items if i["tipo"] == "GOL"} == {"MANUAL"}
    assert {i["origen"] for i in items if i["tipo"] != "GOL"} == {"CAMARA"}
