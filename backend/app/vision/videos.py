"""Lógica de la carga de video por partes  —  CU-27, CU-28 (T-060).

    1. POST /partidos/{id}/videos    declara nombre, tipo y tamaño: el formato se
                                     valida ANTES de subir un solo byte.
    2. PUT  /videos/{id}/contenido   cada trozo con `Content-Range`, en orden.
    3. GET  /videos/{id}             `bytes_recibidos` dice desde dónde retomar.

Al llegar el último trozo el archivo se lee con OpenCV: si es legible queda
SUBIDO con su duración, fps y resolución; si no, ERROR con el motivo.

Como `service.py`, no conoce FastAPI más allá de HTTPException: recibe una
sesión, datos y el almacén.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath

import cv2
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Partido
from app.deportivo.schemas import EstadoPartido
from app.vision.almacen import AlmacenVideos, TrozoDemasiadoGrande
from app.vision.models import Video
from app.vision.schemas import FORMATOS_VIDEO, EstadoVideo, VideoIniciar

# Un video grabado es de un partido que se jugó; uno cancelado no tiene video.
ESTADOS_PARTIDO_SIN_VIDEO = {EstadoPartido.CANCELADO}

_RANGO = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")

# Firma del contenedor en los primeros bytes. MP4 y MOV (ISO BMFF) llevan el
# tipo de la primera caja en los bytes 4 a 8; Matroska empieza con su cabecera EBML.
_CAJAS_ISO = {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip"}
_EBML = b"\x1a\x45\xdf\xa3"
_LARGO_FIRMA = 8


class _FirmaInvalida(Exception):
    pass


def extension_de(nombre: str) -> str:
    return PurePosixPath(nombre.lower()).suffix


def validar_formato(nombre: str, tipo: str) -> str:
    """Devuelve la extensión si el formato es soportado; si no, 415.

    El navegador a veces no conoce el MIME (.mkv suele llegar vacío o como
    application/octet-stream): entonces decide la extensión, y la firma del
    primer trozo lo confirma.
    """
    extension = extension_de(nombre)
    soportados = ", ".join(e.lstrip(".").upper() for e in FORMATOS_VIDEO)
    if extension not in FORMATOS_VIDEO:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Formato no soportado ({extension or 'sin extensión'}). Se aceptan {soportados}.",
        )
    tipo = tipo.strip().lower()
    if tipo not in ("", "application/octet-stream", *FORMATOS_VIDEO[extension]):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"El tipo {tipo} no corresponde a un video {extension.lstrip('.').upper()}.",
        )
    return extension


def firma_valida(cabecera: bytes, extension: str) -> bool:
    if extension == ".mkv":
        return cabecera.startswith(_EBML)
    return cabecera[4:8] in _CAJAS_ISO


async def _verificando_firma(
    trozos: AsyncIterator[bytes], extension: str
) -> AsyncIterator[bytes]:
    """Deja pasar el cuerpo, pero antes de escribir nada mira los primeros bytes."""
    pendiente = b""
    verificada = False
    async for pedazo in trozos:
        if verificada:
            yield pedazo
            continue
        pendiente += pedazo
        if len(pendiente) < _LARGO_FIRMA:
            continue
        if not firma_valida(pendiente, extension):
            raise _FirmaInvalida
        verificada = True
        yield pendiente
    if not verificada:
        # Un primer trozo de menos de 8 bytes no alcanza para reconocer el formato.
        if not pendiente or not firma_valida(pendiente, extension):
            raise _FirmaInvalida
        yield pendiente


async def _video_del_club(db: AsyncSession, usuario: UsuarioActual, video_id: int) -> Video:
    stmt = del_club(Video, usuario).where(Video.id == video_id)
    return verificar_pertenencia((await db.execute(stmt)).scalar_one_or_none(), usuario)


async def _partido_del_club(db: AsyncSession, usuario: UsuarioActual, partido_id: int) -> Partido:
    stmt = del_club(Partido, usuario).where(Partido.id == partido_id)
    return verificar_pertenencia((await db.execute(stmt)).scalar_one_or_none(), usuario)


async def listar_videos(db: AsyncSession, usuario: UsuarioActual, partido_id: int) -> list[Video]:
    """CU-28: videos del partido, el más nuevo primero. 404 si el partido es ajeno."""
    await _partido_del_club(db, usuario, partido_id)
    stmt = (
        del_club(Video, usuario)
        .where(Video.partido_id == partido_id)
        .order_by(Video.creado_en.desc(), Video.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def ver_video(db: AsyncSession, usuario: UsuarioActual, video_id: int) -> Video:
    """CU-27, CU-28: estado de la carga y del procesamiento."""
    return await _video_del_club(db, usuario, video_id)


async def iniciar_carga(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: VideoIniciar,
    almacen: AlmacenVideos,
) -> Video:
    """T-060 paso 1: valida formato y tamaño sin recibir el archivo."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado in ESTADOS_PARTIDO_SIN_VIDEO:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No se puede cargar video de un partido cancelado"
        )
    extension = validar_formato(datos.nombre, datos.tipo)
    if datos.tamano_bytes > settings.video_max_bytes:
        gib = settings.video_max_bytes / 1024**3
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"El video supera el máximo permitido de {gib:g} GiB",
        )

    video = Video(
        club_id=usuario.club_id,
        partido_id=partido_id,
        archivo_url="",
        nombre=datos.nombre,
        tipo=datos.tipo,
        tamano_bytes=datos.tamano_bytes,
        bytes_recibidos=0,
        estado=EstadoVideo.CARGANDO.value,
    )
    db.add(video)
    await db.flush()  # para tener el id con el que se arma la clave
    video.archivo_url = almacen.clave(usuario.club_id, video.id, extension)
    await db.commit()
    await db.refresh(video)
    return video


