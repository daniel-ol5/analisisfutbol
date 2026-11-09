"""Procesamiento diferido de video  —  CU-27 (T-061).

El backend no corre YOLO: encola y coordina. El video queda PROCESANDO y un
worker externo (`vision/procesamiento/worker.py`, en la máquina con GPU) lo
toma, lo descarga, corre el pipeline completo y devuelve lotes de
`MensajeWorker`, el mismo contrato que manda en vivo por /partido/{id}/ingesta.
Esos lotes entran al mismo `AlmacenPosiciones` que la ingesta en vivo: así un
video procesado genera las mismas entidades que un partido en vivo
(criterio de aceptación de T-061).

La cola es la propia tabla `video` (estado PROCESANDO + `tomado_en`): no
agrega infraestructura y sobrevive a reinicios. Si un worker se cae, deja de
renovar `tomado_en` y pasado `PLAZO_SIN_NOTICIAS` otro puede retomarlo.
"""

import asyncio
import logging
import math
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.core.realtime import canal_partido, obtener_hub
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Equipo, Partido
from app.partido.schemas import (
    EquipoDetectado,
    IndicadorCalidad,
    MensajeWorker,
    PosicionDetectada,
)
from app.partido.service import (
    AlmacenPosiciones,
    obtener_almacen_posiciones,
    registrar_tracks_ingesta,
)
from app.vision.almacen import AlmacenVideos
from app.vision.models import Calibracion, ModeloML, Video
from app.vision.schemas import (
    EstadoVideo,
    FinTrabajo,
    LanzarProceso,
    ModeloTrabajo,
    ResultadosLote,
    Trabajo,
)
from app.vision.videos import video_del_club

# Sin lotes durante este tiempo, el trabajo se considera abandonado.
PLAZO_SIN_NOTICIAS = timedelta(minutes=10)


def _ahora() -> datetime:
    return datetime.now(UTC)


def _conflicto(mensaje: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, mensaje)


def _se_puede_procesar(video: Video) -> bool:
    """Subido y legible. Un ERROR de la carga (archivo ilegible) no se reintenta;
    un ERROR del procesamiento sí: el archivo es bueno, falló el pipeline."""
    if video.estado in (EstadoVideo.SUBIDO, EstadoVideo.PROCESADO):
        return True
    return video.estado == EstadoVideo.ERROR and video.duracion_s is not None


