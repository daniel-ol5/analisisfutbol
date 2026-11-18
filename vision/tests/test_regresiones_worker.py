"""Regresiones de reloj, modelos, geometría y observaciones; no requieren GPU."""
from dataclasses import replace
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from calibracion.dinamica import EstimadorHomografiaPitch, RastreadorHomografiaDinamica
from deteccion.modelo import CLASES_COCO, CLASES_FUTBOL, validar_clases
from procesamiento.fuente import CuadroProcesado
from procesamiento.mensajes import EstadoPipeline, armar_mensaje
from procesamiento.worker import atender_uno, procesar_trabajo
from seguimiento.gmc import CompensadorMovimientoCamara
from seguimiento.tipos import Clase
from test_procesamiento import TRABAJO, BackendFalso, _ctx, _det, _escena


@pytest.mark.parametrize("stride", [1, 2, 6])
def test_diez_segundos_duran_diez_segundos_en_cpu_y_gpu(tmp_path, stride):
    imagen, detecciones = _escena()
    cuadros = [CuadroProcesado(imagen, detecciones, i / 30, i) for i in range(0, 300, stride)]
    backend = BackendFalso(dict(TRABAJO))
    atender_uno(backend, lambda t, p: (cuadros, 30, 300), tmp_path, vid_stride=stride)
    muestras = [m for _, lote in backend.lotes for m in lote]
    assert len(muestras) == 50
    assert muestras[-1]["t"] == pytest.approx(9.8)


def test_se_conservan_pts_variables_y_no_se_emiten_muestras_inventadas():
    imagen, detecciones = _escena()
    pts = [0.0, 0.04, 0.23, 0.45, 1.10]
    cuadros = [CuadroProcesado(imagen, detecciones, t, i) for i, t in enumerate(pts)]
    backend = BackendFalso()
    procesar_trabajo(TRABAJO, cuadros, backend, 30, 5, vid_stride=1)
    assert [m["t"] for _, lote in backend.lotes for m in lote] == [0, 0.23, 0.45, 1.1]


def test_el_modelo_generico_no_puede_interpretarse_como_futbol():
    with pytest.raises(ValueError, match="incompatible"):
        validar_clases({0: "person", 32: "sports ball"}, CLASES_FUTBOL)
    validar_clases({0: "person", 32: "sports ball"}, CLASES_COCO)
    validar_clases(["ball", "goalkeeper", "player", "referee"], CLASES_FUTBOL)


def test_descarta_personas_fuera_de_cancha_sin_pegarlas_al_borde():
    imagen, detecciones = _escena()
    detecciones.append(_det(90, (-50, 10, -20, 40)))
    mensaje = armar_mensaje(_ctx(), 0, imagen, detecciones)
    assert 90 not in [j["tid"] for j in mensaje["jugadores"]]
    ctx = replace(_ctx(), largo_m=20, ancho_m=15)
    mensaje = armar_mensaje(ctx, 0, imagen, detecciones)
    assert all(0 <= j["x"] <= 20 and 0 <= j["y"] <= 15 for j in mensaje["jugadores"])


def test_prediccion_del_balon_no_cuenta_como_visible(monkeypatch):
    imagen, detecciones = _escena()
    estado = EstadoPipeline()
    monkeypatch.setattr(estado.balon, "_extraer_candidatos_campo", lambda *args: [])
    balon = _det(0, (250, 200, 260, 210), Clase.BALON)
    assert armar_mensaje(_ctx(), 0, imagen, [*detecciones, balon], estado)["balon"] is not None
    # Evitar que el fondo uniforme convierta este ensayo en uno de pérdida de cámara.
    estado.rastreador_homografia = None
    mensaje = armar_mensaje(_ctx(), 0.2, imagen, detecciones, estado)
    assert mensaje["balon"] is None
    assert mensaje["calidad"]["balon_visible"] is False


def test_gmc_conserva_zoom_y_rotacion_en_la_composicion():
    rng = np.random.default_rng(7)
    imagen = rng.integers(0, 255, (300, 400, 3), dtype=np.uint8)
    gmc = CompensadorMovimientoCamara(min_inliers=8, distancia_minima_puntos=8)
    gmc.estimar(imagen)
    matriz = cv2.getRotationMatrix2D((200, 150), 1, 1.02)
    movida = cv2.warpAffine(imagen, matriz, (400, 300))
    resultado = gmc.estimar(movida)
    assert resultado.es_valida
    assert abs(gmc.matriz_acumulada[0, 1]) > 0.005
    assert gmc.matriz_acumulada[0, 0] == pytest.approx(1.02, abs=0.01)


def test_un_checkpoint_de_pose_humana_no_calibra_una_cancha():
    puntos = MagicMock()
    puntos.__len__.return_value = 1
    puntos.xy.__getitem__.return_value.cpu.return_value.numpy.return_value = np.ones((17, 2))
    puntos.conf = None
    estimador = EstimadorHomografiaPitch()
    estimador._modelo = MagicMock(return_value=[MagicMock(keypoints=puntos)])
    with pytest.raises(ValueError, match="32 marcas"):
        estimador.estimar(np.zeros((100, 100, 3), dtype=np.uint8))


def test_la_calibracion_perdida_requiere_un_reanclaje_absoluto(monkeypatch):
    imagen, detecciones = _escena()
    gmc = CompensadorMovimientoCamara()
    movimientos = iter([True, False, True, True])
    monkeypatch.setattr(gmc, "estimar", lambda *args, **kwargs:
                        gmc._transformacion_identidad(valida=next(movimientos)))
    rastreador = RastreadorHomografiaDinamica(gmc=gmc)
    estado = EstadoPipeline(gmc=gmc, rastreador_homografia=rastreador)
    assert armar_mensaje(_ctx(), 0, imagen, detecciones, estado)["jugadores"]
    for t in (0.2, 0.4):
        mensaje = armar_mensaje(_ctx(), t, imagen, detecciones, estado)
        assert mensaje["jugadores"] == []
        assert mensaje["balon"] is None
        assert mensaje["calidad"]["calibracion_valida"] is False
    rastreador.estimador_pitch = MagicMock()
    rastreador.estimador_pitch.estimar.return_value = MagicMock(
        es_valida=True, homografia=_ctx().homografia)
    mensaje = armar_mensaje(_ctx(), 0.6, imagen, detecciones, estado)
    assert mensaje["calidad"]["calibracion_valida"] is True
    assert mensaje["jugadores"]
