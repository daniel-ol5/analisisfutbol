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
from seguimiento.tipos import Clase, Deteccion
from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar, _tamano_balon_valido

if TYPE_CHECKING:
    from deteccion.modelo import ModeloDeteccion


@dataclass(frozen=True, slots=True)
class CuadroProcesado:
    imagen: np.ndarray
    detecciones: list[Deteccion]
    t: float
    indice: int


def _buscar_balon_en_zoom(
    modelo: ModeloDeteccion,
    imagen: np.ndarray,
    centro: tuple[float, float],
    dispositivo: str,
    lado_roi: int = 640,
) -> list[Deteccion]:
    """Segundo pase a resolución nativa 1:1 alrededor de la última posición del balón.

    Recupera balones pequeños o parcialmente ocluidos en los pies del jugador sin
    alterar el estado del tracker de personas (usa `predict`, no `track`).
    """
    predictor = getattr(modelo.modelo, "predict", None)
    if predictor is None or not isinstance(imagen, np.ndarray) or imagen.size == 0:
        return []
    alto, ancho = imagen.shape[:2]
    if ancho <= lado_roi and alto <= lado_roi:
        return []

    mitad = lado_roi // 2
    cx, cy = centro
    x1 = max(0, min(ancho - lado_roi, int(cx - mitad)))
    y1 = max(0, min(alto - lado_roi, int(cy - mitad)))
    x2 = min(ancho, x1 + lado_roi)
    y2 = min(alto, y1 + lado_roi)
    recorte = imagen[y1:y2, x1:x2]
    if recorte.size == 0:
        return []

    try:
        res_lista = predictor(
            recorte,
            imgsz=lado_roi,
            conf=modelo.config.confianza_min,
            iou=modelo.config.iou_nms,
            device=dispositivo,
            verbose=False,
        )
    except Exception:
        return []
    if not res_lista:
        return []
    cajas = getattr(res_lista[0], "boxes", None)
    if cajas is None or getattr(cajas, "xyxy", None) is None:
        return []

    encontrados: list[Deteccion] = []
    for k, (caja, clase_id, conf) in enumerate(
        zip(cajas.xyxy.tolist(), cajas.cls.tolist(), cajas.conf.tolist(), strict=True), start=1
    ):
        if modelo.config.clases.get(int(clase_id)) != Clase.BALON or conf < modelo.config.confianza_min:
            continue
        bx1, by1, bx2, by2 = caja
        if _tamano_balon_valido(bx2 - bx1, by2 - by1):
            encontrados.append(
                Deteccion.desde_caja(
                    -100 - k,
                    Clase.BALON,
                    (bx1 + x1, by1 + y1, bx2 + x1, by2 + y1),
                    float(conf),
                )
            )
    return encontrados


def seguir_con_cuadros(
    modelo: ModeloDeteccion,
    ruta: str | Path,
    vid_stride: int = 6,
    tracker_config: str | Path | None = None,
    indices_incluir: set[int] | None = None,
    habilitar_zoom_balon: bool = True,
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
        ultima_pos_balon: tuple[float, float] | None = None
        cuadros_sin_balon = 0
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
                detecciones = _adaptar(resultado, modelo.config)
                balones = [d for d in detecciones if d.clase == Clase.BALON]
                if not balones and habilitar_zoom_balon and ultima_pos_balon is not None and cuadros_sin_balon < 12:
                    balones_zoom = _buscar_balon_en_zoom(modelo, imagen, ultima_pos_balon, dispositivo)
                    if balones_zoom:
                        detecciones.extend(balones_zoom)
                        balones = balones_zoom
                if balones:
                    mejor = max(balones, key=lambda d: d.conf)
                    bx1, by1, bx2, by2 = mejor.caja
                    ultima_pos_balon = ((bx1 + bx2) / 2.0, (by1 + by2) / 2.0)
                    cuadros_sin_balon = 0
                else:
                    cuadros_sin_balon += 1
                yield CuadroProcesado(imagen, detecciones, t, indice)
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
