import cv2
import numpy as np
import pytest

from seguimiento.balon import RastreadorBalon
from seguimiento.gmc import TransformacionCamara
from seguimiento.tipos import Clase, Deteccion


def test_balon_detectado_por_yolo():
    rastreador = RastreadorBalon()
    cuadro = np.zeros((100, 100, 3), dtype=np.uint8)
    det_yolo = [Deteccion.desde_caja(0, Clase.BALON, (45.0, 45.0, 55.0, 55.0), 0.85)]

    balon = rastreador.actualizar(cuadro, det_yolo)
    assert balon is not None
    assert balon.clase == Clase.BALON
    assert pytest.approx(balon.caja[0], abs=1.0) == 45.0
    assert pytest.approx(balon.caja[2], abs=1.0) == 55.0
    assert pytest.approx(balon.conf, abs=0.01) == 0.85
    assert len(rastreador.estela) == 1


def test_balon_inercia_en_oclusion():
    rastreador = RastreadorBalon(max_cuadros_perdido=3)
    cuadro = np.zeros((200, 200, 3), dtype=np.uint8)

    # Cuadro 1: en (50, 50)
    det1 = [Deteccion.desde_caja(0, Clase.BALON, (45.0, 45.0, 55.0, 55.0), 0.9)]
    _ = rastreador.actualizar(cuadro, det1)

    # Cuadro 2: se mueve a (60, 50) -> vx = 10
    det2 = [Deteccion.desde_caja(0, Clase.BALON, (55.0, 45.0, 65.0, 55.0), 0.9)]
    b2 = rastreador.actualizar(cuadro, det2)
    assert b2 is not None

    # Cuadro 3: Oclusión (sin detecciones). El balón debe avanzar por inercia hacia x > 60
    b3 = rastreador.actualizar(cuadro, [])
    assert b3 is not None
    cx3 = (b3.caja[0] + b3.caja[2]) / 2.0
    assert cx3 > 60.0

    # Cuadros 4 y 5 sin detección
    _ = rastreador.actualizar(cuadro, [])
    _ = rastreador.actualizar(cuadro, [])

    # Cuadro 6: supera max_cuadros_perdido -> debe ser None (perdido)
    b_perdido = rastreador.actualizar(cuadro, [])
    assert b_perdido is None


def test_balon_compensacion_gmc():
    rastreador = RastreadorBalon()
    cuadro = np.zeros((200, 200, 3), dtype=np.uint8)

    # Balón estático en (100, 100)
    det = [Deteccion.desde_caja(0, Clase.BALON, (95.0, 95.0, 105.0, 105.0), 0.9)]
    _ = rastreador.actualizar(cuadro, det)

    # La cámara se mueve 20 px a la derecha (dx = 20)
    m_2x3 = np.array([[1.0, 0.0, 20.0], [0.0, 1.0, 0.0]], dtype=np.float64)
    m_3x3 = np.eye(3, dtype=np.float64)
    m_3x3[:2, :] = m_2x3
    t_cam = TransformacionCamara(20.0, 0.0, 0.0, 1.0, m_2x3, m_3x3, 1.0, True)

    # Siguiente cuadro en oclusión con movimiento de cámara
    b = rastreador.actualizar(cuadro, [], transformacion_camara=t_cam)
    assert b is not None
    cx = (b.caja[0] + b.caja[2]) / 2.0
    # Posición debe haberse desplazado por el movimiento de cámara a ~120
    assert pytest.approx(cx, abs=2.0) == 120.0

