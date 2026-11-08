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

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Equipo, Partido
from app.partido.service import AlmacenPosiciones
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
            .values(tomado_en=_ahora())
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
