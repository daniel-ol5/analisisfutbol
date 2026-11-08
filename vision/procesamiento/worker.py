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
from procesamiento.api import ApiBackend, Cancelado
from procesamiento.mensajes import Contexto, armar_mensaje
from seguimiento.tipos import Deteccion

log = logging.getLogger("procesamiento")

# 25 muestras a 5 por segundo = 5 s de partido por lote, igual que la ingesta.
TAMANO_LOTE = 25
VID_STRIDE = 6

Cuadros = Iterable[tuple[np.ndarray, list[Deteccion]]]


class Backend(Protocol):
    def tomar(self) -> dict[str, Any] | None: ...
    def descargar(self, ruta: str, destino: Path) -> Path: ...
    def resultados(self, video_id: int, progreso_pct: int, muestras: list[dict[str, Any]]) -> None: ...
    def terminar(self, video_id: int, ok: bool, mensaje_error: str | None = None) -> None: ...


def contexto(trabajo: dict[str, Any], fps_muestreo: float) -> Contexto:
    return Contexto(
        partido_id=trabajo["partido_id"],
        homografia=cargar_homografia(trabajo["matriz_h"]),
        es_local=trabajo["es_local"],
        color_propio=trabajo["color_propio"],
        color_rival=trabajo.get("color_rival"),
        fps_muestreo=fps_muestreo,
    )


def procesar_trabajo(
    trabajo: dict[str, Any],
    cuadros: Cuadros,
    backend: Backend,
    fps_video: float,
    total_cuadros: int,
    vid_stride: int = VID_STRIDE,
    tamano_lote: int = TAMANO_LOTE,
) -> int:
    """Procesa todos los cuadros, manda los lotes y cierra. Devuelve las muestras enviadas.

    Si el backend cancela, `backend.resultados` lanza `Cancelado` y se corta
    sin cerrar: el video ya volvió a SUBIDO.
    """
    if fps_video <= 0:
        raise ValueError("El video no informa sus cuadros por segundo")
    ctx = contexto(trabajo, fps_muestreo=round(fps_video / vid_stride, 2))
    esperadas = max(1, math.ceil(total_cuadros / vid_stride)) if total_cuadros > 0 else None
    video_id = trabajo["video_id"]

    lote: list[dict[str, Any]] = []
    enviadas = 0

    def progreso(hechas: int) -> int:
        if esperadas is None:
            return 0
        return min(99, int(100 * hechas / esperadas))

    for i, (cuadro, detecciones) in enumerate(cuadros):
        t = i * vid_stride / fps_video
        lote.append(armar_mensaje(ctx, t, cuadro, detecciones))
        if len(lote) >= tamano_lote:
            backend.resultados(video_id, progreso(i + 1), lote)
            enviadas += len(lote)
            lote = []
    if lote:
        backend.resultados(video_id, progreso(enviadas + len(lote)), lote)
        enviadas += len(lote)

    backend.terminar(video_id, ok=True)
    return enviadas


def atender_uno(
    backend: Backend,
    abrir_video: Callable[[dict[str, Any], Path], tuple[Cuadros, float, int]],
    carpeta: Path,
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
        enviadas = procesar_trabajo(trabajo, cuadros, backend, fps, total)
        log.info("Video %s procesado: %d muestras", video_id, enviadas)
    except Cancelado:
        log.info("Video %s: el procesamiento se canceló", video_id)
    except Exception as e:  # cualquier falla del pipeline se informa al analista
        log.exception("Video %s falló", video_id)
        backend.terminar(video_id, ok=False, mensaje_error=f"{type(e).__name__}: {e}"[:400])
    finally:
        ruta.unlink(missing_ok=True)
    return True


def abrir_con_yolo(dispositivo: str, clases: str, carpeta: Path):
    """Fábrica de `abrir_video` con el modelo real. Importa ultralytics solo al usarse."""

    def abrir(trabajo: dict[str, Any], ruta: Path) -> tuple[Cuadros, float, int]:
        from deteccion.modelo import CLASES_COCO, CLASES_PROPIO, ConfigModelo, ModeloDeteccion
        from procesamiento.fuente import datos_del_video, seguir_con_cuadros

        modelo = trabajo.get("modelo")
        pesos = "yolo11n.pt"
        if modelo:
            pesos = str(_bajar_pesos(modelo["archivo_url"], carpeta / "modelos"))
        config = ConfigModelo(
            ruta_pesos=pesos,
            dispositivo=dispositivo,
            clases=dict(CLASES_PROPIO if clases == "propio" else CLASES_COCO),
        )
        fps, total = datos_del_video(ruta)
        return seguir_con_cuadros(ModeloDeteccion(config), ruta, VID_STRIDE), fps, total

    return abrir


def _bajar_pesos(url: str, carpeta: Path) -> Path:
    """Los pesos del modelo registrado (CU-29), con caché por nombre de archivo."""
    import urllib.request

    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / Path(url.split("?")[0]).name
    if not destino.exists():
        urllib.request.urlretrieve(url, destino)  # noqa: S310 — https validado al registrar
    return destino


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Worker de procesamiento diferido de video (T-061)")
    p.add_argument("--api", default="http://localhost:8000/api")
    p.add_argument("--email", required=True, help="Usuario ADMIN o ANALISTA del club")
    p.add_argument("--password", default=os.environ.get("VISION_PASSWORD"),
                   help="O la variable VISION_PASSWORD")
    p.add_argument("--dispositivo", default="cuda:0", help="cuda:0, o cpu (mucho más lento)")
    p.add_argument("--clases", choices=["coco", "propio"], default="coco",
                   help="coco: YOLO preentrenado; propio: modelo de 3 clases (CU-29)")
    p.add_argument("--espera", type=float, default=10.0, help="Segundos entre consultas sin trabajo")
    p.add_argument("--una-vez", action="store_true", help="Procesar como mucho un video y salir")
    args = p.parse_args(argv)
    if not args.password:
        p.error("Falta la contraseña: --password o VISION_PASSWORD")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = argumentos(argv)
    backend = ApiBackend(args.api, args.email, args.password)
    carpeta = Path(tempfile.gettempdir()) / "areatecnica-worker"
    abrir = abrir_con_yolo(args.dispositivo, args.clases, carpeta)
    log.info("Esperando videos en %s", args.api)
    while True:
        atendio = atender_uno(backend, abrir, carpeta)
        if args.una_vez:
            return 0
        if not atendio:
            time.sleep(args.espera)


if __name__ == "__main__":
    sys.exit(main())
