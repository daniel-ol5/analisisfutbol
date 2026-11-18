"""Ensayo real de geometría: referencia automática, paneo, recuperación y evidencia visual."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from calibracion.dinamica import EstimadorHomografiaPitch, RastreadorHomografiaDinamica
from calibracion.terreno import lineas_imagen


def evaluar(video: Path, salida: Path, segundos: float = 180, stride: int = 6,
            dispositivo: str = "cpu", pesos: Path | None = None):
    if salida.exists() and any(salida.iterdir()):
        raise ValueError("Usa una carpeta vacía para conservar la evidencia")
    salida.mkdir(parents=True, exist_ok=True)
    estimador = EstimadorHomografiaPitch(ruta_pesos=pesos, dispositivo=dispositivo)
    if not estimador._cargar_modelo_si_hace_falta():
        raise ValueError("Instala el modelo de cancha antes de evaluar")
    rastreador = RastreadorHomografiaDinamica(estimador_pitch=estimador)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Video ilegible")
    muestras, estados = [], Counter()
    indice = 0
    siguiente_foto = 0.
    inicio = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if t >= segundos:
                break
            if indice % stride == 0:
                h = rastreador.actualizar(frame, t_s=t)
                error = rastreador.error_lineas_px
                muestra = {"t": t, "estado": rastreador.estado, "valida": rastreador.valida,
                           "error_lineas_px": error, "ultimo_anclaje_t": rastreador.ultimo_anclaje_t,
                           "matriz_h": h.tolist() if rastreador.valida else None}
                muestras.append(muestra)
                estados[rastreador.estado] += 1
                if t >= siguiente_foto:
                    if rastreador.valida:
                        for linea in lineas_imagen(h, 105, 68, frame.shape[1], frame.shape[0]):
                            pts = np.array(linea) * [frame.shape[1] / 100, frame.shape[0] / 100]
                            cv2.polylines(frame, [pts.astype(np.int32)], False, (100, 255, 255), 2)
                    cv2.putText(frame, f"t={t:.2f}s {rastreador.estado}", (20, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 255, 255), 2)
                    cv2.imwrite(str(salida / f"cuadro-{t:07.2f}.jpg"), frame)
                    print(f"t={t:.1f}s {rastreador.estado} error_lineas_px={error}", flush=True)
                    siguiente_foto = t + 5
            indice += 1
    finally:
        cap.release()
    resumen = {"video": str(video), "segundos_procesamiento": time.perf_counter() - inicio,
               "muestras": len(muestras), "estados": dict(estados), "dispositivo": dispositivo,
               "precision_metrica_validada": False}
    (salida / "muestras.json").write_text(json.dumps(muestras, indent=2), encoding="utf8")
    (salida / "resumen.json").write_text(json.dumps(resumen, indent=2), encoding="utf8")
    return resumen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--segundos", type=float, default=180)
    p.add_argument("--stride", type=int, default=6)
    p.add_argument("--dispositivo", default="cpu")
    p.add_argument("--pesos", type=Path)
    args = p.parse_args()
    if args.stride < 1 or args.segundos <= 0:
        p.error("Duración y stride deben ser positivos")
    import torch
    torch.set_num_threads(4)
    print(json.dumps(evaluar(args.video, args.salida, args.segundos, args.stride,
                             args.dispositivo, args.pesos), indent=2))


if __name__ == "__main__":
    main()
