from unittest.mock import MagicMock
import numpy as np
import pytest

from calibracion.dinamica import (
    EstimadorHomografiaPitch,
    RastreadorHomografiaDinamica,
    generar_keypoints_campo,
)
from seguimiento.gmc import CompensadorMovimientoCamara, TransformacionCamara


def test_generar_keypoints_campo_estandar():
    kpts = generar_keypoints_campo(105.0, 68.0)
    assert len(kpts) == 32
    for idx, (x, y) in kpts.items():
        assert 0.0 <= x <= 105.0, f"X={x} fuera de rango en keypoint {idx}"
        assert 0.0 <= y <= 68.0, f"Y={y} fuera de rango en keypoint {idx}"

    # Córners
    assert kpts[0] == (0.0, 0.0)
    assert kpts[5] == (0.0, 68.0)
    assert kpts[24] == (105.0, 0.0)
    assert kpts[29] == (105.0, 68.0)

    # Línea media y círculo central
    assert kpts[13] == (52.5, 0.0)
    assert kpts[16] == (52.5, 68.0)
    assert kpts[30] == pytest.approx((52.5 - 9.15, 34.0), abs=1e-3)
    assert kpts[31] == pytest.approx((52.5 + 9.15, 34.0), abs=1e-3)

    # Puntos penales
    assert kpts[8] == (11.0, 34.0)
    assert kpts[21] == (105.0 - 11.0, 34.0)


def test_estimador_cuadro_invalido():
    estimador = EstimadorHomografiaPitch()
    res = estimador.estimar(np.array([]))
    assert not res.es_valida
    assert res.homografia is None
    assert res.puntos_detectados == 0


def test_estimador_con_mock_yolo():
    estimador = EstimadorHomografiaPitch()

    # Mapeo sintético afín positivo de metros a píxeles
    # u = 100.0 + 10.0 * x_m, v = 50.0 + 8.0 * y_m
    H_m2px = np.array([
        [10.0, 0.0, 100.0],
        [0.0, 8.0, 50.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    kpts_campo = estimador.keypoints_metricos
    indices_usados = [0, 5, 8, 13, 16, 21, 24, 29]

    # Generar coordenadas en píxeles
    xy_simuladas = np.zeros((32, 2), dtype=np.float32)
    conf_simuladas = np.zeros(32, dtype=np.float32)

    for idx in indices_usados:
        xm, ym = kpts_campo[idx]
        pt_px = H_m2px @ np.array([xm, ym, 1.0])
        xy_simuladas[idx] = [pt_px[0], pt_px[1]]
        conf_simuladas[idx] = 0.95

    # Mockear salida de YOLO
    mock_res = MagicMock()
    mock_res.keypoints.__len__ = lambda self: 1
    mock_res.keypoints.xy = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: xy_simuladas))]
    mock_res.keypoints.conf = [MagicMock(cpu=lambda: MagicMock(numpy=lambda: conf_simuladas))]

    mock_modelo = MagicMock(return_value=[mock_res])
    estimador._modelo = mock_modelo

    frame_dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
    res = estimador.estimar(frame_dummy)

    assert res.es_valida
    assert res.homografia is not None
    assert res.puntos_inliers == len(indices_usados)
    assert res.error_medio_m < 0.05
    assert len(res.puntos_imagen) == len(indices_usados)
    assert len(res.puntos_cancha) == len(indices_usados)


def test_rastreador_homografia_dinamica_gmc():
    H_0 = np.eye(3, dtype=np.float64)
    gmc = CompensadorMovimientoCamara()
    
    # Mockear transformación de paneo: cámara se mueve 50px a la derecha (dx=50)
    gmc.estimar = MagicMock(return_value=TransformacionCamara(
        dx=50.0, dy=0.0, rotacion_rad=0.0, escala=1.0,
        matriz_afine=np.array([[1.0, 0.0, 50.0], [0.0, 1.0, 0.0]]),
        matriz_3x3=np.array([[1.0, 0.0, 50.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        inliers_pct=0.9, es_valida=True
    ))
    gmc._t_acumulada_3x3 = np.array([[1.0, 0.0, 50.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    rastreador = RastreadorHomografiaDinamica(estimador_pitch=None, gmc=gmc)
    frame_dummy = np.zeros((100, 100, 3), dtype=np.uint8)

    H_din = rastreador.actualizar(frame_dummy, homografia_referencia=H_0)

    # Si la cámara panea +50px a la derecha, la escena en píxeles se mueve -50px
    # por lo que T_acumulada @ x_0 traslada +50, e inv(T) traslada -50
    assert H_din[0, 2] == pytest.approx(-50.0, abs=1e-3)


def test_rastreador_homografia_dinamica_suavizado_recalibracion():
    H_0 = np.eye(3, dtype=np.float64)
    gmc = CompensadorMovimientoCamara()
    gmc.estimar = MagicMock(return_value=TransformacionCamara(
        dx=0.0, dy=0.0, rotacion_rad=0.0, escala=1.0,
        matriz_afine=np.eye(2, 3), matriz_3x3=np.eye(3),
        inliers_pct=1.0, es_valida=True
    ))

    # Estimador mock que devuelve una homografía levemente distinta
    H_pitch = np.array([
        [1.0, 0.0, 10.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    mock_estimador = MagicMock()
    mock_estimador.estimar = MagicMock(return_value=MagicMock(
        es_valida=True, homografia=H_pitch
    ))

    rastreador = RastreadorHomografiaDinamica(
        estimador_pitch=mock_estimador,
        gmc=gmc,
        alpha_suavizado=0.5,
    )
    frame_dummy = np.zeros((100, 100, 3), dtype=np.uint8)

    # Forzar recalibración
    H_result = rastreador.actualizar(frame_dummy, homografia_referencia=H_0, forzar_recalibracion=True)

    # Suavizado al 50%: (1 - 0.5) * 0.0 + 0.5 * 10.0 = 5.0
    assert H_result[0, 2] == pytest.approx(5.0, abs=1e-3)
