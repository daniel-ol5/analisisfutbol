"""Cuadros del video con sus detecciones trackeadas  —  CU-27 (T-061).

`seguimiento.tracker.seguir` entrega solo las detecciones; para el color de
camiseta (CU-25) también hace falta la imagen del cuadro. Este generador es el
mismo `modelo.track(...)` de `seguir`, pero devuelve el par (cuadro, detecciones).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
from seguimiento.tipos import Deteccion
from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar

if TYPE_CHECKING:
    from deteccion.modelo import ModeloDeteccion


@dataclass(frozen=True, slots=True)
class CuadroProcesado:
    imagen: np.ndarray
    detecciones: list[Deteccion]
    t: float
    indice: int


def seguir_con_cuadros(
    modelo: ModeloDeteccion,
    ruta: str | Path,
    vid_stride: int = 6,
    tracker_config: str | Path | None = None,
    indices_incluir: set[int] | None = None,
) -> Iterator[CuadroProcesado]:
    """Lee PTS del decodificador; el stride nunca cambia el reloj del video.

    El seguimiento conserva estado en todos los cuadros seleccionados. La
    frecuencia de envío se decide después, independientemente de la inferencia.
    """
    if vid_stride < 1:
        raise ValueError("El salto de cuadros debe ser positivo")
    tracker_path = str(tracker_config or (_CONFIG_TRACKER_DEFECTO if _CONFIG_TRACKER_DEFECTO.exists() else "bytetrack.yaml"))
    dispositivo = modelo.dispositivo_efectivo() if hasattr(modelo, "dispositivo_efectivo") else modelo.config.dispositivo
    kwargs: dict[str, Any] = {
        "tracker": tracker_path,
        "conf": modelo.config.confianza_min,
        "iou": modelo.config.iou_nms,
        "device": dispositivo,
        "persist": True,
        "verbose": False,
    }
    if hasattr(modelo.config, "tamano_img") and modelo.config.tamano_img:
        kwargs["imgsz"] = modelo.config.tamano_img

    captura = cv2.VideoCapture(str(ruta))
    try:
        if not captura.isOpened():
            raise ValueError(f"No se pudo abrir la fuente: {ruta}")
        fps = captura.get(cv2.CAP_PROP_FPS)
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("La fuente no informa FPS válidos")
        indice = 0
        anterior_t = -1.0
        while True:
            ok, imagen = captura.read()
            if not ok:
                break
            if indice % vid_stride == 0 or indice in (indices_incluir or set()):
                t = captura.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if not np.isfinite(t) or t < 0 or t <= anterior_t:
                    t = max(indice / fps, anterior_t + vid_stride / fps)
                anterior_t = t
                resultado = modelo.modelo.track(imagen, **kwargs)[0]
                yield CuadroProcesado(imagen, _adaptar(resultado, modelo.config), t, indice)
            indice += 1
    finally:
        captura.release()


def datos_del_video(ruta: str | Path) -> tuple[float, int]:
    """fps y cantidad de cuadros, para calcular el tiempo y el progreso."""
    captura = cv2.VideoCapture(str(ruta))
    try:
        fps = captura.get(cv2.CAP_PROP_FPS) or 0.0
        cuadros = int(captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        captura.release()
    return fps, cuadros
