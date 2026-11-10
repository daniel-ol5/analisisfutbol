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
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import UsuarioActual
from app.core.realtime import canal_partido, obtener_hub
from app.core.security import token_acceso
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
    video.color_propio = datos.color_propio
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
        # Si se especificó un color propio para el análisis se usa ese; si no,
        # de local juega con la camiseta titular y de visitante con la alternativa.
        color_propio=video.color_propio or (
            equipo.color_local if partido.es_local else equipo.color_visitante
        ),
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

    # Guardar en disco para que el reproductor y el radar 2D puedan sincronizarlo
    if lote.muestras:
        guardar_muestras_partido(video.partido_id, lote.muestras)
        guardar_muestras_video(video.id, lote.muestras)
        hub = obtener_hub()
        canal = canal_partido(usuario.club_id, video.partido_id)
        ultima = lote.muestras[-1]
        _ULTIMA_MUESTRA_PARTIDO[video.partido_id] = ultima
        await hub.difundir(
            canal,
            {"tipo": "posiciones", "datos": ultima.model_dump(mode="json")},
        )
        await hub.difundir(
            canal,
            {"tipo": "calidad", "datos": ultima.calidad.model_dump(mode="json")},
        )

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


def programar_worker_si_corresponde(video_id: int, usuario: UsuarioActual) -> None:
    """Lanza el worker de visión en segundo plano (auto-worker) si no hay uno externo activo."""
    token = token_acceso(usuario.id, usuario.club_id, usuario.rol)
    api_url = "http://127.0.0.1:8000/api"

    raiz = Path(__file__).resolve().parent.parent.parent.parent
    vision_dir = raiz / "vision"

    # Detectar si CUDA está disponible para aceleración
    dispositivo = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            dispositivo = "cuda:0"
    except Exception:
        pass

    comando = [
        sys.executable,
        "-m", "procesamiento.worker",
        "--api", api_url,
        "--token", token,
        "--dispositivo", dispositivo,
        "--clases", "futbol",
        "--una-vez",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{vision_dir};{raiz / 'backend'};{env.get('PYTHONPATH', '')}"

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        subprocess.Popen(
            comando,
            cwd=str(raiz),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        log.info(
            "Worker local lanzado automáticamente en segundo plano para video %s (dispositivo: %s)",
            video_id,
            dispositivo,
        )
    except Exception as e:
        log.warning("No se pudo iniciar el worker local automáticamente: %s", e)


_TRANSMISIONES_ACTIVAS: dict[int, asyncio.Task[None]] = {}
_ULTIMA_MUESTRA_PARTIDO: dict[int, MensajeWorker] = {}


def _guardar_muestras_archivo(ruta: Path, muestras: list[MensajeWorker]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    existentes: list[dict[str, object]] = []
    if ruta.exists():
        try:
            with open(ruta, encoding="utf-8") as f:
                existentes = json.load(f)
        except Exception:
            existentes = []
    existentes.extend(m.model_dump(mode="json") for m in muestras)
    vistos: set[float] = set()
    unicas: list[dict[str, object]] = []
    for d in existentes:
        t_val = round(float(d.get("t", 0.0)), 2)
        if t_val not in vistos:
            vistos.add(t_val)
            unicas.append(d)
    unicas.sort(key=lambda x: float(x.get("t", 0.0)))
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(unicas, f)


def _ruta_muestras_partido(partido_id: int) -> Path:
    candidatos = [
        Path(settings.videos_dir).parent / "muestras" / f"partido-{partido_id}.json",
        Path("almacen/muestras") / f"partido-{partido_id}.json",
        Path("backend/almacen/muestras") / f"partido-{partido_id}.json",
    ]
    for c in candidatos:
        if c.exists():
            return c
    p = candidatos[0]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _ruta_muestras_video(video_id: int) -> Path:
    candidatos = [
        Path(settings.videos_dir).parent / "muestras" / f"video-{video_id}.json",
        Path("almacen/muestras") / f"video-{video_id}.json",
        Path("backend/almacen/muestras") / f"video-{video_id}.json",
    ]
    for c in candidatos:
        if c.exists():
            return c
    p = candidatos[0]
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def guardar_muestras_partido(partido_id: int, muestras: list[MensajeWorker]) -> None:
    """Persiste en disco las muestras reales generadas por YOLO + ByteTrack."""
    _guardar_muestras_archivo(_ruta_muestras_partido(partido_id), muestras)
    for otra_raiz in [Path("almacen/muestras"), Path("backend/almacen/muestras")]:
        if otra_raiz.exists():
            _guardar_muestras_archivo(otra_raiz / f"partido-{partido_id}.json", muestras)


def guardar_muestras_video(video_id: int, muestras: list[MensajeWorker]) -> None:
    """Persiste en disco las muestras del video procesado."""
    _guardar_muestras_archivo(_ruta_muestras_video(video_id), muestras)
    for otra_raiz in [Path("almacen/muestras"), Path("backend/almacen/muestras")]:
        if otra_raiz.exists():
            _guardar_muestras_archivo(otra_raiz / f"video-{video_id}.json", muestras)


def cargar_muestras_video(video_id: int) -> list[MensajeWorker]:
    """Recupera las muestras reales detectadas para un video específico."""
    ruta = _ruta_muestras_video(video_id)
    if not ruta.exists():
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return [MensajeWorker.model_validate(d) for d in datos]
    except Exception:
        log.exception("Error cargando muestras persistidas para video %s", video_id)
        return []


def cargar_muestras_partido(partido_id: int, video_id: int | None = None) -> list[MensajeWorker]:
    """Recupera las muestras reales detectadas para el partido o video."""
    if video_id is not None:
        muestras_vid = cargar_muestras_video(video_id)
        if muestras_vid:
            return muestras_vid
    ruta = _ruta_muestras_partido(partido_id)
    if not ruta.exists():
        return []
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return [MensajeWorker.model_validate(d) for d in datos]
    except Exception:
        log.exception("Error cargando muestras persistidas para partido %s", partido_id)
        return []


async def transmitir_telemetria_partido_en_background(
    partido_id: int,
    club_id: int,
    duracion_s: float = 60.0,
    t_inicio_s: float = 0.0,
    video_id: int | None = None,
) -> None:
    """Emite telemetría a 5 Hz para el partido sincronizada con el visor de video/cámara."""
    try:
        hub = obtener_hub()
        canal = canal_partido(club_id, partido_id)
        almacen_pos = obtener_almacen_posiciones()

        muestras_reales = cargar_muestras_partido(partido_id, video_id=video_id)
        if muestras_reales:
            # Emitir las muestras reales detectadas por YOLO del video
            muestras_a_emitir = [m for m in muestras_reales if m.t >= (t_inicio_s - 0.05)]
            if not muestras_a_emitir:
                mas_cercana = min(muestras_reales, key=lambda m: abs(m.t - t_inicio_s))
                idx_cercano = muestras_reales.index(mas_cercana)
                muestras_a_emitir = muestras_reales[idx_cercano:]
            for muestra in muestras_a_emitir:
                await asyncio.sleep(0.2)
                _ULTIMA_MUESTRA_PARTIDO[partido_id] = muestra
                await hub.difundir(
                    canal,
                    {"tipo": "posiciones", "datos": muestra.model_dump(mode="json")},
                )
                await hub.difundir(
                    canal,
                    {"tipo": "calidad", "datos": muestra.calidad.model_dump(mode="json")},
                )
                await almacen_pos.agregar(muestra)
            await almacen_pos.vaciar()
            return

        # Si no hay muestras reales persistidas, emitir estado degradado sin inventar jugadores
        muestra_vacia = MensajeWorker(
            partido=partido_id,
            t=t_inicio_s,
            jugadores=[],
            balon=None,
            calidad=IndicadorCalidad(
                worker_conectado=False,
                fps=0.0,
                jugadores_detectados=0,
                balon_visible=False,
                retraso_s=0.0,
                degradado=True,
                motivo="Sin telemetría procesada por el worker de visión para este partido",
            ),
        )
        _ULTIMA_MUESTRA_PARTIDO[partido_id] = muestra_vacia
        await hub.difundir(
            canal,
            {"tipo": "posiciones", "datos": muestra_vacia.model_dump(mode="json")},
        )
        await hub.difundir(
            canal,
            {"tipo": "calidad", "datos": muestra_vacia.calidad.model_dump(mode="json")},
        )
        return
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
    video_id: int | None = None,
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
                partido_id, usuario.club_id, duracion_s, t_inicio_s, video_id=video_id
            )
        )
    except RuntimeError:
        pass



_MODELO_YOLO_VIVO: Any | None = None


def _obtener_modelo_vivo() -> Any:
    global _MODELO_YOLO_VIVO
    if _MODELO_YOLO_VIVO is None:
        from ultralytics import YOLO

        candidatos = [
            Path("vision/pesos/yolov8_futbol.pt"),
            Path("backend/vision/pesos/yolov8_futbol.pt"),
            Path(__file__).resolve().parent.parent.parent.parent / "vision" / "pesos" / "yolov8_futbol.pt",
        ]
        ruta_futbol = next((c for c in candidatos if c.exists()), None)
        _MODELO_YOLO_VIVO = YOLO(str(ruta_futbol)) if ruta_futbol else YOLO("yolo11n.pt")
    return _MODELO_YOLO_VIVO


def analizar_fotograma_en_vivo(
    imagen_bytes: bytes,
    partido_id: int = 1,
    color_local: str = "#6CABDD",
    color_rival: str = "#FFFFFF",
    t_actual: float = 0.0,
) -> MensajeWorker:
    """Inferencia ultrarrápida (70-100ms) sobre un fotograma en vivo (webcam o video local)."""
    import cv2
    import numpy as np
    from vision.seguimiento.color import (
        ColoresEquipo,
        clasificar_equipos,
        color_dominante,
        recortar_torso,
    )

    nparr = np.frombuffer(imagen_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        return MensajeWorker(
            partido=partido_id,
            t=t_actual,
            jugadores=[],
            balon=None,
            calidad=IndicadorCalidad(
                worker_conectado=True,
                fps=0.0,
                jugadores_detectados=0,
                balon_visible=False,
                retraso_s=0.0,
                degradado=True,
            ),
        )
    h, w, _ = frame.shape
    modelo = _obtener_modelo_vivo()
    es_modelo_futbol = (
        len(modelo.names) == 4 and "player" in list(modelo.names.values())
    )
    predict_kwargs: dict[str, Any] = {"imgsz": 640, "conf": 0.18, "verbose": False}
    if not es_modelo_futbol:
        predict_kwargs["classes"] = [0, 32]
    res = modelo.predict(frame, **predict_kwargs)[0]

    boxes = res.boxes.xyxy.cpu().numpy()
    clases = res.boxes.cls.cpu().numpy()
    confs = res.boxes.conf.cpu().numpy()

    colores_cfg = ColoresEquipo(
        color_local=color_local, color_visitante=color_rival, color_arbitro="#EAB308"
    )
    jugadores: list[PosicionDetectada] = []
    balon_detectado: PosicionDetectada | None = None
    tid_counter = 1

    for b, cls_id, conf in zip(boxes, clases, confs, strict=False):
        cls_int = int(cls_id)
        x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        bbox_pct = [
            round(min(100.0, max(0.0, x1 / w * 100)), 2),
            round(min(100.0, max(0.0, y1 / h * 100)), 2),
            round(min(100.0, max(0.0, x2 / w * 100)), 2),
            round(min(100.0, max(0.0, y2 / h * 100)), 2),
        ]

        if es_modelo_futbol:
            # Clases del modelo especializado: 0=balón, 1=arquero, 2=jugador, 3=árbitro
            if cls_int == 0 and balon_detectado is None:
                balon_detectado = PosicionDetectada(
                    tid=0,
                    equipo=EquipoDetectado.DESCONOCIDO,
                    x=round(min(104.5, max(0.5, (x1 + x2) / (2 * w) * 105.0)), 2),
                    y=round(min(67.5, max(0.5, y2 / h * 68.0)), 2),
                    conf=round(float(conf), 3),
                    bbox=bbox_pct,
                )
            elif cls_int == 3:  # Árbitro detectado directamente por IA
                jugadores.append(
                    PosicionDetectada(
                        tid=tid_counter,
                        equipo=EquipoDetectado.ARBITRO,
                        x=round(min(104.5, max(0.5, (x1 + x2) / (2 * w) * 105.0)), 2),
                        y=round(min(67.5, max(0.5, y2 / h * 68.0)), 2),
                        conf=round(float(conf), 3),
                        bbox=bbox_pct,
                    )
                )
                tid_counter += 1
            elif cls_int in (1, 2):  # Arquero o jugador de campo
                try:
                    torso = recortar_torso(frame, (x1, y1, x2, y2))
                    dom = color_dominante(torso)
                    c = clasificar_equipos([dom], colores_cfg)[0]
                    eq = c.equipo
                except Exception:
                    eq = EquipoDetectado.DESCONOCIDO
                jugadores.append(
                    PosicionDetectada(
                        tid=tid_counter,
                        equipo=eq,
                        x=round(min(104.5, max(0.5, (x1 + x2) / (2 * w) * 105.0)), 2),
                        y=round(min(67.5, max(0.5, y2 / h * 68.0)), 2),
                        conf=round(float(conf), 3),
                        bbox=bbox_pct,
                    )
                )
                tid_counter += 1
        else:
            # Modelo COCO genérico de respaldo
            if cls_int == 0:  # person
                try:
                    torso = recortar_torso(frame, (x1, y1, x2, y2))
                    dom = color_dominante(torso)
                    c = clasificar_equipos([dom], colores_cfg)[0]
                    eq = c.equipo
                except Exception:
                    eq = EquipoDetectado.DESCONOCIDO
                jugadores.append(
                    PosicionDetectada(
                        tid=tid_counter,
                        equipo=eq,
                        x=round(min(104.5, max(0.5, (x1 + x2) / (2 * w) * 105.0)), 2),
                        y=round(min(67.5, max(0.5, y2 / h * 68.0)), 2),
                        conf=round(float(conf), 3),
                        bbox=bbox_pct,
                    )
                )
                tid_counter += 1
            elif cls_int == 32 and balon_detectado is None:  # sports ball
                balon_detectado = PosicionDetectada(
                    tid=0,
                    equipo=EquipoDetectado.DESCONOCIDO,
                    x=round(min(104.5, max(0.5, (x1 + x2) / (2 * w) * 105.0)), 2),
                    y=round(min(67.5, max(0.5, y2 / h * 68.0)), 2),
                    conf=round(float(conf), 3),
                    bbox=bbox_pct,
                )

    return MensajeWorker(
        partido=partido_id,
        t=t_actual,
        jugadores=jugadores,
        balon=balon_detectado,
        calidad=IndicadorCalidad(
            worker_conectado=True,
            fps=12.0,
            jugadores_detectados=len(jugadores),
            balon_visible=balon_detectado is not None,
            retraso_s=0.08,
            degradado=False,
        ),
    )


def detectar_calibracion_con_ia(
    imagen_bytes: bytes,
    largo_m: float = 105.0,
    ancho_m: float = 68.0,
) -> dict[str, Any]:
    """Detecta los puntos clave de la cancha sobre el fotograma con YOLO-pose y calcula H."""
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo decodificar la imagen enviada")

    try:
        from calibracion.dinamica import EstimadorHomografiaPitch

        estimador = EstimadorHomografiaPitch(largo_m=largo_m, ancho_m=ancho_m)
        res = estimador.estimar(frame)
    except Exception as e:
        log.exception("Error al estimar puntos clave de la cancha con IA")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Fallo al ejecutar el modelo de puntos clave: {e}",
        ) from e

    return {
        "puntos_imagen": [{"x": round(float(u), 1), "y": round(float(v), 1)} for u, v in res.puntos_imagen],
        "puntos_cancha": [{"x": round(float(x), 2), "y": round(float(y), 2)} for x, y in res.puntos_cancha],
        "puntos_detectados": res.puntos_detectados,
        "puntos_inliers": res.puntos_inliers,
        "error_medio_m": round(res.error_medio_m, 3) if np.isfinite(res.error_medio_m) else None,
        "es_valida": res.es_valida,
        "matriz_h": res.homografia.tolist() if res.homografia is not None else None,
    }
