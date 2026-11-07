"""Pruebas de CU-26 (proyeccion a metros) con una camara sintetica: la misma
cancha de 105 x 68 vista desde la tribuna que en
`backend/tests/test_vision_distorsion.py`, pero sin distorsion de lente (esa
correccion es CU-23 y ya se resolvio antes de que estos datos lleguen aqui).

Criterio de aceptacion de CU-26: un cono en el punto de penal se reporta a
menos de 1,5 m de su posicion real.
"""

import cv2
import numpy as np
import pytest

from calibracion.homografia import (
    HomografiaInvalida,
    cargar_homografia,
    proyectar_detecciones,
    proyectar_puntos,
)
from seguimiento.tipos import Clase, Deteccion

LARGO_M, ANCHO_M = 105.0, 68.0
K = np.array([[900.0, 0, 640.0], [0, 900.0, 360.0], [0, 0, 1]])


def _camara_tribuna():
    """Camara fija a 20 m de altura y 45 m de la banda, mirando el centro."""
    pos = np.array([LARGO_M / 2, -45.0, 20.0])
    objetivo = np.array([LARGO_M / 2, ANCHO_M / 2 - 4, 0.0])
    z = objetivo - pos
    z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    r = np.vstack([x, y, z])
    rvec, _ = cv2.Rodrigues(r)
    return rvec, -r @ pos


def _a_pixeles(puntos_m: np.ndarray, altura: float = 0.0) -> np.ndarray:
    """Proyecta puntos de la cancha (x, y) a pixeles, a una altura `z` dada."""
    rvec, tvec = _camara_tribuna()
    objeto = np.column_stack([puntos_m, np.full(len(puntos_m), altura)])
    px, _ = cv2.projectPoints(objeto, rvec, tvec, K, np.zeros(5))
    return px.reshape(-1, 2)


# Lo que se marcaria a mano para calibrar: esquinas, mitad de cancha y areas grandes
MARCAS_M = np.array([
    [0, 0], [LARGO_M, 0], [LARGO_M, ANCHO_M], [0, ANCHO_M],
    [LARGO_M / 2, 0], [LARGO_M / 2, ANCHO_M], [LARGO_M / 2, ANCHO_M / 2],
    [16.5, 13.84], [16.5, 54.16], [LARGO_M - 16.5, 13.84], [LARGO_M - 16.5, 54.16],
])

PENALES_M = np.array([[11.0, ANCHO_M / 2], [LARGO_M - 11.0, ANCHO_M / 2]])


@pytest.fixture(scope="module")
def homografia() -> np.ndarray:
    """La matriz que CU-19/20/21 (backend) entregaria ya calibrada."""
    h, _ = cv2.findHomography(_a_pixeles(MARCAS_M), MARCAS_M)
    return cargar_homografia(h.tolist())


# ---------------- cargar_homografia ----------------

def test_cargar_homografia_rechaza_forma_invalida():
    with pytest.raises(HomografiaInvalida):
        cargar_homografia([[1, 0], [0, 1]])


def test_cargar_homografia_rechaza_singular():
    with pytest.raises(HomografiaInvalida):
        cargar_homografia(np.zeros((3, 3)))


def test_cargar_homografia_rechaza_no_finitos():
    matriz = np.eye(3)
    matriz[0, 0] = np.nan
    with pytest.raises(HomografiaInvalida):
        cargar_homografia(matriz)


def test_cargar_homografia_acepta_identidad():
    homog = cargar_homografia(np.eye(3))
    np.testing.assert_allclose(homog, np.eye(3))


# ---------------- proyectar_puntos ----------------

def test_proyectar_puntos_vacio_no_falla(homografia):
    assert proyectar_puntos([], homografia).shape == (0, 2)


def test_punto_de_penal_queda_a_menos_de_1_5_metros(homografia):
    """Criterio de aceptacion de CU-26."""
    estimados = proyectar_puntos(_a_pixeles(PENALES_M), homografia)
    error = np.linalg.norm(estimados - PENALES_M, axis=1)
    assert error.max() < 1.5, f"error de {error.max():.2f} m en el punto de penal"


def test_usar_el_centro_de_la_caja_en_vez_del_pie_degrada_la_precision(homografia):
    """Documenta por que CU-26 exige el punto de apoyo: el centro de la caja
    esta a media altura del jugador, no en el piso (z=0), y la homografia
    solo es exacta para puntos del plano del suelo."""
    jugadores_m = np.array([[20.0, 10.0], [85.0, 55.0], [50.0, 60.0]])
    altura_jugador = 1.8

    pies_px = _a_pixeles(jugadores_m, altura=0.0)
    centros_px = _a_pixeles(jugadores_m, altura=altura_jugador / 2)

    error_pie = np.linalg.norm(proyectar_puntos(pies_px, homografia) - jugadores_m, axis=1)
    error_centro = np.linalg.norm(proyectar_puntos(centros_px, homografia) - jugadores_m, axis=1)

    assert error_pie.max() < 0.05, f"el pie deberia ser casi exacto: {error_pie.max():.2f} m"
    assert error_centro.max() > 1.0, f"el centro deberia fallar bastante: {error_centro.max():.2f} m"


# ---------------- proyectar_detecciones ----------------

def test_proyectar_detecciones_usa_el_punto_de_apoyo(homografia):
    caja = (100.0, 100.0, 120.0, 200.0)  # x1, y1, x2, y2 en pixeles
    deteccion = Deteccion.desde_caja(tid=1, clase=Clase.JUGADOR, caja=caja, conf=0.9)

    resultado = proyectar_detecciones([deteccion], homografia)

    assert len(resultado) == 1
    d, posicion_m = resultado[0]
    assert d is deteccion
    esperado = proyectar_puntos([deteccion.punto_apoyo], homografia)[0]
    assert posicion_m == pytest.approx(tuple(esperado))


def test_proyectar_detecciones_vacio(homografia):
    assert proyectar_detecciones([], homografia) == []
