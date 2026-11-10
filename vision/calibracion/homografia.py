"""Proyeccion de pixeles a metros con una homografia ya calibrada  —  CU-26.

La calibracion de la homografia (marcar puntos conocidos de la cancha y
resolver la matriz 3x3) es responsabilidad de CU-19/20/21 (backend, Jhon):
ese flujo todavia esta pendiente (`backend/app/vision/router.py` solo tiene
los stubs, y `backend/app/vision/schemas.py` ya define el contrato
`Calibracion.matriz_h` que se recibe aqui). Este modulo solo *aplica* una
matriz ya calculada para convertir el punto de apoyo de cada jugador
(pixeles) a coordenadas reales de la cancha (metros).

Se usa siempre el punto de apoyo (el pie, `Deteccion.punto_apoyo`), nunca el
centro de la caja: la homografia asume que el punto proyectado esta en el
plano del suelo (z=0). El centro de la caja esta a la altura media del
jugador, no en el piso, y ese error crece con la altura del jugador y con la
distancia/angulo de la camara (ver `vision/tests/test_homografia.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from seguimiento.tipos import Deteccion


class HomografiaInvalida(ValueError):
    """La matriz no es una homografia 3x3 utilizable."""


def cargar_homografia(matriz_h: Sequence[Sequence[float]]) -> np.ndarray:
    """Valida y devuelve la matriz 3x3 como `np.ndarray` de float64.

    `matriz_h` llega tal cual la entrega el backend (lista de listas, desde
    JSON): aqui se valida la forma, que no tenga NaN/inf y que no sea
    singular (no invertible) antes de usarla cuadro a cuadro.
    """
    homografia = np.asarray(matriz_h, dtype=np.float64)
    if homografia.shape != (3, 3):
        raise HomografiaInvalida(f"Se esperaba una matriz 3x3, se recibio {homografia.shape}")
    if not np.isfinite(homografia).all():
        raise HomografiaInvalida("La matriz tiene valores no finitos (NaN/inf)")
    if abs(np.linalg.det(homografia)) < 1e-12:
        raise HomografiaInvalida("La matriz es singular: no se puede proyectar con ella")
    return homografia


def proyectar_puntos(
    puntos_px: Sequence[tuple[float, float]], homografia: np.ndarray
) -> np.ndarray:
    """Proyecta puntos en pixeles a metros de cancha con `cv2.perspectiveTransform`.

    Devuelve un array `(n, 2)`; vacio si `puntos_px` esta vacio (evita el
    error que lanza OpenCV al recibir un array de entrada vacio).
    """
    if len(puntos_px) == 0:
        return np.empty((0, 2), dtype=np.float64)
    entrada = np.asarray(puntos_px, dtype=np.float64).reshape(-1, 1, 2)
    salida = cv2.perspectiveTransform(entrada, homografia)
    return salida.reshape(-1, 2)


def proyectar_detecciones(
    detecciones: Sequence[Deteccion], homografia: np.ndarray
) -> list[tuple[Deteccion, tuple[float, float]]]:
    """Empareja cada deteccion con su posicion en metros (punto de apoyo proyectado).

    Nunca el centro de la caja: ver el docstring del modulo para el porque.
    """
    if not detecciones:
        return []
    puntos = [d.punto_apoyo for d in detecciones]
    proyectados = proyectar_puntos(puntos, homografia)
    return list(zip(detecciones, (tuple(p) for p in proyectados), strict=True))


def actualizar_homografia_dinamica(
    homografia_referencia: np.ndarray, matriz_camara_acumulada_3x3: np.ndarray
) -> np.ndarray:
    """Ajusta la homografía de referencia según el paneo acumulado de la cámara:

    H_t = H_0 * T_cam^{-1}

    Permite que la proyección a metros del radar 2D siga siendo exacta cuando
    la cámara táctica se desplaza horizontal o verticalmente para seguir la jugada.
    """
    if matriz_camara_acumulada_3x3 is None or matriz_camara_acumulada_3x3.shape != (3, 3):
        return homografia_referencia.copy()

    try:
        t_inv = np.linalg.inv(matriz_camara_acumulada_3x3)
        return homografia_referencia @ t_inv
    except (np.linalg.LinAlgError, ValueError):
        return homografia_referencia.copy()

