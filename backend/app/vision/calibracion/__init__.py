"""Calibración intrínseca y corrección de la distorsión del lente  —  T-036 (CU-23).

Módulo independiente: no tiene modelos, tablas ni endpoints. La integración con
la homografía (T-029) está descrita en README.md de esta carpeta.
"""

from app.vision.calibracion.distorsion import (
    MIN_IMAGENES,
    PATRON_POR_DEFECTO,
    CalibracionInsuficiente,
    CalibracionIntrinseca,
    MapaCorreccion,
    calibrar,
    corregir_imagen,
    corregir_puntos,
    detectar_esquinas,
    precalcular_mapa,
)

__all__ = [
    "MIN_IMAGENES",
    "PATRON_POR_DEFECTO",
    "CalibracionInsuficiente",
    "CalibracionIntrinseca",
    "MapaCorreccion",
    "calibrar",
    "corregir_imagen",
    "corregir_puntos",
    "detectar_esquinas",
    "precalcular_mapa",
]
