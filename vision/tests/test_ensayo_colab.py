import json
import zipfile
from types import SimpleNamespace

import numpy as np
import pytest
from deteccion.modelo import ConfigModelo
from evaluacion.ensayo_video import ensayar
from evaluacion.preparar_colab import preparar
from procesamiento.fuente import CuadroProcesado
from test_procesamiento import _ctx, _escena


def test_ensayo_exporta_detecciones_y_telemetria_sin_api(tmp_path, monkeypatch):
    imagen, detecciones = _escena()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fixture")
    modelo = SimpleNamespace(config=ConfigModelo(dispositivo="cpu"),
        dispositivo_efectivo=lambda: "cpu", dispositivo_inferencia=lambda: "cpu",
        modelo=SimpleNamespace(names={0: "person"}))
    monkeypatch.setattr("evaluacion.ensayo_video.seguir_con_cuadros", lambda *args:
        (CuadroProcesado(imagen, detecciones, t, i) for i, t in enumerate([0, .2, .4])))
    salida = tmp_path / "resultados"
    resumen = ensayar(modelo, video, salida, calibracion={"valida": True,
        "matriz_h": _ctx().homografia.tolist(), "partido_id": 7})
    assert resumen["cuadros_inferidos"] == 3
    assert resumen["ultimo_t_s"] == .4
    assert resumen["precision_validada"] is False
    assert resumen["dispositivo"] == "cpu"
    muestras = json.loads((salida / "muestras.json").read_text())
    assert len(muestras) == 3
    assert muestras[0]["partido"] == 7
    assert len((salida / "detecciones.jsonl").read_text().splitlines()) == 3
    assert list(salida.glob("cuadro-*.jpg"))
    with pytest.raises(ValueError, match="vacía"):
        ensayar(modelo, video, salida)


def test_ensayo_sin_calibracion_no_fabrica_posiciones_metricas(tmp_path, monkeypatch):
    imagen = np.zeros((20, 20, 3), np.uint8)
    modelo = SimpleNamespace(config=ConfigModelo(dispositivo="cpu"),
        dispositivo_efectivo=lambda: "cpu", dispositivo_inferencia=lambda: "cpu",
        modelo=SimpleNamespace(names={0: "person"}))
    monkeypatch.setattr("evaluacion.ensayo_video._directo", lambda *args:
        (item for item in [CuadroProcesado(imagen, [], .1, 0)]))
    salida = tmp_path / "sin-calibracion"
    resumen = ensayar(modelo, tmp_path / "clip.mp4", salida, simular_directo=True)
    assert resumen["modo"] == "directo_simulado"
    assert json.loads((salida / "muestras.json").read_text()) == []


def test_paquete_colab_solo_incluye_codigo_y_configuracion(tmp_path):
    salida = tmp_path / "worker.zip"
    manifiesto = preparar(salida)
    with zipfile.ZipFile(salida) as paquete:
        nombres = paquete.namelist()
        assert "vision/procesamiento/directo.py" in nombres
        assert "vision/evaluacion/ensayo_video.py" in nombres
        assert "vision/entrenamiento/entrenar.py" in nombres
        assert "vision/evaluacion/validacion_yolo.py" in nombres
        assert "vision/seguimiento/tracker_futbol.yaml" in nombres
        assert set(nombres) == {f"vision/{n}" for n in manifiesto} | {"manifiesto.json"}
        assert all(not n.endswith((".env", ".pt", ".mp4", ".db")) for n in nombres)
    with pytest.raises(FileExistsError):
        preparar(salida)
