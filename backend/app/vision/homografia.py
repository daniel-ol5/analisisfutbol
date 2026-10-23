"""Homografía de la cancha y error de reproyección en metros  —  CU-21 (T-029).

Función PURA: no conoce FastAPI ni la base de datos, y usa solo numpy (nada de
cv2 en la ruta de la API). Entra la lista de puntos marcados sobre la imagen y
los mismos puntos en metros sobre el plano de la cancha; sale la matriz H 3x3
que lleva de píxeles a metros y cuánto se equivoca esa matriz sobre los propios
puntos.

Método: DLT con normalización de Hartley y ajuste por mínimos cuadrados sobre
TODOS los puntos. Se evita RANSAC a propósito: descartaría los puntos mal
marcados y el error informado dejaría de ser honesto.

TODO T-036 (Alejandra): la corrección de la distorsión del lente queda FUERA de
T-029. Los puntos de imagen entran tal cual los marcó el usuario. Cuando se
integre `app.vision.calibracion.corregir_puntos`, debe aplicarse ANTES de llamar
a `calcular_homografia` (requiere ampliar el contrato: `coef_distorsion` solo no
alcanza, falta la matriz de la cámara y el tamaño de imagen).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MIN_PUNTOS = 8

# CU-21: un error medio mayor a 2 m marca la calibración como NO válida y bloquea
# el inicio del partido. Exactamente 2,0 m todavía es válido.
UMBRAL_ERROR_MEDIO_M = 2.0

# Colinealidad: cociente entre el segundo y el primer valor singular de los
# puntos centrados, es decir, cuánto se abre la nube en su eje menor respecto del
# mayor (0 = todos sobre una recta, 1 = nube redonda).
# Cómo se eligió: con las marcas repartidas por la cancha (esquinas, área,
# círculo central) el cociente sale entre ~0,3 y ~0,7 en metros y entre ~0,1 y
# ~0,5 en la imagen, por la perspectiva. 0,05 equivale a que las marcas ocupen
# una franja de solo el 5 % de su largo (unos 5 m sobre 105 m): ahí la matriz
# ya está mal condicionada y el residual sería engañosamente bajo. Es un
# umbral heurístico por criterio de ingeniería, NO calibrado con fotos reales:
# conviene revisarlo cuando haya calibraciones de partidos verdaderos.
UMBRAL_COLINEALIDAD = 0.05

# Rangos numéricos de degeneración (en el espacio normalizado de Hartley, donde
# todo es de orden 1, por eso valen para cualquier tamaño de imagen).
_UMBRAL_RANGO_DLT = 1e-8       # 8.º valor singular del DLT relativo al mayor
_UMBRAL_SINGULAR_H = 1e-8      # valor singular menor de H relativo al mayor
_UMBRAL_W = 1e-9               # |w| de la proyección relativo al mayor


class HomografiaError(ValueError):
    """Los puntos no permiten calcular una homografía fiable. El mensaje va al usuario."""


@dataclass(frozen=True)
class ResultadoHomografia:
    matriz: list[list[float]]   # 3x3, de píxeles a metros, con matriz[2][2] = 1 si es posible
    error_medio_m: float
    error_max_m: float
    indice_peor: int            # base 0, sobre la lista de puntos recibida


def es_valida(error_medio_m: float) -> bool:
    return error_medio_m <= UMBRAL_ERROR_MEDIO_M


def _a_matriz_nx2(puntos: Sequence[Sequence[float]] | np.ndarray, nombre: str) -> np.ndarray:
    try:
        arr = np.asarray(puntos, dtype=float)
    except (TypeError, ValueError):
        raise HomografiaError(f"{nombre}: todos los puntos deben ser pares (x, y) numéricos") from None
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise HomografiaError(f"{nombre}: se esperaba una lista de pares (x, y)")
    if not np.all(np.isfinite(arr)):
        raise HomografiaError(f"{nombre}: contiene valores no finitos (NaN o infinito)")
    return arr


def _indices_repetidos(arr: np.ndarray) -> list[int]:
    """Índices (base 0) de los puntos que repiten uno anterior."""
    vistos: set[tuple[float, float]] = set()
    repetidos: list[int] = []
    for i, (x, y) in enumerate(arr):
        clave = (float(x), float(y))
        if clave in vistos:
            repetidos.append(i)
        vistos.add(clave)
    return repetidos


def _cociente_colinealidad(arr: np.ndarray) -> float:
    valores = np.linalg.svd(arr - arr.mean(axis=0), compute_uv=False)
    return 0.0 if valores[0] == 0 else float(valores[1] / valores[0])


def _normalizar(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hartley: centroide en el origen y distancia media al origen sqrt(2)."""
    centro = arr.mean(axis=0)
    dist_media = np.linalg.norm(arr - centro, axis=1).mean()
    escala = np.sqrt(2.0) / dist_media
    t = np.array([[escala, 0.0, -escala * centro[0]],
                  [0.0, escala, -escala * centro[1]],
                  [0.0, 0.0, 1.0]])
    homogeneos = np.column_stack([arr, np.ones(len(arr))])
    return (homogeneos @ t.T)[:, :2], t


