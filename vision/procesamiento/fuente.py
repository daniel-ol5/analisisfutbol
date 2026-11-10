"""Cuadros del video con sus detecciones trackeadas  —  CU-27 (T-061).

`seguimiento.tracker.seguir` entrega solo las detecciones; para el color de
camiseta (CU-25) también hace falta la imagen del cuadro. Este generador es el
mismo `modelo.track(...)` de `seguir`, pero devuelve el par (cuadro, detecciones).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from seguimiento.tipos import Deteccion
from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar

if TYPE_CHECKING:
    from deteccion.modelo import ModeloDeteccion


def seguir_con_cuadros(
    modelo: ModeloDeteccion,
    ruta: str | Path,
    vid_stride: int = 6,
    tracker_config: str | Path | None = None,
) -> Iterator[tuple[np.ndarray, list[Deteccion]]]:
    """Un par (cuadro BGR, detecciones) por cada `vid_stride` cuadros del video."""
    tracker_path = str(tracker_config or (_CONFIG_TRACKER_DEFECTO if _CONFIG_TRACKER_DEFECTO.exists() else "bytetrack.yaml"))
    dispositivo = modelo.dispositivo_efectivo() if hasattr(modelo, "dispositivo_efectivo") else modelo.config.dispositivo
    kwargs: dict[str, Any] = {
        "source": str(ruta),
        "tracker": tracker_path,
        "vid_stride": vid_stride,
        "conf": modelo.config.confianza_min,
        "iou": modelo.config.iou_nms,
        "device": dispositivo,
        "stream": True,
        "persist": True,
        "verbose": False,
    }
    if hasattr(modelo.config, "tamano_img") and modelo.config.tamano_img:
        kwargs["imgsz"] = modelo.config.tamano_img

    resultados = modelo.modelo.track(**kwargs)
    for resultado in resultados:
        yield resultado.orig_img, _adaptar(resultado, modelo.config)


def datos_del_video(ruta: str | Path) -> tuple[float, int]:
    """fps y cantidad de cuadros, para calcular el tiempo y el progreso."""
    captura = cv2.VideoCapture(str(ruta))
    try:
        fps = captura.get(cv2.CAP_PROP_FPS) or 0.0
        cuadros = int(captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        captura.release()
    return fps, cuadros