def rango(content_range: str | None) -> tuple[int, int, int]:
    """`bytes 0-8388607/4500000000` → (0, 8388607, 4500000000)."""
    coincide = _RANGO.match((content_range or "").strip())
    if not coincide:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Falta el encabezado Content-Range con el formato 'bytes inicio-fin/total'",
        )
    inicio, fin, total = (int(g) for g in coincide.groups())
    if fin < inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Content-Range con fin menor que inicio")
    return inicio, fin, total


async def recibir_trozo(
    db: AsyncSession,
    usuario: UsuarioActual,
    video_id: int,
    content_range: str | None,
    cuerpo: AsyncIterator[bytes],
    almacen: AlmacenVideos,
) -> Video:
    """T-060 paso 2: guarda un trozo. Van en orden y sin huecos."""
    video = await _video_del_club(db, usuario, video_id)
    if video.estado != EstadoVideo.CARGANDO:
        raise HTTPException(status.HTTP_409_CONFLICT, "La carga de este video ya terminó")

    inicio, fin, total = rango(content_range)
    if total != video.tamano_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"El total del Content-Range ({total}) no coincide con el tamaño declarado "
            f"({video.tamano_bytes})",
        )
    if fin >= total:
        raise HTTPException(
            status.HTTP_416_RANGE_NOT_SATISFIABLE, "El trozo se pasa del final del archivo"
        )
    if inicio != video.bytes_recibidos:
        # El cliente perdió la cuenta (o se cortó la red): que retome desde acá.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Se esperaba el trozo que empieza en el byte {video.bytes_recibidos}",
        )
    largo = fin - inicio + 1
    if largo > settings.video_max_trozo_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Cada trozo puede tener como máximo {settings.video_max_trozo_bytes} bytes",
        )

    extension = extension_de(video.archivo_url)
    if inicio == 0:
        cuerpo = _verificando_firma(cuerpo, extension)
    try:
        escritos = await almacen.escribir(video.archivo_url, inicio, cuerpo, largo)
    except _FirmaInvalida:
        await almacen.borrar(video.archivo_url)
        video.estado = EstadoVideo.ERROR.value
        video.mensaje_error = (
            f"El contenido no es un video {extension.lstrip('.').upper()}: "
            "revisa que el archivo no esté dañado o renombrado"
        )
        await db.commit()
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, video.mensaje_error) from None
    except TrozoDemasiadoGrande:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "El cuerpo trae más bytes que el Content-Range"
        ) from None
    if escritos != largo:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Llegaron {escritos} bytes y el Content-Range anunciaba {largo}: reenvía el trozo",
        )

    # Avanza solo si nadie avanzó antes: dos envíos del mismo trozo a la vez
    # escriben los mismos bytes en el mismo lugar, y solo uno cuenta.
    avance = await db.execute(
        update(Video)
        .where(Video.id == video.id, Video.bytes_recibidos == inicio)
        .values(bytes_recibidos=fin + 1)
    )
    if avance.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Otro envío de este trozo llegó primero; consulta el estado"
        )
    await db.commit()
    await db.refresh(video)

    if video.bytes_recibidos == video.tamano_bytes:
        await _cerrar_carga(db, video, almacen)
    return video


def leer_video(ruta: Path) -> tuple[int, int, str] | None:
    """Duración (s), fps y resolución leyendo el archivo; None si no se puede."""
    captura = cv2.VideoCapture(str(ruta))
    try:
        if not captura.isOpened():
            return None
        legible, _ = captura.read()
        fps = captura.get(cv2.CAP_PROP_FPS)
        cuadros = captura.get(cv2.CAP_PROP_FRAME_COUNT)
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not legible or fps <= 0 or ancho <= 0 or alto <= 0:
            return None
        return round(cuadros / fps), round(fps), f"{ancho}x{alto}"
    finally:
        captura.release()


async def _cerrar_carga(db: AsyncSession, video: Video, almacen: AlmacenVideos) -> None:
    datos = await asyncio.to_thread(leer_video, almacen.ruta_local(video.archivo_url))
    if datos is None:
        video.estado = EstadoVideo.ERROR.value
        video.mensaje_error = (
            "El archivo llegó completo pero no se pudo leer como video. "
            "Puede estar dañado o usar un códec no soportado."
        )
    else:
        video.duracion_s, video.fps, video.resolucion = datos
        video.estado = EstadoVideo.SUBIDO.value
        video.mensaje_error = None
    await db.commit()
    await db.refresh(video)
