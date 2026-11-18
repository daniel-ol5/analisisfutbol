import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from deteccion.modelo import ModeloDeteccion


@pytest.mark.parametrize("dispositivo", ["cuda:0", "cpu"])
def test_dispositivo_del_predictor_aunque_los_pesos_base_sigan_en_cpu(dispositivo):
    modelo = ModeloDeteccion()
    modelo._modelo = SimpleNamespace(
        model=SimpleNamespace(device="cpu"),
        predictor=SimpleNamespace(device=dispositivo),
    )
    assert modelo.dispositivo_inferencia() == dispositivo


def test_sin_inferencia_no_se_inventa_un_dispositivo_ni_se_carga_yolo():
    modelo = ModeloDeteccion()
    assert modelo.dispositivo_inferencia() is None
    modelo._modelo = SimpleNamespace(model=SimpleNamespace(device="cpu"), predictor=None)
    assert modelo.dispositivo_inferencia() is None


def test_se_registra_dispositivo_durante_inferencia_aunque_se_libere_predictor(monkeypatch):
    callbacks = {}
    yolo = SimpleNamespace(names={0: "person", 32: "sports ball"}, predictor=None,
        add_callback=lambda evento, funcion: callbacks.update({evento: funcion}))
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda pesos: yolo))
    modelo = ModeloDeteccion()
    modelo.cargar()
    assert modelo.dispositivo_inferencia() is None
    callbacks["on_predict_postprocess_end"](SimpleNamespace(device="cuda:0"))
    assert modelo.dispositivo_inferencia() == "cuda:0"
    modelo.cargar()  # Otra carga no puede heredar evidencia de una ejecución anterior.
    assert modelo.dispositivo_inferencia() is None


@pytest.mark.parametrize("celda_id,carpeta", [
    ("celda-12", "grabacion"), ("celda-14", "directo-simulado"),
])
@pytest.mark.parametrize("dispositivo", ["cuda:0", "cpu"])
def test_cuaderno_verifica_predictor_con_pesos_base_cpu(tmp_path, celda_id, carpeta, dispositivo):
    modelo = ModeloDeteccion()
    modelo._modelo = SimpleNamespace(
        model=SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device="cpu")])),
        predictor=SimpleNamespace(device=dispositivo),
    )

    def ensayo_falso(modelo, video, salida, **kwargs):
        salida.mkdir()
        return {"dispositivo": dispositivo}

    cuda = SimpleNamespace(
        reset_peak_memory_stats=lambda: None, synchronize=lambda: None,
        max_memory_allocated=lambda: 1024**2, get_device_name=lambda i: "GPU simulada",
        empty_cache=lambda: None,
    )
    alcance = {"nuevo_modelo": lambda: modelo, "torch": SimpleNamespace(cuda=cuda),
        "ensayar": ensayo_falso, "video": tmp_path / "clip.mp4", "salidas": tmp_path,
        "SEGUNDOS": 30, "STRIDE": 1, "calibracion": None, "COLOR_PROPIO": "#C8102E",
        "COLOR_RIVAL": "#17202A", "ES_LOCAL": True, "json": json}
    cuaderno = Path(__file__).resolve().parents[1] / "notebooks/Primera_prueba_Colab.ipynb"
    celdas = json.loads(cuaderno.read_text(encoding="utf-8"))["cells"]
    codigo = "".join(next(c for c in celdas if c["id"] == celda_id)["source"])
    if dispositivo == "cpu":
        with pytest.raises(RuntimeError, match="no se ejecuto en GPU"):
            exec(compile(codigo, celda_id, "exec"), alcance)  # noqa: S102 -- Cuaderno local del proyecto.
        return
    exec(compile(codigo, celda_id, "exec"), alcance)  # noqa: S102 -- Cuaderno local del proyecto.
    resumen = json.loads(next(tmp_path.glob(f"{carpeta}-*/resumen.json")).read_text())
    assert resumen["dispositivo_real_modelo"] == "cuda:0"


@pytest.mark.parametrize("con_calibracion", [False, True])
def test_celda_de_continuacion_funciona_sin_predictor_persistente(tmp_path, monkeypatch, con_calibracion):
    llamadas = []
    descargas = []
    calibracion = {"valida": True, "matriz_h": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def crear_modelo(config):
        callbacks = {}
        yolo = SimpleNamespace(predictor=None,
            add_callback=lambda evento, funcion: callbacks.update({evento: funcion}))
        return SimpleNamespace(config=config, modelo=yolo, cargar=lambda: None, callbacks=callbacks)

    def ensayo_falso(modelo, video, salida, **kwargs):
        llamadas.append(kwargs["simular_directo"])
        assert kwargs["calibracion"] == (calibracion if con_calibracion else None)
        salida.mkdir()
        modelo.callbacks["on_predict_postprocess_end"](SimpleNamespace(device="cuda:0"))
        return {"dispositivo": None}  # Emula el informe sin predictor disponible al terminar.

    cuda = SimpleNamespace(is_available=lambda: True, get_device_name=lambda i: "GPU simulada",
        reset_peak_memory_stats=lambda: None, synchronize=lambda: None,
        max_memory_allocated=lambda: 1024**2, empty_cache=lambda: None)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    colab = SimpleNamespace(files=SimpleNamespace(download=descargas.append,
        upload=lambda: {"calibracion.json": json.dumps(calibracion).encode()}))
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(colab=colab))
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.setattr("deteccion.modelo.ModeloDeteccion", crear_modelo)
    monkeypatch.setattr("evaluacion.ensayo_video.ensayar", ensayo_falso)
    script = Path(__file__).resolve().parents[1] / "notebooks/Continuar_prueba_Colab.py"
    alcance = {"video": tmp_path / "clip.mp4", "CARPETA_ENSAYOS_COLAB": str(tmp_path)}
    codigo = script.read_text(encoding="utf-8")
    if con_calibracion:
        codigo = codigo.replace("USAR_CALIBRACION_ENSAYO = False", "USAR_CALIBRACION_ENSAYO = True")
    exec(compile(codigo, str(script), "exec"), alcance)  # noqa: S102 -- Celda local del proyecto.
    assert llamadas == [False, True]
    assert len(descargas) == 1
    assert Path(descargas[0]).is_file()
    for resumen in tmp_path.glob("ensayo-futbol-*/*/resumen.json"):
        assert json.loads(resumen.read_text())["dispositivo_real_modelo"] == "cuda:0"