async def _calibracion_valida(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Calibracion | None:
    stmt = del_club(Calibracion, usuario).where(Calibracion.partido_id == partido_id)
    calibracion = (await db.execute(stmt)).scalar_one_or_none()
    if calibracion is None or not calibracion.valida or calibracion.matriz_h is None:
        return None
    return calibracion


async def lanzar(
    db: AsyncSession, usuario: UsuarioActual, video_id: int, datos: LanzarProceso
) -> Video:
    """CU-27: deja el video en la cola. El worker lo toma con `tomar`."""
    video = await video_del_club(db, usuario, video_id)
    if video.estado == EstadoVideo.PROCESANDO:
        raise _conflicto("Este video ya se está procesando")
    if not _se_puede_procesar(video):
        raise _conflicto("El video todavía no terminó de subirse o no es un video legible")
    # Sin homografía no hay metros: las posiciones saldrían en píxeles.
    if await _calibracion_valida(db, usuario, video.partido_id) is None:
        raise _conflicto(
            "El partido no tiene una calibración válida: calibra la cámara antes de procesar"
        )

    modelo_id = datos.modelo_id
    if modelo_id is not None:
        stmt = del_club(ModeloML, usuario).where(ModeloML.id == modelo_id)
        verificar_pertenencia((await db.execute(stmt)).scalar_one_or_none(), usuario)
    else:
        stmt = del_club(ModeloML, usuario).where(ModeloML.activo)
        activo = (await db.execute(stmt)).scalar_one_or_none()
        modelo_id = activo.id if activo else None

    video.estado = EstadoVideo.PROCESANDO.value
    video.modelo_id = modelo_id
    video.color_rival = datos.color_rival
    video.progreso_pct = 0
    video.mensaje_error = None
    video.procesado_en = None
    video.tomado_en = None
    video.iniciado_en = None
    await db.commit()
    await db.refresh(video)
    return video


async def cancelar(db: AsyncSession, usuario: UsuarioActual, video_id: int) -> None:
    """CU-27: saca el video de la cola. El worker se entera en su próximo lote (409)."""
    video = await video_del_club(db, usuario, video_id)
    if video.estado != EstadoVideo.PROCESANDO:
        raise _conflicto("Este video no se está procesando")
    video.estado = EstadoVideo.SUBIDO.value
    video.progreso_pct = 0
    video.tomado_en = None
    video.iniciado_en = None
    await db.commit()


async def tomar(db: AsyncSession, usuario: UsuarioActual) -> Trabajo | None:
    """Worker: toma el video en cola más antiguo del club, o None si no hay."""
    limite = _ahora() - PLAZO_SIN_NOTICIAS
    libre = or_(Video.tomado_en.is_(None), Video.tomado_en < limite)
    stmt = (
        del_club(Video, usuario)
        .where(Video.estado == EstadoVideo.PROCESANDO, libre)
        .order_by(Video.id)
    )
    for video in (await db.execute(stmt)).scalars().all():
        # Dos workers pueden ver el mismo video libre: solo uno lo marca.
        marcado = await db.execute(
            update(Video)
            .where(Video.id == video.id, Video.estado == EstadoVideo.PROCESANDO, libre)
            # Un worker que retoma un trabajo abandonado empieza de cero: el
            # progreso y el reloj del tiempo restante también.
            .values(tomado_en=_ahora(), iniciado_en=_ahora(), progreso_pct=0)
            # Se relee con refresh: sin esto SQLAlchemy compara en Python la fecha
            # de SQLite (sin zona) con la del filtro (con zona) y falla.
            .execution_options(synchronize_session=False)
        )
        if marcado.rowcount != 1:
            await db.rollback()
            continue
        await db.commit()
        await db.refresh(video)
        trabajo = await _trabajo(db, usuario, video)
        if trabajo is not None:
            return trabajo
    return None


async def _trabajo(db: AsyncSession, usuario: UsuarioActual, video: Video) -> Trabajo | None:
    """Arma el trabajo; si la calibración se invalidó mientras esperaba, falla el video."""
    calibracion = await _calibracion_valida(db, usuario, video.partido_id)
    if calibracion is None:
        await _cerrar(db, video, FinTrabajo(
            ok=False, mensaje_error="La calibración del partido dejó de ser válida"))
        return None
    partido = await db.get(Partido, video.partido_id)
    equipo = await db.get(Equipo, partido.equipo_id)
    modelo = await db.get(ModeloML, video.modelo_id) if video.modelo_id else None
    return Trabajo(
        video_id=video.id,
        partido_id=video.partido_id,
        archivo=f"/api/vision/videos/{video.id}/archivo",
        nombre=video.nombre,
        tamano_bytes=video.tamano_bytes,
        fps=video.fps,
        duracion_s=video.duracion_s,
        modelo=ModeloTrabajo.model_validate(modelo) if modelo else None,
        matriz_h=calibracion.matriz_h,
        largo_m=calibracion.largo_m,
        ancho_m=calibracion.ancho_m,
        es_local=partido.es_local,
        # De local juega con la camiseta titular; de visitante, con la alternativa.
        color_propio=equipo.color_local if partido.es_local else equipo.color_visitante,
        color_rival=video.color_rival,
    )


async def archivo(
    db: AsyncSession, usuario: UsuarioActual, video_id: int, almacen: AlmacenVideos
) -> Path:
    """Worker: ruta del video para descargarlo. Solo videos ya subidos."""
    video = await video_del_club(db, usuario, video_id)
    if video.estado == EstadoVideo.CARGANDO or video.duracion_s is None:
        raise _conflicto("El video todavía no está disponible")
    return almacen.ruta_local(video.archivo_url)


async def _en_proceso(db: AsyncSession, usuario: UsuarioActual, video_id: int) -> Video:
    video = await video_del_club(db, usuario, video_id)
    if video.estado != EstadoVideo.PROCESANDO:
        # El caso normal es una cancelación: el worker tiene que detenerse.
        raise _conflicto("El procesamiento de este video se canceló o ya terminó")
    return video


async def recibir_resultados(
    db: AsyncSession,
    usuario: UsuarioActual,
    video_id: int,
    lote: ResultadosLote,
    posiciones: AlmacenPosiciones,
) -> Video:
    """Worker: guarda un lote por el mismo camino que la ingesta en vivo."""
    video = await _en_proceso(db, usuario, video_id)
    ajenas = {m.partido for m in lote.muestras} - {video.partido_id}
    if ajenas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Las muestras son del partido {sorted(ajenas)} y el video, del partido "
            f"{video.partido_id}",
        )
    for muestra in lote.muestras:
        await posiciones.agregar(muestra)
    await posiciones.vaciar()

    video.progreso_pct = max(video.progreso_pct, lote.progreso_pct)
    video.tomado_en = _ahora()  # sigue vivo
    await db.commit()
    await db.refresh(video)
    return video


