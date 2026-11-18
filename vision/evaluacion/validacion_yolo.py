"""Compara detectores con las mismas imágenes y etiquetas de validación YOLO."""

from __future__ import annotations

from pathlib import Path

from deteccion.modelo import ModeloDeteccion
from seguimiento.tipos import Clase, Deteccion

from .mapa import EvaluacionInvalida, calcular_map50


def validar(
    modelo: ModeloDeteccion,
    imagenes: list[Path],
    etiquetas: Path,
    clases_etiquetas: dict[int, Clase],
) -> dict[str, float | None]:
    """AP50 por clase, antes del tracker. La clase ausente queda sin valor."""
    if not imagenes:
        raise ValueError("La validación requiere al menos una imagen anotada")

    config = modelo.config
    resultados = (
        resultado
        for inicio in range(0, len(imagenes), 4)
        for resultado in modelo.modelo.predict(
            [str(imagen) for imagen in imagenes[inicio:inicio + 4]],
            stream=True, imgsz=config.tamano_img,
            device=modelo.dispositivo_efectivo(),
            conf=0.001, iou=config.iou_nms, classes=list(config.clases), verbose=False,
        )
    )
    verdad = []
    detectadas = []
    for imagen, resultado in zip(imagenes, resultados, strict=True):
        alto, ancho = resultado.orig_shape
        anotadas = []
        etiqueta = etiquetas / f"{imagen.stem}.txt"
        for i, linea in enumerate(etiqueta.read_text(encoding="utf-8").splitlines()):
            if not linea.strip():
                continue
            clase_id, centro_x, centro_y, largo, altura = linea.split()
            x, y, w, h = map(float, (centro_x, centro_y, largo, altura))
            caja = ((x - w / 2) * ancho, (y - h / 2) * alto,
                    (x + w / 2) * ancho, (y + h / 2) * alto)
            anotadas.append(Deteccion.desde_caja(i, clases_etiquetas[int(clase_id)], caja, 1.0))
        verdad.append(anotadas)

        cajas = resultado.boxes
        detectadas.append([
            Deteccion.desde_caja(i, config.clases[int(clase_id)], tuple(caja), conf)
            for i, (clase_id, caja, conf) in enumerate(
                zip(cajas.cls.tolist(), cajas.xyxy.tolist(), cajas.conf.tolist(), strict=True)
            )
        ])

    metricas = {}
    for clase in dict.fromkeys(clases_etiquetas.values()):
        try:
            ap50 = calcular_map50(detectadas, verdad, clase) if clase in config.clases.values() else None
        except EvaluacionInvalida:
            ap50 = None
        metricas[clase.value.lower()] = None if ap50 is None else round(ap50, 4)
    return metricas
