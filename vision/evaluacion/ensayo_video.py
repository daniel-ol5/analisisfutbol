"""Ensayo interactivo sin API: detecciones, telemetría opcional y evidencia local."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import math
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
from calibracion.homografia import cargar_homografia
from deteccion.modelo import (
    CLASES_COCO,
    CLASES_FUTBOL,
    CLASES_PROPIO,
    ConfigModelo,
    ModeloDeteccion,
)
from procesamiento.directo import cuadros_recientes
from procesamiento.fuente import CuadroProcesado, seguir_con_cuadros
from procesamiento.mensajes import Contexto, EstadoPipeline, armar_mensaje
from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar


def _sha256(ruta: Path) -> str | None:
    if not ruta.is_file():
        return None
    with ruta.open("rb") as archivo:
        return hashlib.file_digest(archivo, "sha256").hexdigest()


def _versiones() -> dict[str, str]:
    versiones = {"python": platform.python_version()}
    for nombre in ("torch", "ultralytics", "opencv-python", "numpy"):
        try:
            versiones[nombre] = importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            versiones[nombre] = "no instalado"
    return versiones


def _directo(modelo: ModeloDeteccion, ruta: Path):
    fuente = cuadros_recientes(str(ruta), simular=True)
    try:
        for indice, (imagen, t) in enumerate(fuente):
            resultado = modelo.modelo.track(imagen, tracker=str(_CONFIG_TRACKER_DEFECTO),
                persist=True, device=modelo.dispositivo_efectivo(), imgsz=modelo.config.tamano_img,
                conf=modelo.config.confianza_min, iou=modelo.config.iou_nms, verbose=False)[0]
            yield CuadroProcesado(imagen, _adaptar(resultado, modelo.config), t, indice)
    finally:
        fuente.close()


def ensayar(
    modelo: ModeloDeteccion, video: Path, salida: Path, *, segundos: float = 30,
    stride: int = 1, simular_directo: bool = False, calibracion: dict[str, Any] | None = None,
    color_propio: str = "#C8102E", color_rival: str = "#17202A", es_local: bool = True,
) -> dict[str, Any]:
    if not math.isfinite(segundos) or segundos <= 0 or stride < 1:
        raise ValueError("La duración y el salto deben ser positivos")
    if salida.exists() and any(salida.iterdir()):
        raise ValueError("Usa una carpeta de salida vacía para conservar cada ensayo")
    salida.mkdir(parents=True, exist_ok=True)
    ctx = None
    estado = None
    dispositivo = modelo.dispositivo_efectivo()
    if calibracion is not None:
        automatico = calibracion.get("modo") == "AUTOMATICA"
        if not automatico and not calibracion.get("valida"):
            raise ValueError("La calibración debe estar validada")
        if calibracion.get("coef_distorsion") and any(calibracion["coef_distorsion"]):
            raise ValueError("Este ensayo requiere video rectificado y una calibración sobre ese video")
        if calibracion.get("tamano_imagen_fuente"):
            captura = cv2.VideoCapture(str(video))
            try:
                tamano = {"ancho": int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)),
                          "alto": int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))}
            finally:
                captura.release()
            if calibracion["tamano_imagen_fuente"] != tamano:
                raise ValueError("La calibración y el video tienen resoluciones distintas")
        ctx = Contexto(calibracion.get("partido_id", 1), cargar_homografia(calibracion["matriz_h"]) if calibracion.get("matriz_h") else None,
            es_local, color_propio, color_rival, 5,
            calibracion.get("largo_m", 105), calibracion.get("ancho_m", 68),
            modo_calibracion=calibracion.get("modo", "MANUAL"), referencia=calibracion.get("referencia"))
        estado = EstadoPipeline(dispositivo=dispositivo, largo_m=ctx.largo_m, ancho_m=ctx.ancho_m,
                                habilitar_reconocimiento=automatico or bool(ctx.referencia))
        if automatico and estado.rastreador_homografia.estimador_pitch is None:
            raise ValueError("Instala primero el modelo de cancha: python -m calibracion.instalar_modelo")
    fuente = _directo(modelo, video) if simular_directo else seguir_con_cuadros(modelo, video, stride)
    muestras = []
    frames = balon_detectado = 0
    siguiente_t = foto_t = 0.0
    ultima_t = None
    inicio = time.perf_counter()
    try:
        with (salida / "detecciones.jsonl").open("w", encoding="utf-8") as archivo:
            for item in fuente:
                if item.t >= segundos:
                    break
                frames += 1
                ultima_t = item.t
                balon_detectado += any(d.clase.value == "BALON" for d in item.detecciones)
                archivo.write(json.dumps({"t": item.t, "indice": item.indice,
                    "detecciones": [asdict(d) for d in item.detecciones]}, allow_nan=False) + "\n")
                if ctx is not None:
                    mensaje = armar_mensaje(ctx, item.t, item.imagen, item.detecciones, estado)
                    mensaje["calidad"]["fps"] = round(frames / max(time.perf_counter() - inicio, 1e-6), 2)
                    if item.t + 1e-6 >= siguiente_t:
                        muestras.append(mensaje)
                        siguiente_t = (math.floor((item.t + 1e-6) * 5) + 1) / 5
                if item.t >= foto_t:
                    foto = item.imagen.copy()
                    for d in item.detecciones:
                        x1, y1, x2, y2 = (round(v) for v in d.caja)
                        cv2.rectangle(foto, (x1, y1), (x2, y2), (0, 220, 255), 1)
                        cv2.putText(foto, f"{d.clase.value} {d.tid}", (x1, max(12, y1)),
                            cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 220, 255), 1)
                    cv2.putText(foto, f"t={item.t:.3f}s", (12, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 220, 255), 2)
                    if not cv2.imwrite(str(salida / f"cuadro-{item.t:08.3f}.jpg"), foto):
                        raise OSError("No se pudo guardar un cuadro de evidencia")
                    foto_t = item.t + 5
    finally:
        fuente.close()
    duracion = time.perf_counter() - inicio
    if frames == 0:
        raise ValueError("No se decodificaron cuadros para el ensayo")
    resumen = {"modo": "directo_simulado" if simular_directo else "grabacion",
        "video": video.name, "video_sha256": _sha256(video),
        "pesos": str(modelo.config.ruta_pesos), "pesos_sha256": _sha256(Path(modelo.config.ruta_pesos)),
        "clases": modelo.modelo.names, "dispositivo": modelo.dispositivo_inferencia(),
        "dispositivo_configurado": dispositivo,
        "tamano_img": modelo.config.tamano_img, "stride": 1 if simular_directo else stride,
        "cuadros_inferidos": frames, "ultimo_t_s": ultima_t, "tiempo_total_s": round(duracion, 3),
        "cuadros_por_segundo_total": round(frames / duracion, 2),
        "cuadros_con_balon_detectado": balon_detectado, "muestras": len(muestras),
        "muestras_con_calibracion_valida": sum(m["calidad"]["calibracion_valida"] for m in muestras),
        "versiones": _versiones(), "precision_validada": False,
        "nota": "Rendimiento incluye decodificación, inferencia, pipeline y escritura. No mide latencia de red ni mAP/IDF1."}
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (salida / "muestras.json").write_text(json.dumps(muestras, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--pesos", default="yolo11n.pt")
    p.add_argument("--clases", choices=["coco", "futbol", "propio"], default="coco")
    p.add_argument("--calibracion", type=Path)
    p.add_argument("--color-propio", default="#C8102E")
    p.add_argument("--color-rival", default="#17202A")
    p.add_argument("--visitante", action="store_true")
    p.add_argument("--dispositivo", default="cuda:0")
    p.add_argument("--tamano-img", type=int, default=1280)
    p.add_argument("--segundos", type=float, default=30)
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--simular-directo", action="store_true")
    args = p.parse_args()
    if args.tamano_img < 32:
        p.error("--tamano-img debe ser al menos 32")
    logging.basicConfig(level=logging.INFO)
    clases = {"coco": CLASES_COCO, "futbol": CLASES_FUTBOL, "propio": CLASES_PROPIO}[args.clases]
    modelo = ModeloDeteccion(ConfigModelo(ruta_pesos=args.pesos, clases=dict(clases),
        dispositivo=args.dispositivo, tamano_img=args.tamano_img))
    modelo.cargar()
    cal = json.loads(args.calibracion.read_text(encoding="utf-8")) if args.calibracion else None
    resumen = ensayar(modelo, args.video, args.salida, segundos=args.segundos, stride=args.stride,
        simular_directo=args.simular_directo, calibracion=cal, color_propio=args.color_propio,
        color_rival=args.color_rival, es_local=not args.visitante)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
