"""Cuadros del video con sus detecciones trackeadas  —  CU-27 (T-061).

`seguimiento.tracker.seguir` entrega solo las detecciones; para el color de
camiseta (CU-25) también hace falta la imagen del cuadro. Este generador es el
mismo `modelo.track(...)` de `seguir`, pero devuelve el par (cuadro, detecciones).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from seguimiento.tipos import Deteccion
from seguimiento.tracker import _adaptar

if TYPE_CHECKING:
    from deteccion.modelo import ModeloDeteccion


def seguir_con_cuadros(
    modelo: ModeloDeteccion, ruta: str | Path, vid_stride: int = 6
) -> Iterator[tuple[np.ndarray, list[Deteccion]]]:
    """Un par (cuadro BGR, detecciones) por cada `vid_stride` cuadros del video."""
    resultados = modelo.modelo.track(
        source=str(ruta),
        tracker="bytetrack.yaml",
        vid_stride=vid_stride,
        stream=True,
        persist=True,
        verbose=False,
    )
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
