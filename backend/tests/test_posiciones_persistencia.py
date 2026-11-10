"""Persistencia de posiciones fuera de /ingesta  —  T-033.

El almacén de posiciones es UNO por proceso, con un buffer por partido. Aquí
se prueba que los otros caminos que escriben en él guardan bien, sin tocar su
código:

- El procesamiento de video grabado (`POST /vision/videos/{id}/resultados`).
- El procesamiento local de respaldo (`procesar_video_local_en_background`),
  que pide un almacén nuevo en cada llamada: antes de este cambio sus
  posiciones se perdían, porque cada instancia acumulaba un solo mensaje.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from partidos_prueba import PARTIDO_A, PARTIDO_B, contar_posiciones, sembrar_partidos
from sqlalchemy import event, select
from test_vision_procesamiento import _club, _lanzar, _lote, _muestra, _video_subido

from app.core.database import SessionLocal, engine
from app.deportivo.models import Posicion
from app.main import app, lifespan
from app.partido.schemas import MensajeWorker
from app.partido.service import (
    PosicionesEnLote,
    obtener_almacen_posiciones,
    reiniciar_almacen_posiciones,
)
from app.vision import procesamiento
from app.vision.almacen import AlmacenEnDisco, obtener_almacen_videos
from app.vision.models import Video


def _mensaje(partido: int, t: float, jugadores: int = 22) -> MensajeWorker:
    return MensajeWorker.model_validate({
        "partido": partido, "t": t,
        "jugadores": [{"tid": i, "equipo": "LOCAL", "x": 10.0 + i, "y": 5.0, "conf": 0.9}
                      for i in range(1, jugadores + 1)],
        "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 52.5, "y": 34.0, "conf": 0.7},
        "calidad": {"worker_conectado": True, "fps": 5.0, "jugadores_detectados": jugadores,
                    "balon_visible": True, "retraso_s": 0.2, "degradado": False},
    })


@pytest.fixture(autouse=True)
def almacen_limpio() -> Iterator[None]:
    """Cada prueba arranca con el almacén del proceso vacío."""
    reiniciar_almacen_posiciones()
    yield
    reiniciar_almacen_posiciones()


@pytest.fixture
def inserts() -> Iterator[list[int]]:
    """Filas de cada INSERT en `posicion`, por el motor de la app."""
    registro: list[int] = []

    def espiar(conn, cursor, sql, parametros, contexto, executemany):
        if sql.startswith("INSERT INTO posicion "):
            registro.append(len(parametros) if executemany else 1)

    event.listen(engine.sync_engine, "before_cursor_execute", espiar)
    yield registro
    event.remove(engine.sync_engine, "before_cursor_execute", espiar)


# ---------------- Un almacén por proceso, un buffer por partido ----------------

async def test_siempre_es_el_mismo_almacen_y_guarda_en_la_tabla_posicion():
    almacen = obtener_almacen_posiciones()
    assert almacen is obtener_almacen_posiciones()
    assert isinstance(almacen, PosicionesEnLote)
    assert almacen.modelo is Posicion


async def test_patron_de_un_almacen_nuevo_por_llamada_no_pierde_nada(inserts):
    """Reproduce lo que hace `procesar_video_local_en_background`:
    `obtener_almacen_posiciones().agregar(...)` en cada muestra y
    `obtener_almacen_posiciones().vaciar()` de vez en cuando."""
    await sembrar_partidos()
    for i in range(7):
        await obtener_almacen_posiciones().agregar(_mensaje(PARTIDO_A, i * 0.2))
    assert await contar_posiciones() == 0          # todavía en el buffer

    await obtener_almacen_posiciones().vaciar()

    assert await contar_posiciones(PARTIDO_A) == 7 * 23
    assert inserts == [7 * 23]                      # un solo INSERT masivo


async def test_cada_partido_junta_su_propio_lote(inserts):
    lote = PosicionesEnLote.TAMANO_LOTE
    almacen = obtener_almacen_posiciones()
    for i in range(lote - 1):
        await almacen.agregar(_mensaje(PARTIDO_A, i * 0.2))
        await almacen.agregar(_mensaje(PARTIDO_B, i * 0.2))
    assert inserts == []                            # ninguno llegó a su lote

    await almacen.agregar(_mensaje(PARTIDO_A, 99.0))   # A completa el suyo

    assert inserts == [lote * 23]
    assert await contar_posiciones(PARTIDO_A) == lote * 23
    assert await contar_posiciones(PARTIDO_B) == 0
    assert almacen.pendientes(PARTIDO_B) == (lote - 1) * 23


async def test_tras_un_tiempo_sin_datos_se_guarda_solo():
    almacen = obtener_almacen_posiciones()
    almacen.inactividad_s = 0.1
    await almacen.agregar(_mensaje(PARTIDO_A, 0.0))
    await almacen.agregar(_mensaje(PARTIDO_A, 0.2))

    for _ in range(50):
        if await contar_posiciones(PARTIDO_A) == 2 * 23:
            break
        await asyncio.sleep(0.05)
    assert await contar_posiciones(PARTIDO_A) == 2 * 23
    assert almacen.pendientes(PARTIDO_A) == 0


async def test_cada_mensaje_nuevo_reinicia_la_espera():
    """Sin depender del reloj real: cada mensaje cancela el temporizador
    anterior y programa uno nuevo, más tarde."""
    almacen = obtener_almacen_posiciones()
    almacen.inactividad_s = 60.0
    vencimientos = []
    anteriores = []
    for i in range(4):
        await almacen.agregar(_mensaje(PARTIDO_A, i * 0.2))
        temporizador = almacen._temporizadores[PARTIDO_A]
        vencimientos.append(temporizador.when())
        anteriores.append(temporizador)
        await asyncio.sleep(0.01)

    assert vencimientos == sorted(vencimientos) and len(set(vencimientos)) == 4
    assert all(t.cancelled() for t in anteriores[:-1])
    assert not anteriores[-1].cancelled()
    assert almacen.pendientes(PARTIDO_A) == 4 * 23
    assert await contar_posiciones() == 0
    await almacen.vaciar()                      # y vaciar cancela el último
    assert anteriores[-1].cancelled()


async def test_al_apagar_la_api_se_guarda_lo_pendiente():
    async with lifespan(app):
        await obtener_almacen_posiciones().agregar(_mensaje(PARTIDO_A, 0.0))
        assert await contar_posiciones() == 0
    assert await contar_posiciones(PARTIDO_A) == 23


async def test_si_la_base_falla_se_pierde_el_lote_pero_no_se_corta(caplog):
    almacen = obtener_almacen_posiciones()
    almacen.modelo = Video                        # columnas que no existen en `video`
    await almacen.agregar(_mensaje(PARTIDO_A, 0.0))
    await almacen.vaciar()                        # no lanza: queda en el log
    assert "No se pudo guardar" in caplog.text
    assert almacen.pendientes(PARTIDO_A) == 0


# ---------------- Video grabado: los caminos de Araceli y Daniel ----------------

@pytest.fixture
def almacen_videos(tmp_path) -> Iterator[AlmacenEnDisco]:
    almacen = AlmacenEnDisco(tmp_path / "videos")
    app.dependency_overrides[obtener_almacen_videos] = lambda: almacen
    yield almacen
    app.dependency_overrides.pop(obtener_almacen_videos, None)


@pytest.fixture
async def cliente(almacen_videos) -> AsyncIterator[AsyncClient]:
    """Sin reemplazar el almacén de posiciones: se usa el real."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="module")