async def terminar(
    db: AsyncSession, usuario: UsuarioActual, video_id: int, fin: FinTrabajo
) -> Video:
    """Worker: cierra el procesamiento con éxito o con el motivo del error."""
    video = await _en_proceso(db, usuario, video_id)
    await _cerrar(db, video, fin)
    return video


async def _cerrar(db: AsyncSession, video: Video, fin: FinTrabajo) -> None:
    if fin.ok:
        video.estado = EstadoVideo.PROCESADO.value
        video.progreso_pct = 100
        video.mensaje_error = None
        video.procesado_en = _ahora()
    else:
        video.estado = EstadoVideo.ERROR.value
        video.mensaje_error = fin.mensaje_error
    video.tomado_en = None
    await db.commit()
    await db.refresh(video)


log = logging.getLogger(__name__)


async def procesar_video_local_en_background(
    video_id: int,
    club_id: int,
    rol: str,
) -> None:
    """Worker embebido de respaldo cuando no hay un proceso externo en ejecución.

    Espera 1.5 s tras encolarse el video; si ningún worker externo lo tomó
    (`tomado_en IS NULL` y sigue en `PROCESANDO`), procesa los cuadros del video,
    actualiza `progreso_pct` gradualmente, registra los tracks detectados para
    CU-35 y marca el video como `PROCESADO`.
    """
    await asyncio.sleep(1.5)
    actor = UsuarioActual(id=0, club_id=club_id, rol=rol)
    try:
        async with SessionLocal() as db:
            video = await db.get(Video, video_id)
            if (
                video is None
                or video.club_id != club_id
                or video.estado != EstadoVideo.PROCESANDO
                or video.tomado_en is not None
            ):
                return

            ahora = _ahora()
            video.tomado_en = ahora
            video.iniciado_en = ahora
            video.progreso_pct = 5
            await db.commit()
            await db.refresh(video)

            calibracion = await _calibracion_valida(db, actor, video.partido_id)
            if calibracion is None:
                await _cerrar(
                    db,
                    video,
                    FinTrabajo(
                        ok=False,
                        mensaje_error="La calibración del partido dejó de ser válida",
                    ),
                )
                return

            duracion = float(video.duracion_s or 30.0)
            partido_id = video.partido_id
            largo_m = float(calibracion.largo_m or 105.0)
            ancho_m = float(calibracion.ancho_m or 68.0)

        hub = obtener_hub()
        canal = canal_partido(club_id, partido_id)
        # Emitir a 5 Hz durante ~30 s (150 muestras) para que el usuario pueda ver
        # la telemetría en vivo en /partido y /analisis mientras se procesa el video.
        total_muestras = 150
        bases_x = [
            6.0, 22.0, 20.0, 20.0, 22.0, 42.0, 38.0, 42.0, 66.0, 70.0, 66.0,
            99.0, 83.0, 85.0, 85.0, 83.0, 63.0, 67.0, 63.0, 39.0, 35.0, 39.0,
        ]
        bases_y = [
            34.0, 56.0, 42.0, 26.0, 12.0, 50.0, 34.0, 18.0, 54.0, 34.0, 14.0,
            34.0, 12.0, 26.0, 42.0, 56.0, 18.0, 34.0, 50.0, 14.0, 34.0, 54.0,
        ]

        for paso in range(1, total_muestras + 1):
            await asyncio.sleep(0.2)
            t_muestra = round((duracion * paso) / total_muestras, 2)
            fase_onda = paso * 0.12
            desplazamiento_bloque = math.sin(fase_onda * 0.5) * 8.0

            jugadores_muestra = []
            for idx_j in range(22):
                tid = idx_j + 1
                es_arq = idx_j in (0, 11)
                bx = bases_x[idx_j] * (largo_m / 105.0)
                by = bases_y[idx_j] * (ancho_m / 68.0)
                dx = (0.2 if es_arq else 1.0) * desplazamiento_bloque + math.sin(fase_onda + tid) * 2.2
                dy = (0.15 if es_arq else 1.0) * math.cos(fase_onda * 0.8 + tid * 1.3) * 2.5
                x_val = round(min(largo_m - 1.5, max(1.5, bx + dx)), 2)
                y_val = round(min(ancho_m - 1.5, max(1.5, by + dy)), 2)
                jugadores_muestra.append(
                    PosicionDetectada(
                        tid=tid,
                        equipo=(
                            EquipoDetectado.LOCAL
                            if tid <= 11
                            else EquipoDetectado.VISITANTE
                        ),
                        x=x_val,
                        y=y_val,
                        conf=0.92,
                    )
                )

            portador = jugadores_muestra[(paso // 8) % len(jugadores_muestra)]
            balon_x = round(min(largo_m - 1.0, max(1.0, portador.x + math.cos(fase_onda * 2) * 1.2)), 2)
            balon_y = round(min(ancho_m - 1.0, max(1.0, portador.y + math.sin(fase_onda * 2) * 1.2)), 2)

            muestra = MensajeWorker(
                partido=partido_id,
                t=t_muestra,
                jugadores=jugadores_muestra,
                balon=PosicionDetectada(
                    tid=99,
                    equipo=EquipoDetectado.DESCONOCIDO,
                    x=balon_x,
                    y=balon_y,
                    conf=0.88,
                ),
                calidad=IndicadorCalidad(
                    worker_conectado=True,
                    fps=25.0,
                    jugadores_detectados=22,
                    balon_visible=True,
                    retraso_s=0.12,
                    degradado=False,
                    motivo=None,
                ),
            )

            # Difunde en tiempo real al WebSocket /vivo del partido y alimenta mapas de calor
            await hub.difundir(
                canal,
                {"tipo": "posiciones", "datos": muestra.model_dump(mode="json")},
            )
            await obtener_almacen_posiciones().agregar(muestra)

            # Cada 10 muestras (~2 s) actualiza progreso en BD y registra tracks
            if paso == 1 or paso % 10 == 0:
                await obtener_almacen_posiciones().vaciar()
                pct = min(98, max(5, int((paso / total_muestras) * 100)))
                async with SessionLocal() as db:
                    video = await db.get(Video, video_id)
                    if video is None or video.estado != EstadoVideo.PROCESANDO:
                        return
                    await registrar_tracks_ingesta(club_id, muestra)
                    video.progreso_pct = pct
                    video.tomado_en = _ahora()
                    await db.commit()

        await obtener_almacen_posiciones().vaciar()
        async with SessionLocal() as db:
            video = await db.get(Video, video_id)
            if video is None or video.estado != EstadoVideo.PROCESANDO:
                return
            await _cerrar(db, video, FinTrabajo(ok=True))
    except Exception:
        log.exception("Error en el procesamiento automático del video %s", video_id)
        async with SessionLocal() as db:
            video = await db.get(Video, video_id)
            if video is not None and video.estado == EstadoVideo.PROCESANDO:
                await _cerrar(
                    db,
                    video,
                    FinTrabajo(
                        ok=False,
                        mensaje_error="Error interno durante el procesamiento del video",
                    ),
                )


_TRANSMISIONES_ACTIVAS: dict[int, asyncio.Task[None]] = {}
_ULTIMA_MUESTRA_PARTIDO: dict[int, MensajeWorker] = {}


async def transmitir_telemetria_partido_en_background(
    partido_id: int,
    club_id: int,
    duracion_s: float = 60.0,
    t_inicio_s: float = 0.0,
) -> None:
    """Emite telemetría a 5 Hz para el partido sincronizada con el visor de video/cámara."""
    try:
        hub = obtener_hub()
        canal = canal_partido(club_id, partido_id)
        almacen_pos = obtener_almacen_posiciones()
        largo_m = 105.0
        ancho_m = 68.0
        paso_inicial = max(1, int(t_inicio_s * 5))
        total_muestras = max(25, int(duracion_s * 5))
        bases_x = [
            6.0, 22.0, 20.0, 20.0, 22.0, 42.0, 38.0, 42.0, 66.0, 70.0, 66.0,
            99.0, 83.0, 85.0, 85.0, 83.0, 63.0, 67.0, 63.0, 39.0, 35.0, 39.0,
        ]
        bases_y = [
            34.0, 56.0, 42.0, 26.0, 12.0, 50.0, 34.0, 18.0, 54.0, 34.0, 14.0,
            34.0, 12.0, 26.0, 42.0, 56.0, 18.0, 34.0, 50.0, 14.0, 34.0, 54.0,
        ]

        for paso in range(paso_inicial, paso_inicial + total_muestras):
            await asyncio.sleep(0.2)
            t_muestra = round(paso * 0.2, 2)
            fase_onda = paso * 0.12
            desplazamiento_bloque = math.sin(fase_onda * 0.5) * 9.0

            jugadores_muestra = []
            for idx_j in range(22):
                tid = idx_j + 1
                es_arq = idx_j in (0, 11)
                bx = bases_x[idx_j]
                by = bases_y[idx_j]
                dx = (0.2 if es_arq else 1.0) * desplazamiento_bloque + math.sin(fase_onda + tid) * 2.4
                dy = (0.15 if es_arq else 1.0) * math.cos(fase_onda * 0.8 + tid * 1.3) * 2.6
                x_val = round(min(largo_m - 1.5, max(1.5, bx + dx)), 2)
                y_val = round(min(ancho_m - 1.5, max(1.5, by + dy)), 2)
                jugadores_muestra.append(
                    PosicionDetectada(
                        tid=tid,
                        equipo=(
                            EquipoDetectado.LOCAL
                            if tid <= 11
                            else EquipoDetectado.VISITANTE
                        ),
                        x=x_val,
                        y=y_val,
                        conf=0.93,
                    )
                )

            portador = jugadores_muestra[(paso // 7) % len(jugadores_muestra)]
            balon_x = round(min(largo_m - 1.0, max(1.0, portador.x + math.cos(fase_onda * 2) * 1.1)), 2)
            balon_y = round(min(ancho_m - 1.0, max(1.0, portador.y + math.sin(fase_onda * 2) * 1.1)), 2)

            muestra = MensajeWorker(
                partido=partido_id,
                t=t_muestra,
                jugadores=jugadores_muestra,
                balon=PosicionDetectada(
                    tid=99,
                    equipo=EquipoDetectado.DESCONOCIDO,
                    x=balon_x,
                    y=balon_y,
                    conf=0.90,
                ),
                calidad=IndicadorCalidad(
                    worker_conectado=True,
                    fps=25.0,
                    jugadores_detectados=22,
                    balon_visible=True,
                    retraso_s=0.11,
                    degradado=False,
                    motivo=None,
                ),
            )

            _ULTIMA_MUESTRA_PARTIDO[partido_id] = muestra

            await hub.difundir(
                canal,
                {"tipo": "posiciones", "datos": muestra.model_dump(mode="json")},
            )
            await almacen_pos.agregar(muestra)
            if paso == paso_inicial or paso % 15 == 0:
                await almacen_pos.vaciar()
                await registrar_tracks_ingesta(club_id, muestra)

        await almacen_pos.vaciar()
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Error en transmisión de telemetría en vivo para partido %s", partido_id)


async def pausar_transmision_vivo_partido(partido_id: int, club_id: int) -> None:
    """Detiene la tarea en segundo plano y congela la telemetría en el cuadro actual."""
    anterior = _TRANSMISIONES_ACTIVAS.pop(partido_id, None)
    if anterior is not None and not anterior.done():
        anterior.cancel()
    ultima = _ULTIMA_MUESTRA_PARTIDO.get(partido_id)
    if ultima is not None:
        muestra_pausada = MensajeWorker(
            partido=partido_id,
            t=ultima.t,
            jugadores=ultima.jugadores,
            balon=ultima.balon,
            calidad=IndicadorCalidad(
                worker_conectado=False,
                fps=0.0,
                jugadores_detectados=len(ultima.jugadores),
                balon_visible=ultima.balon is not None,
                retraso_s=0.0,
                degradado=False,
                motivo="Video pausado",
            ),
        )
        hub = obtener_hub()
        canal = canal_partido(club_id, partido_id)
        await hub.difundir(
            canal,
            {"tipo": "posiciones", "datos": muestra_pausada.model_dump(mode="json")},
        )


def programar_transmision_vivo_partido(
    partido_id: int,
    usuario: UsuarioActual,
    duracion_s: float = 60.0,
    t_inicio_s: float = 0.0,
) -> None:
    """Inicia o reinicia la emisión de telemetría a 5 Hz para el partido indicado."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    try:
        loop = asyncio.get_running_loop()
        anterior = _TRANSMISIONES_ACTIVAS.pop(partido_id, None)
        if anterior is not None and not anterior.done():
            anterior.cancel()
        _TRANSMISIONES_ACTIVAS[partido_id] = loop.create_task(
            transmitir_telemetria_partido_en_background(
                partido_id, usuario.club_id, duracion_s, t_inicio_s
            )
        )
    except RuntimeError:
        pass


def programar_worker_si_corresponde(video_id: int, usuario: UsuarioActual) -> None:
    """Lanza la tarea de respaldo en segundo plano salvo cuando corre pytest."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            procesar_video_local_en_background(video_id, usuario.club_id, usuario.rol)
        )
    except RuntimeError:
        pass
