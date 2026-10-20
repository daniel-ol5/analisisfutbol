"""Corrección de la distorsión del lente  —  T-036 (CU-23).

Funciones puras, sin base de datos ni HTTP:

1. `calibrar(imagenes)`: calibración intrínseca con un patrón de ajedrez.
   Se hace UNA vez por cámara y lente (no por partido).
2. `precalcular_mapa(calibracion)`: el mapa de corrección píxel a píxel. Es lo
   caro; se calcula una vez y se reutiliza en cada fotograma.
3. `corregir_imagen(imagen, mapa)`: un `remap` por fotograma (barato).
4. `corregir_puntos(puntos, calibracion, mapa)`: corrige solo coordenadas, sin
   tocar la imagen. Es lo que necesita la homografía (T-029): los puntos de
   los jugadores, y los que se marcan para calibrar la cancha.

Por qué importa: con un gran angular o una action cam, una línea recta de la
cancha sale curva cerca de los bordes. La homografía supone rectas, así que un
jugador cerca de la banda queda a varios metros de donde está. Corrigiendo
antes, el error en el borde es comparable al del centro.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

# Esquinas INTERIORES del patrón (columnas, filas): un tablero de 10x7 casillas
PATRON_POR_DEFECTO = (9, 6)
MIN_IMAGENES = 5   # con menos, la estimación de k1..k3 es inestable

_CRITERIO_SUBPIXEL = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)


class CalibracionInsuficiente(ValueError):
    """No se detectó el patrón en suficientes imágenes."""


@dataclass(frozen=True)
class CalibracionIntrinseca:
    """Parámetros propios de la cámara y el lente. No dependen de la cancha."""

    matriz_camara: np.ndarray        # K, 3x3, en píxeles
    coef_distorsion: np.ndarray      # (k1, k2, p1, p2, k3)
    tamano_imagen: tuple[int, int]   # (ancho, alto) en píxeles
    error_reproyeccion_px: float     # RMS: < 0,5 px es una buena calibración
    imagenes_usadas: int

    def a_dict(self) -> dict[str, Any]:
        """Serializable a JSON, para guardarlo junto a la calibración (T-028)."""
        return {
            "matriz_camara": self.matriz_camara.tolist(),
            "coef_distorsion": self.coef_distorsion.ravel().tolist(),
            "tamano_imagen": list(self.tamano_imagen),
            "error_reproyeccion_px": self.error_reproyeccion_px,
            "imagenes_usadas": self.imagenes_usadas,
        }

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "CalibracionIntrinseca":
        return cls(
            matriz_camara=np.asarray(datos["matriz_camara"], dtype=np.float64),
            coef_distorsion=np.asarray(datos["coef_distorsion"], dtype=np.float64),
            tamano_imagen=(int(datos["tamano_imagen"][0]), int(datos["tamano_imagen"][1])),
            error_reproyeccion_px=float(datos["error_reproyeccion_px"]),
            imagenes_usadas=int(datos["imagenes_usadas"]),
        )


@dataclass(frozen=True)
class MapaCorreccion:
    """Mapa precalculado para `cv2.remap`, y la matriz de la imagen corregida."""

    mapa1: np.ndarray
    mapa2: np.ndarray
    matriz_nueva: np.ndarray         # K' de la imagen ya corregida
    tamano_imagen: tuple[int, int]


# ---------------- 1. Calibrar ----------------

def detectar_esquinas(imagen: np.ndarray,
                      patron: tuple[int, int] = PATRON_POR_DEFECTO) -> np.ndarray | None:
    """Esquinas del ajedrez con precisión subpíxel, o None si no se ve entero."""
    gris = imagen if imagen.ndim == 2 else cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    encontrado, esquinas = cv2.findChessboardCorners(
        gris, patron, flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not encontrado:
        return None
    return cv2.cornerSubPix(gris, esquinas, (5, 5), (-1, -1), _CRITERIO_SUBPIXEL)


def calibrar(imagenes: Iterable[np.ndarray],
             patron: tuple[int, int] = PATRON_POR_DEFECTO,
             tamano_casilla: float = 1.0) -> CalibracionIntrinseca:
    """Calibración intrínseca a partir de fotos del patrón de ajedrez.

    Conviene unas 15 fotos, con el tablero en distintas inclinaciones y
    **llegando a los bordes y esquinas del cuadro**: es justo ahí donde la
    distorsión es mayor. `tamano_casilla` solo escala la posición del tablero;
    K y los coeficientes no dependen de él.
    """
    objeto = np.zeros((patron[0] * patron[1], 3), np.float32)
    objeto[:, :2] = np.mgrid[0:patron[0], 0:patron[1]].T.reshape(-1, 2) * tamano_casilla

    puntos_objeto, puntos_imagen = [], []
    tamano: tuple[int, int] | None = None
    for imagen in imagenes:
        alto, ancho = imagen.shape[:2]
        if tamano is None:
            tamano = (ancho, alto)
        elif tamano != (ancho, alto):
            raise ValueError(f"Todas las imágenes deben medir {tamano}, no {(ancho, alto)}")
        esquinas = detectar_esquinas(imagen, patron)
        if esquinas is not None:
            puntos_objeto.append(objeto)
            puntos_imagen.append(esquinas)

    if tamano is None or len(puntos_imagen) < MIN_IMAGENES:
        raise CalibracionInsuficiente(
            f"Se detectó el patrón en {len(puntos_imagen)} imágenes; hacen falta {MIN_IMAGENES}")

    rms, matriz, coef, _, _ = cv2.calibrateCamera(puntos_objeto, puntos_imagen, tamano, None, None)
    return CalibracionIntrinseca(matriz, coef.ravel(), tamano, float(rms), len(puntos_imagen))


# ---------------- 2. Precalcular el mapa ----------------

def precalcular_mapa(calibracion: CalibracionIntrinseca, alfa: float = 0.0) -> MapaCorreccion:
    """Mapa de corrección para todo el cuadro. Se calcula una vez por cámara.

    `alfa` = 0 recorta los bordes negros que deja la corrección; 1 conserva
    todos los píxeles originales (con bordes negros). Para la cancha conviene 0
    salvo que se pierda una banda.
    """
    tamano = calibracion.tamano_imagen
    nueva, _ = cv2.getOptimalNewCameraMatrix(
        calibracion.matriz_camara, calibracion.coef_distorsion, tamano, alfa, tamano)
    mapa1, mapa2 = cv2.initUndistortRectifyMap(
        calibracion.matriz_camara, calibracion.coef_distorsion, None, nueva, tamano, cv2.CV_16SC2)
    return MapaCorreccion(mapa1, mapa2, nueva, tamano)


# ---------------- 3 y 4. Corregir ----------------

def corregir_imagen(imagen: np.ndarray, mapa: MapaCorreccion) -> np.ndarray:
    """Imagen sin distorsión. Barato: solo un `remap` con el mapa precalculado."""
    alto, ancho = imagen.shape[:2]
    if (ancho, alto) != mapa.tamano_imagen:
        raise ValueError(f"El mapa es para {mapa.tamano_imagen}, la imagen mide {(ancho, alto)}")
    return cv2.remap(imagen, mapa.mapa1, mapa.mapa2, cv2.INTER_LINEAR)


def corregir_puntos(puntos: Sequence[Sequence[float]] | np.ndarray,
                    calibracion: CalibracionIntrinseca,
                    mapa: MapaCorreccion) -> np.ndarray:
    """Lleva puntos de la imagen ORIGINAL a la imagen CORREGIDA.

    Entra una lista de (x, y) en píxeles del cuadro de la cámara; sale un array
    Nx2 en píxeles de la imagen corregida (la de `corregir_imagen`, con la
    matriz `mapa.matriz_nueva`). Es exacto, no pasa por el mapa de píxeles.
    """
    pts = np.asarray(puntos, dtype=np.float64).reshape(-1, 1, 2)
    if pts.size == 0:
        return np.empty((0, 2))
    corregidos = invertir_distorsion(pts, calibracion.matriz_camara, calibracion.coef_distorsion,
                                     mapa.matriz_nueva)
    return corregidos.reshape(-1, 2)


# La inversión del modelo del lente es iterativa. Con las iteraciones por
# defecto queda imprecisa justo en los bordes de un gran angular, que es lo
# que se quiere corregir: se pide convergencia fina.
_CRITERIO_INVERSION = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 100, 1e-10)


def invertir_distorsion(puntos: np.ndarray, matriz: np.ndarray, coef: np.ndarray,
                        matriz_salida: np.ndarray | None = None) -> np.ndarray:
    """`undistortPoints` con convergencia fina, en OpenCV 4.x y 5.x.

    OpenCV 4 lo ofrece como `undistortPointsIter`; OpenCV 5 lo quitó y
    `undistortPoints` acepta el criterio directamente.
    """
    if hasattr(cv2, "undistortPointsIter"):
        return cv2.undistortPointsIter(puntos, matriz, coef, None, matriz_salida,
                                       _CRITERIO_INVERSION)
    return cv2.undistortPoints(puntos, matriz, coef, P=matriz_salida,
                               criteria=_CRITERIO_INVERSION)
