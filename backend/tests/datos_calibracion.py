"""Datos sintéticos de calibración, compartidos por los tests de homografía y de endpoints.

Se parte de una homografía CONOCIDA de metros a píxeles (una cámara en la
tribuna, con perspectiva) y se proyectan marcas repartidas por la cancha. Así el
resultado correcto es exacto y no depende del propio código bajo prueba.
Solo numpy: no hay base de datos ni cv2.
"""

import numpy as np

# Metros -> píxeles. Última fila con perspectiva: w = 0.0002 x + 0.012 y + 1 (siempre > 0).
H_METROS_A_PIXELES = np.array([
    [16.0, 3.0, 160.0],
    [0.5, 6.0, 180.0],
    [0.0002, 0.012, 1.0],
])


def marcas_cancha(largo: float = 105.0, ancho: float = 68.0) -> np.ndarray:
    """12 marcas bien repartidas: esquinas, medio campo, centro y áreas (en metros)."""
    fx, fy = largo / 105.0, ancho / 68.0
    base = [
        (0, 0), (105, 0), (105, 68), (0, 68),
        (52.5, 0), (52.5, 68), (52.5, 34),
        (16.5, 13.85), (16.5, 54.15), (88.5, 13.85), (88.5, 54.15),
        (105, 34),
    ]
    return np.array([(x * fx, y * fy) for x, y in base], dtype=float)


def a_pixeles(metros: np.ndarray) -> np.ndarray:
    h = np.column_stack([metros, np.ones(len(metros))]) @ H_METROS_A_PIXELES.T
    return h[:, :2] / h[:, 2:3]


def a_metros(pixeles: np.ndarray) -> np.ndarray:
    h = np.column_stack([pixeles, np.ones(len(pixeles))]) @ np.linalg.inv(H_METROS_A_PIXELES).T
    return h[:, :2] / h[:, 2:3]


def a_json(puntos: np.ndarray) -> list[dict[str, float]]:
    return [{"x": float(x), "y": float(y)} for x, y in puntos]


def cuerpo_valido(largo: float = 105.0, ancho: float = 68.0, **cambios) -> dict:
    """Cuerpo de POST con homografía exacta (error ~0)."""
    cancha = marcas_cancha(largo, ancho)
    cuerpo = {
        "puntos_imagen": a_json(a_pixeles(cancha)),
        "puntos_cancha": a_json(cancha),
        "largo_m": largo,
        "ancho_m": ancho,
    }
    cuerpo.update(cambios)
    return cuerpo