def mp4(tmp_path_factory) -> bytes:
    ruta = tmp_path_factory.mktemp("clip") / "clip.mp4"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), 25, (64, 48))
    rng = np.random.default_rng(3)
    for _ in range(50):
        escritor.write(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8))
    escritor.release()
    return ruta.read_bytes()


async def test_los_lotes_del_worker_de_video_se_guardan(cliente, mp4, inserts):
    """`POST /vision/videos/{id}/resultados` (Araceli) guarda en `posicion`."""
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    assert (await _lanzar(cliente, club, video)).status_code == 200

    partido = club["partido_id"]
    r = await _lote(cliente, club, video, 40, [_muestra(partido, t) for t in (0, 0.2, 0.4)])
    assert r.status_code == 200, r.text

    # 2 jugadores + balón por muestra; un INSERT por lote, como en vivo
    async with SessionLocal() as db:
        filas = (await db.execute(select(Posicion).where(Posicion.partido_id == partido)
                                  .order_by(Posicion.t, Posicion.track_id))).scalars().all()
    assert [(f.t, f.track_id) for f in filas] == [
        (0, 0), (0, 7), (0, 9), (0.2, 0), (0.2, 7), (0.2, 9), (0.4, 0), (0.4, 7), (0.4, 9)]
    assert inserts == [9]


async def test_lote_de_video_de_otro_club_no_escribe(cliente, mp4):
    propio = await _club(cliente, "a")
    ajeno = await _club(cliente, "b")
    video = await _video_subido(cliente, propio, mp4)
    await _lanzar(cliente, propio, video)

    r = await _lote(cliente, ajeno, video, 40, [_muestra(propio["partido_id"], 0)])
    assert r.status_code == 404
    assert await contar_posiciones() == 0


class _AsyncioSinEsperas:
    """`asyncio` real salvo `sleep`, para correr el respaldo local sin esperar 30 s."""

    def __getattr__(self, nombre: str):
        return getattr(asyncio, nombre)

    @staticmethod
    async def sleep(_segundos: float, resultado=None):
        return resultado


async def test_el_procesamiento_local_de_respaldo_guarda_todas_sus_posiciones(
        cliente, mp4, monkeypatch):
    """Caso real de Daniel: `procesar_video_local_en_background` pide un
    almacén nuevo en cada muestra. Con un almacén por proceso no pierde nada."""
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    assert (await _lanzar(cliente, club, video)).status_code == 200
    monkeypatch.setattr(procesamiento, "asyncio", _AsyncioSinEsperas())

    async with SessionLocal() as db:
        club_id = (await db.get(Video, video["id"])).club_id
    await procesamiento.procesar_video_local_en_background(video["id"], club_id, "ADMIN")

    async with SessionLocal() as db:
        assert (await db.get(Video, video["id"])).estado == "PROCESADO"
    # 150 muestras de 22 jugadores + balón, ninguna perdida
    assert await contar_posiciones(club["partido_id"]) == 150 * 23
    assert obtener_almacen_posiciones().pendientes(club["partido_id"]) == 0
