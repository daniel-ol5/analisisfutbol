from dataclasses import replace
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from calibracion.dinamica import RastreadorHomografiaDinamica
from calibracion.referencias import BancoReferencias
from procesamiento.mensajes import EstadoPipeline, armar_mensaje
from procesamiento.worker import contexto
from seguimiento.gmc import CompensadorMovimientoCamara
from test_procesamiento import TRABAJO, _ctx, _escena


def test_el_contrato_actual_no_reutiliza_referencias_manuales_sin_fuente():
    with pytest.raises(ValueError, match="no identifica su fuente"):
        contexto({**TRABAJO, "modo_calibracion": "MANUAL", "referencia": None}, 5)


def test_se_sigue_perspectiva_sin_reducirla_a_traslacion():
    rng = np.random.default_rng(42)
    imagen = rng.integers(0, 255, (300, 450, 3), dtype=np.uint8)
    real = np.array([[1.01, .012, 7], [-.006, 1.005, -3], [.00008, -.00005, 1.]])
    movida = cv2.warpPerspective(imagen, real, (450, 300))
    gmc = CompensadorMovimientoCamara(distancia_minima_puntos=8)
    gmc.estimar(imagen)
    resultado = gmc.estimar(movida, dt_s=.04)
    assert resultado.es_valida
    controles = np.float32([[80, 60], [350, 80], [300, 240], [100, 210]]).reshape(-1, 1, 2)
    esperados = cv2.perspectiveTransform(controles, real)
    observados = cv2.perspectiveTransform(controles, resultado.matriz_3x3)
    assert np.max(np.linalg.norm(esperados - observados, axis=2)) < 1.5


def test_una_referencia_futura_no_se_aplica_antes_de_su_cuadro():
    imagen, detecciones = _escena()
    ctx = replace(_ctx(), referencia={"tiempo_s": 2.0})
    estado = EstadoPipeline()
    estado.gmc.estimar = MagicMock(side_effect=lambda *a, **k: estado.gmc._transformacion_identidad())
    for t in (0, .2, 1.8):
        mensaje = armar_mensaje(ctx, t, imagen, detecciones, estado)
        assert mensaje["jugadores"] == []
        assert mensaje["detecciones"]
        assert mensaje["calidad"]["calibracion_valida"] is False
    mensaje = armar_mensaje(ctx, 2, imagen, detecciones, estado)
    assert mensaje["jugadores"]


def test_la_referencia_expira_sin_verificacion_absoluta():
    imagen, detecciones = _escena()
    estado = EstadoPipeline()
    estado.gmc.estimar = MagicMock(side_effect=lambda *a, **k: estado.gmc._transformacion_identidad())
    for t in np.arange(0, 5.4, .2):
        mensaje = armar_mensaje(_ctx(), float(t), imagen, detecciones, estado)
    assert mensaje["calidad"]["estado_calibracion"] == "PERDIDA"
    assert mensaje["jugadores"] == []
    assert mensaje["detecciones"]


def test_buscar_una_referencia_guardada_no_pospone_el_anclaje_periodico():
    imagen, _ = _escena()
    estimador = MagicMock()
    estimador.estimar.return_value.es_valida = False
    rastreador = RastreadorHomografiaDinamica(estimador_pitch=estimador, recalibrar_cada_n_cuadros=3)
    rastreador.gmc.estimar = MagicMock(side_effect=lambda *args, **kw: rastreador.gmc._transformacion_identidad())
    rastreador.banco = MagicMock()
    rastreador.banco.recuperar.return_value = None

    for t in (0, 0.2, 0.4):
        rastreador.actualizar(imagen, np.eye(3), t_s=t)

    rastreador.banco.recuperar.assert_called_once()
    estimador.estimar.assert_called_once()


def test_cambio_de_resolucion_invalida_la_continuidad():
    gmc = CompensadorMovimientoCamara()
    gmc.estimar(np.zeros((100, 100, 3), np.uint8))
    assert not gmc.estimar(np.zeros((120, 160, 3), np.uint8)).es_valida


def test_referencia_visual_recupera_un_paneo_y_rechaza_otra_escena():
    rng = np.random.default_rng(20)
    original = rng.integers(0, 255, (420, 640, 3), dtype=np.uint8)
    transformacion = np.array([[1., .015, 12.], [-.01, 1., -5.], [.00002, -.00003, 1.]])
    movida = cv2.warpPerspective(original, transformacion, (640, 420))
    banco = BancoReferencias()
    banco.agregar(original, np.eye(3))
    recuperada = banco.recuperar(movida)
    assert recuperada is not None
    controles = np.float32([[80, 100], [550, 110], [400, 330], [150, 300]]).reshape(-1, 1, 2)
    actuales = cv2.perspectiveTransform(controles, transformacion)
    reconstruidos = cv2.perspectiveTransform(actuales, recuperada[0])
    assert np.max(np.linalg.norm(controles - reconstruidos, axis=2)) < 1
    assert banco.recuperar(rng.integers(0, 255, original.shape, dtype=np.uint8)) is None


def test_referencia_visual_descarta_un_ajuste_sin_correspondencias_validas(monkeypatch):
    cuadro = np.zeros((100, 160, 3), dtype=np.uint8)
    puntos = np.float32([(x, y) for x in (10, 50, 100, 150) for y in (10, 25, 40, 55, 70, 85)])
    descriptores = np.eye(len(puntos), dtype=np.float32)
    banco = BancoReferencias()
    monkeypatch.setattr(banco, "caracteristicas", lambda *_: (puntos, descriptores))
    banco.agregar(cuadro, np.eye(3))

    # Una matriz finita puede venir acompañada de una máscara sin inliers.
    mascara = np.zeros((len(puntos), 1), dtype=np.uint8)
    monkeypatch.setattr(cv2, "findHomography", lambda *_: (np.eye(3), mascara))

    assert banco.recuperar(cuadro) is None
