"""Inspección reproducible de un archivo, sin YOLO, Torch ni GPU."""
import argparse
import json
import math
from pathlib import Path

import cv2


def inspeccionar(ruta: Path) -> dict:
    cap = cv2.VideoCapture(str(ruta))
    if not cap.isOpened():
        raise ValueError("No se pudo abrir el archivo")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        ancho, alto = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cuadros = 0
        primero = ultimo = None
        no_crecientes = 0
        intervalos = []
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if math.isfinite(pts):
                if ultimo is not None:
                    intervalo = pts - ultimo
                    no_crecientes += intervalo <= 0
                    intervalos.append(intervalo)
                primero = pts if primero is None else primero
                ultimo = pts
            cuadros += 1
        return {
            "archivo": ruta.name, "bytes": ruta.stat().st_size,
            "ancho_px": ancho, "alto_px": alto, "fps_declarados": fps,
            "cuadros_decodificados": cuadros, "primer_pts_s": primero, "ultimo_pts_s": ultimo,
            "duracion_nominal_s": cuadros / fps if fps > 0 else None,
            "pts_no_crecientes": no_crecientes,
            "intervalo_min_s": min(intervalos) if intervalos else None,
            "intervalo_max_s": max(intervalos) if intervalos else None,
            "inferencia_ejecutada": False,
        }
    finally:
        cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    texto = json.dumps(inspeccionar(args.archivo), ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto + "\n", encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
