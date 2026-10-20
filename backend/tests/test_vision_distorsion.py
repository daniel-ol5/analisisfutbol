"""Pruebas de la corrección de distorsión  —  T-036 (CU-23).

Todo es sintético: una cámara gran angular conocida (distorsión de barril),
fotos del patrón de ajedrez renderizadas desde varias poses, y una cancha de
105 x 68 vista desde la tribuna. Se calibra a partir de las fotos (sin usar los
valores verdaderos) y se compara el error antes y después de corregir.

Criterio de finalización: un punto cercano al borde tiene, después de
corregir, un error comparable al de un punto central.
"""

import functools
import math

import cv2
import numpy as np
import pytest

from app.vision.calibracion import (
    CalibracionInsuficiente,
    CalibracionIntrinseca,
    calibrar,
    corregir_imagen,
    corregir_puntos,
    detectar_esquinas,
    precalcular_mapa,
)
from app.vision.calibracion.distorsion import invertir_distorsion

# ---------------- La cámara "verdadera" ----------------

ANCHO, ALTO = 640, 480
K = np.array([[380.0, 0, 322.0], [0, 380.0, 238.0], [0, 0, 1]])
D = np.array([-0.30, 0.10, 0.0005, -0.0004, -0.015])   # barril marcado, como una action cam
PATRON = (9, 6)
CENTRO_TABLERO = np.array([4.0, 2.5, 0.0])


def _pose(ang_grados: tuple[float, float, float], centro_n: tuple[float, float], z: float):
    """Tablero con su centro sobre el rayo `centro_n` (coords. normalizadas) a profundidad z."""
    rvec = np.radians(np.array(ang_grados, dtype=np.float64))
    r, _ = cv2.Rodrigues(rvec)
    tvec = z * np.array([centro_n[0], centro_n[1], 1.0]) - r @ CENTRO_TABLERO
    return rvec, tvec


