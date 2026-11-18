# Pegar este archivo completo en una celda nueva del Colab que ya tiene el video.
import json
import shutil
from pathlib import Path
from uuid import uuid4

import torch
from deteccion.modelo import CLASES_COCO, ConfigModelo, ModeloDeteccion
from evaluacion.ensayo_video import ensayar
from google.colab import files

USAR_CALIBRACION_ENSAYO = False  # Cambiar a True para subir el JSON válido de la aplicación.
COLOR_PROPIO = "#C8102E"
COLOR_RIVAL = "#17202A"
ES_LOCAL = True

if not torch.cuda.is_available():
    raise RuntimeError("Activa una GPU antes de ejecutar esta celda")
video_prueba = globals().get("video")
if video_prueba is None:
    raise RuntimeError("Ejecuta primero la celda que sube el video")

calibracion_ensayo = None
if USAR_CALIBRACION_ENSAYO:
    subidos_calibracion = files.upload()
    if len(subidos_calibracion) != 1:
        raise ValueError("Selecciona solo el JSON de calibración")
    calibracion_ensayo = json.loads(next(iter(subidos_calibracion.values())))
    subidos_calibracion.clear()
    if calibracion_ensayo.get("modo") == "AUTOMATICA":
        from calibracion.instalar_modelo import instalar
        instalar()
    elif not calibracion_ensayo.get("valida") or not calibracion_ensayo.get("matriz_h"):
        raise ValueError("La calibración debe estar validada y tener matriz_h")

raiz_pruebas = Path(globals().get("CARPETA_ENSAYOS_COLAB", "/content")) / f"ensayo-futbol-{uuid4().hex[:8]}"
raiz_pruebas.mkdir()
print("GPU:", torch.cuda.get_device_name(0))

for nombre, simular in [("grabacion", False), ("directo-simulado", True)]:
    modelo_prueba = ModeloDeteccion(ConfigModelo(
        ruta_pesos="yolo11n.pt", clases=dict(CLASES_COCO),
        dispositivo="cuda:0", tamano_img=1280,
    ))
    modelo_prueba.cargar()
    observado = {}

    def registrar_dispositivo(predictor, registro=observado):
        registro["dispositivo"] = str(predictor.device)

    modelo_prueba.modelo.add_callback("on_predict_postprocess_end", registrar_dispositivo)
    torch.cuda.reset_peak_memory_stats()
    print("Iniciando", nombre, "| 30 segundos de video | imagen 1280")
    resumen = ensayar(modelo_prueba, Path(video_prueba), raiz_pruebas / nombre,
                      segundos=30, stride=1, simular_directo=simular,
                      calibracion=calibracion_ensayo, color_propio=COLOR_PROPIO,
                      color_rival=COLOR_RIVAL, es_local=ES_LOCAL)
    torch.cuda.synchronize()
    real = observado.get("dispositivo")
    if not real or not real.startswith("cuda"):
        raise RuntimeError(f"No se confirmó inferencia en GPU: {observado}")
    resumen.update(dispositivo=real, dispositivo_real_modelo=real,
                   gpu_nombre=torch.cuda.get_device_name(0),
                   gpu_memoria_max_mib=round(torch.cuda.max_memory_allocated() / 1024**2, 1))
    (raiz_pruebas / nombre / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    del modelo_prueba
    torch.cuda.empty_cache()

paquete_prueba = shutil.make_archive(str(raiz_pruebas), "zip", raiz_pruebas)
files.download(paquete_prueba)
print("Ensayos terminados. Conserva el ZIP descargado:", paquete_prueba)
