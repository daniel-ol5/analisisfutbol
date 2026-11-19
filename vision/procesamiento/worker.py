"""Worker de procesamiento diferido de video  —  CU-27 (T-061).

Corre en la máquina con GPU, como el worker en vivo. Pide trabajos al backend,
descarga el video, corre el pipeline completo (YOLO + ByteTrack, color de
equipo, homografía) y devuelve lotes de `MensajeWorker` con el progreso.

    cd vision
    python -m procesamiento.worker --api http://localhost:8000/api \\
        --email analista@club.com --password ...

La contraseña también se puede pasar en la variable VISION_PASSWORD. Un
usuario ADMIN o ANALISTA del club alcanza: el worker solo toma videos de ese club.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import getpass
import hashlib
import logging
import math
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from calibracion.homografia import cargar_homografia
from seguimiento.tipos import Deteccion

from procesamiento.api import ApiBackend, Cancelado
from procesamiento.fuente import CuadroProcesado
from procesamiento.mensajes import Contexto, EstadoPipeline, armar_mensaje

log = logging.getLogger("procesamiento")

# 25 muestras a 5 por segundo = 5 s de partido por lote, igual que la ingesta.
TAMANO_LOTE = 25
VID_STRIDE = 6

Cuadros = Iterable[CuadroProcesado | tuple[np.ndarray, list[Deteccion]]]


class Backend(Protocol):
    def tomar(self) -> dict[str, Any] | None: ...
    def descargar(self, ruta: str, destino: Path) -> Path: ...
    def resultados(self, video_id: int, progreso_pct: int, muestras: list[dict[str, Any]]) -> None: ...
    def terminar(self, video_id: int, ok: bool, mensaje_error: str | None = None) -> None: ...


def contexto(trabajo: dict[str, Any], fps_muestreo: float) -> Contexto:
    if trabajo.get("modo_calibracion") == "MANUAL" and not trabajo.get("referencia"):
        raise ValueError("La calibración manual anterior no identifica su fuente. "
                         "Vincúlala al video y cuadro en Calibrar cámara antes de procesar")
    return Contexto(
        partido_id=trabajo["partido_id"],
        homografia=cargar_homografia(trabajo["matriz_h"]) if trabajo.get("matriz_h") else None,
        es_local=trabajo["es_local"],
        color_propio=trabajo["color_propio"],
        color_rival=trabajo.get("color_rival"),
        fps_muestreo=fps_muestreo,
        largo_m=trabajo.get("largo_m", 105.0),
        ancho_m=trabajo.get("ancho_m", 68.0),
        modo_calibracion=trabajo.get("modo_calibracion", "MANUAL"),
        referencia=trabajo.get("referencia"),
    )


def procesar_trabajo(
    trabajo: dict[str, Any],
    cuadros: Cuadros,
    backend: Backend,
    fps_video: float,
    total_cuadros: int,
    vid_stride: int = VID_STRIDE,
    tamano_lote: int = TAMANO_LOTE,
    dispositivo: str = "cpu",
) -> int:
    """Procesa todos los cuadros, manda los lotes y cierra. Devuelve las muestras enviadas.

    Si el backend cancela, `backend.resultados` lanza `Cancelado` y se corta
    sin cerrar: el video ya volvió a SUBIDO.
    """
    if not math.isfinite(fps_video) or fps_video <= 0:
        raise ValueError("El video no informa sus cuadros por segundo")
    if vid_stride < 1 or tamano_lote < 1:
        raise ValueError("El salto y el tamaño del lote deben ser positivos")
    ctx = contexto(trabajo, fps_muestreo=5.0)
    video_id = trabajo["video_id"]

    estado = EstadoPipeline(dispositivo=dispositivo, largo_m=ctx.largo_m, ancho_m=ctx.ancho_m,
                            habilitar_reconocimiento=ctx.modo_calibracion == "AUTOMATICA" or bool(ctx.referencia))
    if ctx.modo_calibracion == "AUTOMATICA" and estado.rastreador_homografia.estimador_pitch is None:
        raise ValueError("Instala el modelo de cancha: python -m calibracion.instalar_modelo")
    lote: list[dict[str, Any]] = []
    enviadas = 0

    siguiente_t = 0.0
    indice = 0
    inicio = time.perf_counter()
    hechas = 0
    for i, item in enumerate(cuadros):
        if isinstance(item, CuadroProcesado):
            cuadro, detecciones, t, indice = item.imagen, item.detecciones, item.t, item.indice
        else:  # Adaptadores de pruebas y fuentes antiguas.
            cuadro, detecciones = item
            indice, t = i * vid_stride, i * vid_stride / fps_video
        # Cámara, balón y colores avanzan también entre emisiones.
        mensaje = armar_mensaje(ctx, t, cuadro, detecciones, estado=estado)
        hechas += 1
        mensaje["calidad"]["fps"] = round(hechas / max(time.perf_counter() - inicio, 1e-6), 2)
        if t + 1e-6 < siguiente_t:
            continue
        siguiente_t = (math.floor((t + 1e-6) * 5) + 1) / 5
        lote.append(mensaje)
        if len(lote) >= tamano_lote:
            enviadas += len(lote)
            progreso = min(99, int(100 * (indice + vid_stride) / total_cuadros)) if total_cuadros else 0
            backend.resultados(video_id, progreso, lote)
            lote = []
    if lote:
        enviadas += len(lote)
        progreso = min(99, int(100 * (indice + vid_stride) / total_cuadros)) if total_cuadros else 0
        backend.resultados(video_id, progreso, lote)

    backend.terminar(video_id, ok=True)
    return enviadas


def atender_uno(
    backend: Backend,
    abrir_video: Callable[[dict[str, Any], Path], tuple[Cuadros, float, int]],
    carpeta: Path,
    vid_stride: int = VID_STRIDE,
    dispositivo: str = "cpu",
) -> bool:
    """Toma y procesa un trabajo. Devuelve False si no había ninguno."""
    trabajo = backend.tomar()
    if trabajo is None:
        return False
    video_id = trabajo["video_id"]
    log.info("Video %s (partido %s): %s", video_id, trabajo["partido_id"], trabajo["nombre"])
    ruta = carpeta / f"video-{video_id}{Path(trabajo['nombre']).suffix.lower()}"
    try:
        backend.descargar(trabajo["archivo"], ruta)
        cuadros, fps, total = abrir_video(trabajo, ruta)
        enviadas = procesar_trabajo(trabajo, cuadros, backend, fps, total, vid_stride=vid_stride,
                                   dispositivo=dispositivo)
        log.info("Video %s procesado: %d muestras", video_id, enviadas)
    except Cancelado:
        log.info("Video %s: el procesamiento se canceló", video_id)
    except Exception as e:  # cualquier falla del pipeline se informa al analista
        log.exception("Video %s falló", video_id)
        backend.terminar(video_id, ok=False, mensaje_error=f"{type(e).__name__}: {e}"[:400])
    finally:
        if "cuadros" in locals():
            if hasattr(cuadros, "close"):
                with contextlib.suppress(Exception):
                    cuadros.close()
            del cuadros
        gc.collect()
        with contextlib.suppress(OSError):
            ruta.unlink(missing_ok=True)
    return True


def abrir_con_yolo(dispositivo: str, clases: str, carpeta: Path, vid_stride: int = VID_STRIDE,
                   tamano_img: int = 1280, pesos_locales: Path | None = None):
    """Fábrica de `abrir_video` con el modelo real. Importa ultralytics solo al usarse."""

    def abrir(trabajo: dict[str, Any], ruta: Path) -> tuple[Cuadros, float, int]:
        from deteccion.modelo import (
            _PESOS_FUTBOL,
            CLASES_COCO,
            CLASES_FUTBOL,
            CLASES_PROPIO,
            ConfigModelo,
            ModeloDeteccion,
        )

        from procesamiento.fuente import datos_del_video, seguir_con_cuadros

        modelo = trabajo.get("modelo")
        futbol_local = clases in ("futbol", "auto") and _PESOS_FUTBOL.is_file()
        pesos_coco = _PESOS_FUTBOL.with_name("yolo11n.pt")
        pesos = str(pesos_coco) if pesos_coco.is_file() else "yolo11n.pt"
        if modelo:
            pesos = str(_bajar_pesos(modelo["archivo_url"], carpeta / "modelos"))
        elif pesos_locales is not None:
            pesos = str(pesos_locales)
        elif clases == "propio":
            raise ValueError("Para --clases propio debes registrar y seleccionar un modelo entrenado")
        elif futbol_local:
            pesos = str(_PESOS_FUTBOL)
        elif clases == "futbol":
            log.warning("No hay pesos especializados; se usará COCO con sus clases correctas")

        auto_clases = clases == "auto"
        clases_map = (
            {}
            if auto_clases
            else (
                CLASES_FUTBOL
                if clases == "futbol" and (pesos_locales is not None or modelo or futbol_local)
                else (CLASES_PROPIO if clases == "propio" else CLASES_COCO)
            )
        )
        config = ConfigModelo(
            ruta_pesos=pesos,
            dispositivo=dispositivo,
            clases=dict(clases_map),
            tamano_img=tamano_img,
            auto_clases=auto_clases,
        )
        fps, total = datos_del_video(ruta)
        referencia = trabajo.get("referencia") or {}
        indices = {referencia["cuadro_indice"]} if referencia.get("cuadro_indice") is not None else set()
        return seguir_con_cuadros(ModeloDeteccion(config), ruta, vid_stride, indices_incluir=indices), fps, total

    return abrir


def _bajar_pesos(url: str, carpeta: Path) -> Path:
    """Los pesos del modelo registrado (CU-29), con caché por nombre de archivo."""
    import urllib.request

    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = Path(url.split("?")[0]).name
    destino = carpeta / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}-{nombre}"
    if not destino.exists():
        urllib.request.urlretrieve(url, destino)
    return destino


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Worker de procesamiento diferido de video (T-061)")
    p.add_argument("--api", default="http://localhost:8000/api")
    p.add_argument("--token", default=os.environ.get("VISION_TOKEN"),
                   help="Token JWT de acceso (para ejecución directa desde el backend)")
    p.add_argument("--email", default=None, help="Usuario ADMIN o ANALISTA del club")
    p.add_argument("--password", default=os.environ.get("VISION_PASSWORD"),
                   help="O la variable VISION_PASSWORD")
    p.add_argument("--dispositivo", default="cuda:0", help="cuda:0, o cpu (mucho más lento)")
    p.add_argument("--pesos", type=Path, help="Archivo .pt local para trabajos sin modelo registrado")
    p.add_argument("--clases", choices=["auto", "coco", "propio", "futbol"], default="auto",
                   help="auto: detecta el mapa desde los pesos; futbol (4 clases); propio (3 clases); coco")
    p.add_argument("--espera", type=float, default=10.0, help="Segundos entre consultas sin trabajo")
    p.add_argument("--stride", type=int, default=None,
                   help="Paso de cuadros para el tracker (1 en GPU para máxima continuidad, 6 en CPU)")
    p.add_argument("--tamano-img", type=int, default=1280, help="Tamaño de inferencia; no redimensiona el archivo")
    p.add_argument("--una-vez", action="store_true", help="Procesar como mucho un video y salir")
    args = p.parse_args(argv)
    if args.pesos is not None and not args.pesos.is_file():
        p.error(f"No se encuentra el archivo de pesos: {args.pesos}")
    if not args.token and args.email and not args.password:
        args.password = getpass.getpass("Contraseña del analista: ")
    if not args.token and not (args.email and args.password):
        p.error("Debe especificar --token, o bien --email y --password")
    if (args.stride is not None and args.stride < 1) or args.tamano_img < 32:
        p.error("--stride debe ser positivo y --tamano-img al menos 32")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = argumentos(argv)
    from deteccion.modelo import ConfigModelo, ModeloDeteccion

    efectivo = ModeloDeteccion(ConfigModelo(dispositivo=args.dispositivo)).dispositivo_efectivo()
    if efectivo != args.dispositivo:
        log.warning("%s no está disponible; se usará %s", args.dispositivo, efectivo)
    args.dispositivo = efectivo
    backend = ApiBackend(
        args.api,
        email=args.email or "",
        password=args.password or "",
        token=args.token,
    )
    carpeta = Path(tempfile.gettempdir()) / "areatecnica-worker"
    stride = args.stride if args.stride is not None else (1 if "cuda" in args.dispositivo else VID_STRIDE)
    log.info("Iniciando worker en %s (dispositivo: %s, stride: %d)...", args.api, args.dispositivo, stride)
    abrir = abrir_con_yolo(args.dispositivo, args.clases, carpeta, vid_stride=stride,
                          tamano_img=args.tamano_img, pesos_locales=args.pesos)
    log.info("Esperando videos en %s", args.api)
    while True:
        atendio = atender_uno(backend, abrir, carpeta, vid_stride=stride, dispositivo=args.dispositivo)
        if args.una_vez:
            return 0
        if not atendio:
            time.sleep(args.espera)


if __name__ == "__main__":
    sys.exit(main())