def _normalizados_de_pixeles(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Inversa exacta del modelo verdadero (iterativa, con tolerancia fina)."""
    pts = np.stack([u.ravel(), v.ravel()], axis=1).reshape(-1, 1, 2).astype(np.float64)
    return invertir_distorsion(pts, K, D).reshape(-1, 2)


SOBREMUESTREO = 3


@functools.cache
def _rayos_por_subpixel() -> np.ndarray:
    """Rayo de cada subpíxel. No depende de la pose: se calcula una sola vez."""
    s = SOBREMUESTREO
    u2, v2 = np.meshgrid(np.arange(ANCHO * s), np.arange(ALTO * s))
    return _normalizados_de_pixeles((u2 + 0.5) / s - 0.5, (v2 + 0.5) / s - 0.5)


def _renderizar_tablero(rvec, tvec) -> np.ndarray:
    """Foto del ajedrez como la vería la cámara verdadera, con bordes suavizados."""
    s = SOBREMUESTREO
    n = _rayos_por_subpixel()

    # Intersección de cada rayo con el plano del tablero (Z = 0 en su sistema)
    r, _ = cv2.Rodrigues(rvec)
    rayo = np.column_stack([n, np.ones(len(n))]) @ r          # = (R^T d)^T
    origen = r.T @ tvec
    escala = origen[2] / rayo[:, 2]
    bx = escala * rayo[:, 0] - origen[0]
    by = escala * rayo[:, 1] - origen[1]

    img = np.full(len(n), 255, np.uint8)
    dentro = (bx >= -1) & (bx < 9) & (by >= -1) & (by < 6)
    negro = ((np.floor(bx) + np.floor(by)) % 2 == 0) & dentro
    img[negro] = 20
    img[(escala <= 0) | (np.abs(bx - 4) > 7) | (np.abs(by - 2.5) > 5.5)] = 150
    img = img.reshape(ALTO * s, ANCHO * s)
    return cv2.resize(img, (ANCHO, ALTO), interpolation=cv2.INTER_AREA)


# Poses variadas: centro, bordes y esquinas, con distintas inclinaciones
POSES = [
    ((0, 0, 0), (0.0, 0.0), 11),
    ((15, -10, 5), (-0.35, -0.25), 13),
    ((-15, 10, -5), (0.35, -0.25), 13),
    ((10, 15, 3), (-0.35, 0.25), 13),
    ((-10, -15, -3), (0.35, 0.25), 13),
    ((25, 0, 0), (0.0, -0.3), 12),
    ((-25, 0, 10), (0.0, 0.3), 12),
    ((0, 25, -8), (-0.45, 0.0), 12),
    ((0, -25, 8), (0.45, 0.0), 12),
    ((20, 20, 15), (0.1, 0.05), 10),
    ((-20, -20, -15), (-0.1, -0.05), 10),
    ((5, -5, 30), (0.0, 0.0), 9),
    # Llegando a las esquinas y los bordes del cuadro: sin estas, el polinomio
    # del lente se extrapola ahí y el error en las esquinas sube a ~30 px
    ((-10, -10, 0), (-0.75, -0.5625), 15),
    ((-10, -10, 0), (0.75, -0.5625), 15),
    ((10, 10, 0), (-0.75, 0.5625), 15),
    ((10, -10, 0), (0.75, 0.5625), 15),
    ((0, 15, 0), (-0.8, 0.0), 12),
    ((0, -15, 0), (0.8, 0.0), 12),
    ((10, 0, 0), (0.0, -0.5), 15),
    ((0, 0, 0), (0.0, 0.5), 13),
]


@pytest.fixture(scope="module")
def fotos() -> list[np.ndarray]:
    return [_renderizar_tablero(*_pose(*p)) for p in POSES]


@pytest.fixture(scope="module")
def calibracion(fotos) -> CalibracionIntrinseca:
    return calibrar(fotos, PATRON)


# ---------------- Calibración ----------------

def test_se_detecta_el_patron_en_las_fotos_sinteticas(fotos):
    detectadas = sum(detectar_esquinas(f, PATRON) is not None for f in fotos)
    assert detectadas == len(fotos), f"solo {detectadas} de {len(fotos)}"


def test_recupera_los_parametros_de_la_camara(calibracion):
    assert calibracion.error_reproyeccion_px < 0.5
    assert calibracion.matriz_camara[0, 0] == pytest.approx(K[0, 0], rel=0.02)
    assert calibracion.matriz_camara[1, 1] == pytest.approx(K[1, 1], rel=0.02)
    assert calibracion.matriz_camara[0, 2] == pytest.approx(K[0, 2], abs=4)
    assert calibracion.matriz_camara[1, 2] == pytest.approx(K[1, 2], abs=4)
    assert calibracion.coef_distorsion[0] == pytest.approx(D[0], abs=0.03)   # k1 domina


def test_pocas_fotos_no_alcanzan(fotos):
    with pytest.raises(CalibracionInsuficiente):
        calibrar(fotos[:3], PATRON)
    with pytest.raises(CalibracionInsuficiente):
        calibrar([np.full((ALTO, ANCHO), 255, np.uint8)] * 8, PATRON)


def test_fotos_de_distinto_tamano_se_rechazan(fotos):
    with pytest.raises(ValueError, match="medir"):
        calibrar([*fotos[:5], np.zeros((100, 100), np.uint8)], PATRON)


def test_se_guarda_y_se_recupera_como_json(calibracion):
    import json
    vuelta = CalibracionIntrinseca.desde_dict(json.loads(json.dumps(calibracion.a_dict())))
    np.testing.assert_allclose(vuelta.matriz_camara, calibracion.matriz_camara)
    np.testing.assert_allclose(vuelta.coef_distorsion, calibracion.coef_distorsion)
    assert vuelta.tamano_imagen == (ANCHO, ALTO)


# ---------------- Criterio: el borde queda como el centro (píxeles) ----------------

def _error_px(distorsionados: np.ndarray, calibracion: CalibracionIntrinseca):
    """Error antes y después de corregir, contra la proyección ideal sin lente."""
    u, v = distorsionados[:, 0], distorsionados[:, 1]
    n = _normalizados_de_pixeles(u, v)
    homog = np.column_stack([n, np.ones(len(n))])

    ideal_sin_corregir = (homog @ K.T)[:, :2]
    antes = np.linalg.norm(distorsionados - ideal_sin_corregir, axis=1)

    mapa = precalcular_mapa(calibracion)
    ideal_corregido = homog @ mapa.matriz_nueva.T
    ideal_corregido = ideal_corregido[:, :2] / ideal_corregido[:, 2:]
    despues = np.linalg.norm(corregir_puntos(distorsionados, calibracion, mapa)
                             - ideal_corregido, axis=1)
    return antes, despues


def test_punto_del_borde_queda_con_error_comparable_al_central(calibracion):
    centro = np.array([[ANCHO / 2 + 8, ALTO / 2 - 5]])
    bordes = np.array([[25.0, ALTO / 2], [ANCHO - 25.0, ALTO / 2],
                       [ANCHO / 2, 20.0], [40.0, 35.0], [ANCHO - 40.0, ALTO - 35.0]])

    antes_c, despues_c = _error_px(centro, calibracion)
    antes_b, despues_b = _error_px(bordes, calibracion)

    # Antes: el centro casi no se deforma y el borde se va decenas de píxeles
    assert antes_c.max() < 1.0
    assert antes_b.min() > 15.0
    # Después: el borde queda a menos de 1 px, del mismo orden que el centro
    assert despues_b.max() < 1.0
    assert despues_b.max() < despues_c.max() + 0.75


# ---------------- Criterio en metros: la homografía de la cancha ----------------

LARGO_M, ANCHO_M = 105.0, 68.0


def _camara_tribuna():
    """Cámara fija a 20 m de altura y 45 m de la banda, mirando el centro."""
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


def _a_pixeles(puntos_m: np.ndarray) -> np.ndarray:
    rvec, tvec = _camara_tribuna()
    objeto = np.column_stack([puntos_m, np.zeros(len(puntos_m))])
    px, _ = cv2.projectPoints(objeto, rvec, tvec, K, D)
    return px.reshape(-1, 2)


# Lo que se marca a mano para T-028: esquinas, mitad de cancha y áreas grandes
MARCAS_M = np.array([
    [0, 0], [LARGO_M, 0], [LARGO_M, ANCHO_M], [0, ANCHO_M],
    [LARGO_M / 2, 0], [LARGO_M / 2, ANCHO_M], [LARGO_M / 2, ANCHO_M / 2],
    [16.5, 13.84], [16.5, 54.16], [LARGO_M - 16.5, 13.84], [LARGO_M - 16.5, 54.16],
])


def _error_m(jugadores_m: np.ndarray, calibracion: CalibracionIntrinseca | None) -> np.ndarray:
    """Posición en metros por homografía (como T-029) contra la verdadera."""
    marcas_px, jugadores_px = _a_pixeles(MARCAS_M), _a_pixeles(jugadores_m)
    if calibracion is not None:
        mapa = precalcular_mapa(calibracion)
        marcas_px = corregir_puntos(marcas_px, calibracion, mapa)
        jugadores_px = corregir_puntos(jugadores_px, calibracion, mapa)
    h, _ = cv2.findHomography(marcas_px, MARCAS_M)
    estimados = cv2.perspectiveTransform(jugadores_px.reshape(-1, 1, 2), h).reshape(-1, 2)
    return np.linalg.norm(estimados - jugadores_m, axis=1)


def test_la_cancha_se_ve_entera():
    px = _a_pixeles(MARCAS_M)
    assert (px[:, 0] > 0).all() and (px[:, 0] < ANCHO).all()
    assert (px[:, 1] > 0).all() and (px[:, 1] < ALTO).all()


def test_en_metros_el_jugador_de_la_banda_queda_como_el_del_centro(calibracion):
    centro = np.array([[50.0, 30.0], [58.0, 38.0]])
    borde = np.array([[6.0, 3.0], [99.0, 3.0], [8.0, 64.0], [97.0, 65.0], [52.0, 66.0]])

    sin_c, sin_b = _error_m(centro, None), _error_m(borde, None)
    con_c, con_b = _error_m(centro, calibracion), _error_m(borde, calibracion)

    # Sin corregir, la homografía no puede representar la curva del lente
    assert sin_b.max() > 1.0, f"sin corregir, borde {sin_b.max():.2f} m"
    assert sin_c.max() < sin_b.max()
    # Corrigiendo, el borde queda en el orden del centro y muy por debajo de 2 m (CU-21)
    assert con_b.max() < 0.35, f"corregido, borde {con_b.max():.2f} m"
    assert con_b.max() < con_c.max() + 0.25
    assert con_b.max() < sin_b.max() / 4


# ---------------- Imagen ----------------

def _residuo_rectas(esquinas: np.ndarray) -> float:
    """Cuánto se apartan de una recta las esquinas de cada fila del tablero."""
    filas = esquinas.reshape(PATRON[1], PATRON[0], 2)
    peor = 0.0
    for fila in filas:
        vx, vy, x0, y0 = cv2.fitLine(fila.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        dist = np.abs((fila[:, 0] - x0) * vy - (fila[:, 1] - y0) * vx)
        peor = max(peor, float(dist.max()))
    return peor


def test_corregir_imagen_endereza_las_rectas(calibracion):
    foto = _renderizar_tablero(*_pose((5, -5, 4), (-0.3, -0.2), 12))
    mapa = precalcular_mapa(calibracion)
    corregida = corregir_imagen(foto, mapa)

    antes = _residuo_rectas(detectar_esquinas(foto, PATRON))
    despues = _residuo_rectas(detectar_esquinas(corregida, PATRON))
    assert antes > 2.0
    assert despues < 0.5
    assert corregida.shape == foto.shape


def test_el_mapa_se_reutiliza_y_valida_el_tamano(calibracion):
    mapa = precalcular_mapa(calibracion)
    for _ in range(3):
        corregir_imagen(np.zeros((ALTO, ANCHO, 3), np.uint8), mapa)
    with pytest.raises(ValueError, match="mapa"):
        corregir_imagen(np.zeros((100, 100), np.uint8), mapa)


def test_corregir_puntos_vacio(calibracion):
    assert corregir_puntos([], calibracion, precalcular_mapa(calibracion)).shape == (0, 2)


def test_corregir_puntos_coincide_con_la_imagen_corregida(calibracion):
    """Un punto corregido cae donde está ese mismo detalle en la imagen corregida."""
    foto = _renderizar_tablero(*_pose((0, 10, 0), (0.35, 0.2), 12))
    mapa = precalcular_mapa(calibracion)
    en_foto = detectar_esquinas(foto, PATRON).reshape(-1, 2)
    en_corregida = detectar_esquinas(corregir_imagen(foto, mapa), PATRON).reshape(-1, 2)
    diferencia = np.linalg.norm(corregir_puntos(en_foto, calibracion, mapa) - en_corregida, axis=1)
    assert math.isfinite(diferencia.max())
    assert diferencia.max() < 0.5
