import cv2
import numpy as np
import pytest

from seguimiento.gmc import CompensadorMovimientoCamara, TransformacionCamara


def test_primer_cuadro_devuelve_identidad():
    gmc = CompensadorMovimientoCamara()
    cuadro = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(cuadro, (50, 50), 10, (255, 255, 255), -1)

    t = gmc.estimar(cuadro)
    assert t.dx == 0.0
    assert t.dy == 0.0
    assert t.escala == 1.0
    assert t.rotacion_rad == 0.0
    assert t.es_valida is True
    np.testing.assert_allclose(t.matriz_3x3, np.eye(3))


def test_estimacion_traslacion_sintetica():
    gmc = CompensadorMovimientoCamara(min_inliers=5)

    cuadro1 = np.zeros((200, 200, 3), dtype=np.uint8)
    for x in range(30, 170, 30):
        for y in range(30, 170, 30):
            cv2.rectangle(cuadro1, (x, y), (x + 8, y + 8), (255, 255, 255), -1)

    # Desplazamiento sintético: dx = 12.0, dy = -5.0
    m_real = np.float32([[1.0, 0.0, 12.0], [0.0, 1.0, -5.0]])
    cuadro2 = cv2.warpAffine(cuadro1, m_real, (200, 200))

    _ = gmc.estimar(cuadro1)
    t = gmc.estimar(cuadro2)

    assert t.es_valida is True
    assert pytest.approx(t.dx, abs=1.0) == 12.0
    assert pytest.approx(t.dy, abs=1.0) == -5.0
    assert pytest.approx(t.escala, abs=0.05) == 1.0
    assert pytest.approx(t.rotacion_rad, abs=0.05) == 0.0


def test_compensar_caja():
    gmc = CompensadorMovimientoCamara()
    m_2x3 = np.array([[1.0, 0.0, 15.0], [0.0, 1.0, -10.0]], dtype=np.float64)
    m_3x3 = np.eye(3, dtype=np.float64)
    m_3x3[:2, :] = m_2x3

    t = TransformacionCamara(
        dx=15.0,
        dy=-10.0,
        rotacion_rad=0.0,
        escala=1.0,
        matriz_afine=m_2x3,
        matriz_3x3=m_3x3,
        inliers_pct=1.0,
        es_valida=True,
    )

    caja_orig = (100.0, 100.0, 150.0, 200.0)
    caja_comp = gmc.compensar_caja(caja_orig, t)

    assert pytest.approx(caja_comp[0], abs=0.1) == 115.0
    assert pytest.approx(caja_comp[1], abs=0.1) == 90.0
    assert pytest.approx(caja_comp[2], abs=0.1) == 165.0
    assert pytest.approx(caja_comp[3], abs=0.1) == 190.0


def test_homografia_compensada():
    gmc = CompensadorMovimientoCamara()
    # Simular una traslación acumulada de 100 px a la derecha
    m_acum = np.array([
        [1.0, 0.0, 100.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    gmc._t_acumulada_3x3 = m_acum

    h_0 = np.eye(3, dtype=np.float64)
    h_comp = gmc.homografia_compensada(h_0)

    # Un punto que en el cuadro actual está en x=400 (porque la cámara se movió 100 a la derecha,
    # el punto original estaba en x=300) debe dar x=300 al aplicarle h_comp
    pt_actual = np.array([400.0, 50.0, 1.0])
    pt_mundo = h_comp @ pt_actual
    assert pytest.approx(pt_mundo[0], abs=0.1) == 300.0
    assert pytest.approx(pt_mundo[1], abs=0.1) == 50.0

