"""Worker en directo: cámara/RTSP o archivo a velocidad real -> /ingesta.

Ejecutar desde vision. La contraseña se pide en terminal o se lee de VISION_PASSWORD.
El pipeline de mensajes, geometría, color y balón es el mismo de worker.py.
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import time
from collections.abc import Iterator
from threading import Condition, Event, Thread
from typing import Any

import cv2
from deteccion.modelo import (
    CLASES_COCO,
    CLASES_FUTBOL,
    CLASES_PROPIO,
    ConfigModelo,
    ModeloDeteccion,
)
from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar

from procesamiento.api import ApiBackend
from procesamiento.mensajes import EstadoPipeline, armar_mensaje
from procesamiento.worker import contexto

log = logging.getLogger("directo")


def cuadros_recientes(fuente: str, simular: bool = False) -> Iterator[tuple[Any, float]]:
    """Un único cuadro pendiente; una GPU lenta no acumula minutos de video.

    La lectura se separa de la inferencia para conservar siempre el más reciente.
    En simulación se respetan los PTS del archivo en lugar de leerlo de golpe.
    """
    cap = cv2.VideoCapture(int(fuente) if fuente.isdecimal() else fuente)
    if not cap.isOpened():
        cap.release()
        raise ValueError("No se pudo abrir la fuente de video")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cond = Condition()
    parar = Event()
    ultimo: list[tuple[Any, float]] = []
    terminado = False
    inicio = time.monotonic()

    def leer() -> None:
        nonlocal terminado
        indice = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        anterior = -1.0
        try:
            while not parar.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if simular:
                    pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    t = pts if pts > anterior else indice / fps
                    if parar.wait(max(0.0, inicio + t - time.monotonic())):
                        break
                    anterior = t
                else:
                    t = time.monotonic() - inicio
                with cond:
                    ultimo[:] = [(frame, t)]
                    cond.notify()
                indice += 1
        finally:
            with cond:
                terminado = True
                cond.notify()
            cap.release()

    hilo = Thread(target=leer, name="captura-vision", daemon=True)
    hilo.start()
    try:
        while True:
            with cond:
                cond.wait_for(lambda: bool(ultimo) or terminado)
                if not ultimo:
                    break
                item = ultimo.pop()
            yield item
    finally:
        parar.set()
        hilo.join(timeout=2)


def configuracion_partido(api: ApiBackend, partido_id: int) -> dict[str, Any]:
    partido = api._json("GET", f"/deportivo/partidos/{partido_id}")
    calibracion = api._json("GET", f"/vision/partidos/{partido_id}/calibracion")
    if calibracion.get("modo") != "AUTOMATICA" and (not calibracion.get("valida") or not calibracion.get("matriz_h")):
        raise ValueError("Calibra el partido antes de iniciar el worker")
    equipo = api._json("GET", f"/deportivo/equipos/{partido['equipo_id']}")
    return {
        "partido_id": partido_id, "matriz_h": calibracion["matriz_h"],
        "largo_m": calibracion["largo_m"], "ancho_m": calibracion["ancho_m"],
        "es_local": partido["es_local"],
        "color_propio": equipo["color_local" if partido["es_local"] else "color_visitante"],
        "modo_calibracion": calibracion.get("modo", "MANUAL"), "referencia": calibracion.get("referencia"),
    }


def conectar_ingesta(api: ApiBackend, partido: int):
    from websockets.sync.client import connect

    token = api._json("POST", f"/partido/{partido}/token-ingesta")["token"]
    url = api.base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    ws = connect(f"{url}/partido/{partido}/ingesta", open_timeout=15, max_size=1_000_000)
    try:
        ws.send(json.dumps({"tipo": "auth", "token": token}))
        if json.loads(ws.recv(timeout=10)).get("tipo") != "listo":
            raise ValueError("La API no aceptó la ingesta")
    except BaseException:
        ws.close()
        raise
    return ws


def main(argv: list[str] | None = None) -> int:
    from websockets.exceptions import ConnectionClosed
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api", default="http://127.0.0.1:8000/api")
    p.add_argument("--email", required=True)
    p.add_argument("--partido", type=int, required=True)
    p.add_argument("--fuente", required=True, help="0, RTSP, HTTP, TCP o ruta de archivo")
    p.add_argument("--pesos", default="yolo11n.pt")
    p.add_argument("--clases", choices=["coco", "futbol", "propio"], default="coco")
    p.add_argument("--color-propio")
    p.add_argument("--color-rival")
    p.add_argument("--dispositivo", default="cpu")
    p.add_argument("--tamano-img", type=int, default=1280)
    p.add_argument("--simular-directo", action="store_true", help="Transmitir un archivo respetando su reloj")
    p.add_argument("--inicio-t", type=float, default=0, help="Segundo de partido al inicio de esta captura")
    p.add_argument("--fuente-id", default="camara-principal", help="Nombre de fuente configurado en la aplicación")
    args = p.parse_args(argv)
    if args.tamano_img < 32 or args.inicio_t < 0:
        p.error("Tamaño de imagen o tiempo inicial inválidos")
    password = os.environ.get("VISION_PASSWORD") or getpass.getpass("Contraseña del analista: ")
    if not password:
        p.error("Debes introducir la contraseña o definir VISION_PASSWORD")
    logging.basicConfig(level=logging.INFO)
    api = ApiBackend(args.api, args.email, password)
    trabajo = configuracion_partido(api, args.partido)
    referencia = trabajo.get("referencia") or {}
    if referencia.get("tipo") == "VIDEO" or (referencia.get("fuente_id") and referencia["fuente_id"] != args.fuente_id):
        raise ValueError("Configura la calibración de este partido para la misma fuente de DIRECTO")
    if trabajo["modo_calibracion"] != "AUTOMATICA":
        raise ValueError("Para una cámara móvil en directo configura reconocimiento automático")
    trabajo["color_rival"] = args.color_rival
    if args.color_propio:
        trabajo["color_propio"] = args.color_propio
    ctx = contexto(trabajo, 5)
    clases = {"coco": CLASES_COCO, "futbol": CLASES_FUTBOL, "propio": CLASES_PROPIO}[args.clases]
    modelo = ModeloDeteccion(ConfigModelo(ruta_pesos=args.pesos, clases=dict(clases),
        dispositivo=args.dispositivo, tamano_img=args.tamano_img))
    modelo.cargar()  # Validar checkpoint antes de abrir cámara o publicar.
    estado = EstadoPipeline(dispositivo=modelo.dispositivo_efectivo(), largo_m=ctx.largo_m,
                            ancho_m=ctx.ancho_m, habilitar_reconocimiento=True)
    if estado.rastreador_homografia.estimador_pitch is None:
        raise ValueError("Instala el modelo de cancha: python -m calibracion.instalar_modelo")
    ws = conectar_ingesta(api, args.partido)
    siguiente = 0.0
    inicio = time.perf_counter()
    frames = 0
    fuente = cuadros_recientes(args.fuente, args.simular_directo)
    try:
        for imagen, t in fuente:
            captura_t = time.perf_counter()
            res = modelo.modelo.track(imagen, tracker=str(_CONFIG_TRACKER_DEFECTO), persist=True,
                imgsz=args.tamano_img, device=modelo.dispositivo_efectivo(),
                conf=modelo.config.confianza_min, iou=modelo.config.iou_nms, verbose=False)[0]
            mensaje = armar_mensaje(ctx, args.inicio_t + t, imagen, _adaptar(res, modelo.config), estado)
            frames += 1
            mensaje["calidad"]["fps"] = round(frames / max(time.perf_counter() - inicio, 1e-6), 2)
            mensaje["calidad"]["retraso_s"] = round(time.perf_counter() - captura_t, 3)
            if t < siguiente:
                continue
            siguiente = t + 0.2
            try:
                ws.send(json.dumps(mensaje))
                try:
                    respuesta = json.loads(ws.recv(timeout=0))
                    if respuesta.get("tipo") == "error":
                        raise ValueError(f"La API rechazó posiciones: {respuesta.get('detalle')}")
                except TimeoutError:
                    pass
            except (OSError, ConnectionError, ConnectionClosed):
                ws.close()
                log.warning("Conexión perdida; reconectando sin reproducir cuadros atrasados")
                ws = conectar_ingesta(api, args.partido)
    finally:
        fuente.close()
        ws.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