def _proyectar(matriz: np.ndarray, puntos: np.ndarray) -> np.ndarray:
    homogeneos = np.column_stack([puntos, np.ones(len(puntos))]) @ matriz.T
    w = homogeneos[:, 2]
    if np.any(np.abs(w) <= _UMBRAL_W * np.abs(w).max()) or not (np.all(w > 0) or np.all(w < 0)):
        raise HomografiaError(
            "La homografía es inestable: algún punto cae sobre el horizonte o los puntos "
            "quedan a ambos lados de él. Revisa que estén bien marcados"
        )
    return homogeneos[:, :2] / w[:, None]


def calcular_homografia(
    puntos_imagen: Sequence[Sequence[float]] | np.ndarray,
    puntos_cancha: Sequence[Sequence[float]] | np.ndarray,
) -> ResultadoHomografia:
    """Ajusta H (píxeles -> metros) y mide el error de reproyección en metros.

    El error de cada punto es la distancia euclídea entre `H(punto_imagen)` y su
    `punto_cancha`. Lanza `HomografiaError` si los datos no sirven.
    """
    img = _a_matriz_nx2(puntos_imagen, "puntos_imagen")
    can = _a_matriz_nx2(puntos_cancha, "puntos_cancha")

    if len(img) != len(can):
        raise HomografiaError(
            "puntos_imagen y puntos_cancha deben tener la misma cantidad de puntos "
            f"(recibidos {len(img)} y {len(can)})"
        )
    if len(img) < MIN_PUNTOS:
        raise HomografiaError(
            f"Se necesitan al menos {MIN_PUNTOS} puntos para calibrar (recibidos {len(img)})"
        )

    for nombre, arr in (("puntos_imagen", img), ("puntos_cancha", can)):
        repetidos = _indices_repetidos(arr)
        if repetidos:
            raise HomografiaError(
                f"{nombre} tiene puntos repetidos (índices base 0: {repetidos}). "
                "Cada marca debe ser un punto distinto"
            )
        if _cociente_colinealidad(arr) < UMBRAL_COLINEALIDAD:
            raise HomografiaError(
                f"{nombre} están casi alineados sobre una recta: reparte los puntos "
                "por toda la cancha para poder calibrar"
            )

    img_n, t_img = _normalizar(img)
    can_n, t_can = _normalizar(can)

    # DLT: dos ecuaciones por punto sobre las 9 entradas de H (por filas).
    n = len(img_n)
    a = np.zeros((2 * n, 9))
    x, y = img_n[:, 0], img_n[:, 1]
    u, v = can_n[:, 0], can_n[:, 1]
    a[0::2, 0], a[0::2, 1], a[0::2, 2] = -x, -y, -1.0
    a[0::2, 6], a[0::2, 7], a[0::2, 8] = u * x, u * y, u
    a[1::2, 3], a[1::2, 4], a[1::2, 5] = -x, -y, -1.0
    a[1::2, 6], a[1::2, 7], a[1::2, 8] = v * x, v * y, v

    _, valores, vt = np.linalg.svd(a)
    if valores[7] <= _UMBRAL_RANGO_DLT * valores[0]:
        raise HomografiaError(
            "Los puntos son degenerados (por ejemplo, todos sobre dos rectas): "
            "no determinan una única homografía"
        )
    h_n = vt[-1].reshape(3, 3)
    h_n = h_n / np.linalg.norm(h_n)

    s_h = np.linalg.svd(h_n, compute_uv=False)
    if s_h[2] <= _UMBRAL_SINGULAR_H * s_h[0]:
        raise HomografiaError("La matriz de homografía es singular: revisa la marcación de los puntos")

    h = np.linalg.inv(t_can) @ h_n @ t_img
    # Si H[2][2] ~ 0 la escala por [2][2] sería inestable: se usa la norma de Frobenius.
    escala = h[2, 2] if abs(h[2, 2]) > 1e-9 * np.linalg.norm(h) else np.linalg.norm(h)
    h = h / escala

    proyectados = _proyectar(h, img)
    errores = np.linalg.norm(proyectados - can, axis=1)
    if not np.all(np.isfinite(errores)) or not np.all(np.isfinite(h)):
        raise HomografiaError("El cálculo produjo valores no finitos: revisa los puntos")

    return ResultadoHomografia(
        matriz=[[float(c) for c in fila] for fila in h],
        error_medio_m=float(errores.mean()),
        error_max_m=float(errores.max()),
        indice_peor=int(errores.argmax()),
    )
