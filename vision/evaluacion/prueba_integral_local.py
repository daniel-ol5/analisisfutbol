"""Prueba aislada con API, modelos reales, SQLite y WebSocket; no toca la base del usuario."""
import argparse
import json
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4


def ejecutar(video: Path, salida: Path):
    if salida.exists():
        raise ValueError("Usa una carpeta nueva para este ensayo aislado")
    salida.mkdir(parents=True)
    raiz = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(raiz / "backend"))
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(salida / 'ensayo.db').resolve().as_posix()}"
    os.environ["VIDEOS_DIR"] = str((salida / "videos").resolve())
    os.environ["VISION_AUTO_WORKER"] = "false"
    os.environ["YOLO_CONFIG_DIR"] = str(salida / "ultralytics")
    import torch
    from app.core.database import Base, engine
    from app.main import app
    from app.vision import procesamiento
    from deteccion.modelo import CLASES_COCO, ConfigModelo, ModeloDeteccion
    from procesamiento.directo import cuadros_recientes
    from procesamiento.fuente import datos_del_video, seguir_con_cuadros
    from procesamiento.mensajes import EstadoPipeline, armar_mensaje
    from procesamiento.worker import contexto, procesar_trabajo
    from seguimiento.tracker import _CONFIG_TRACKER_DEFECTO, _adaptar
    from starlette.testclient import TestClient

    torch.set_num_threads(4)
    # Aislar también los JSON de resultados de las rutas históricas de compatibilidad.
    procesamiento._ruta_muestras_video = lambda i: salida / "muestras" / f"video-{i}.json"
    procesamiento._ruta_muestras_partido = lambda i: salida / "muestras" / f"partido-{i}.json"
    procesamiento.guardar_muestras_video = lambda i, m, **kw: procesamiento._guardar_muestras_archivo(procesamiento._ruta_muestras_video(i), m, **kw)
    procesamiento.guardar_muestras_partido = lambda i, m: procesamiento._guardar_muestras_archivo(procesamiento._ruta_muestras_partido(i), m)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(aplicacion):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with original(aplicacion):
            yield

    app.router.lifespan_context = lifespan
    inicio = time.perf_counter()
    informe = {}
    with TestClient(app) as cliente:
        def pedir(metodo, ruta, **kwargs):
            r = cliente.request(metodo, "/api" + ruta, **kwargs)
            if r.status_code >= 400:
                raise RuntimeError(f"{ruta}: HTTP {r.status_code}: {r.text[:500]}")
            return r.json() if r.content else None

        registro = pedir("POST", "/seguridad/registro", json={"nombre_club": "Ensayo aislado",
            "email": f"ensayo-{uuid4().hex[:8]}@example.com", "password": uuid4().hex})
        cliente.headers["Authorization"] = f"Bearer {registro['access_token']}"
        equipo = pedir("POST", "/deportivo/equipos", json={"nombre": "Bayern prueba",
            "color_local": "#C8102E", "color_visitante": "#17202A"})

        def partido(nombre):
            return pedir("POST", "/deportivo/partidos", json={"equipo_id": equipo["id"],
                "rival": nombre, "es_local": True, "sede": "Ensayo",
                "fecha_hora": (datetime.now(UTC) + timedelta(days=1)).isoformat()})["id"]

        pid = partido("Grabación")
        contenido = video.read_bytes()
        v = pedir("POST", f"/vision/partidos/{pid}/videos", json={"nombre": video.name,
            "tipo": "video/mp4", "tamano_bytes": len(contenido)})
        vid = v["id"]
        pedir("PUT", f"/vision/videos/{vid}/contenido", content=contenido,
              headers={"Content-Range": f"bytes 0-{len(contenido)-1}/{len(contenido)}", "Content-Type": "application/octet-stream"})
        pedir("POST", f"/vision/partidos/{pid}/calibracion", json={"modo": "AUTOMATICA",
            "referencia": {"tipo": "VIDEO", "video_id": vid}})
        pedir("POST", f"/vision/videos/{vid}/procesar", json={"color_propio": "#C8102E", "color_rival": "#17202A"})
        trabajo = pedir("POST", "/vision/trabajos/tomar")

        class BackendPrueba:
            def resultados(self, video_id, progreso_pct, muestras):
                pedir("POST", f"/vision/videos/{video_id}/resultados", json={"progreso_pct": progreso_pct, "muestras": muestras})

            def terminar(self, video_id, ok, mensaje_error=None):
                pedir("POST", f"/vision/videos/{video_id}/terminar", json={"ok": ok, "mensaje_error": mensaje_error})

        def nuevo_modelo():
            modelo = ModeloDeteccion(ConfigModelo(ruta_pesos=str(raiz / "vision/pesos/yolo11n.pt"),
                clases=dict(CLASES_COCO), dispositivo="cpu", tamano_img=640))
            modelo.cargar()
            return modelo

        print("Grabación: ejecutando modelos reales y enviando lotes a la API", flush=True)
        modelo = nuevo_modelo()
        fps, total = datos_del_video(video)
        enviadas = procesar_trabajo(trabajo, seguir_con_cuadros(modelo, video, 6), BackendPrueba(), fps, total, dispositivo="cpu")
        estado = pedir("GET", f"/vision/videos/{vid}")
        muestras = pedir("GET", f"/vision/videos/{vid}/muestras")
        assert estado["estado"] == "PROCESADO"
        assert enviadas == len(muestras) and len(muestras) > 0
        assert any(m["jugadores"] for m in muestras)
        informe["grabacion"] = {"estado": estado["estado"], "muestras": len(muestras),
            "muestras_con_referencia": sum(m["calidad"]["calibracion_valida"] for m in muestras)}

        pid_directo = partido("Directo simulado")
        pedir("POST", f"/vision/partidos/{pid_directo}/calibracion", json={"modo": "AUTOMATICA",
            "referencia": {"tipo": "DIRECTO", "fuente_id": "ensayo"}})
        pedir("POST", f"/partido/{pid_directo}/iniciar", json={"ataca_hacia": "DER"})
        token = pedir("POST", f"/partido/{pid_directo}/token-ingesta")["token"]
        modelo = nuevo_modelo()
        trabajo_directo = {**trabajo, "partido_id": pid_directo, "matriz_h": None,
                          "referencia": {"tipo": "DIRECTO", "fuente_id": "ensayo", "tiempo_s": 0}}
        ctx = contexto(trabajo_directo, 5)
        pipeline = EstadoPipeline(habilitar_reconocimiento=True)
        fuente = cuadros_recientes(str(video), simular=True)
        recibidas = validas = 0
        print("Directo: inferencia causal, ingesta WebSocket y suscriptor real de la API", flush=True)
        try:
            with cliente.websocket_connect(f"/api/partido/{pid_directo}/vivo") as visor, cliente.websocket_connect(f"/api/partido/{pid_directo}/ingesta") as ingesta:
                visor.send_json({"tipo": "auth", "token": registro["access_token"]})
                assert visor.receive_json()["tipo"] == "listo"
                ingesta.send_json({"tipo": "auth", "token": token})
                assert ingesta.receive_json()["tipo"] == "listo"
                for imagen, t in fuente:
                    resultado = modelo.modelo.track(imagen, tracker=str(_CONFIG_TRACKER_DEFECTO), persist=True,
                        imgsz=640, device="cpu", verbose=False)[0]
                    m = armar_mensaje(ctx, t, imagen, _adaptar(resultado, modelo.config), pipeline)
                    ingesta.send_json(m)
                    while True:
                        respuesta = visor.receive_json()
                        if respuesta["tipo"] == "posiciones":
                            assert respuesta["datos"]["t"] == m["t"]
                            recibidas += 1
                            validas += bool(respuesta["datos"]["calidad"]["calibracion_valida"])
                            break
        finally:
            fuente.close()
        pedir("POST", f"/partido/{pid_directo}/finalizar")
        assert recibidas > 0 and validas > 0
        informe["directo"] = {"muestras_recibidas_por_websocket": recibidas, "muestras_con_referencia": validas}
        with sqlite3.connect(salida / "ensayo.db") as db:
            informe["posiciones_en_db"] = dict(db.execute("select partido_id, count(*) from posicion group by partido_id").fetchall())
        assert informe["posiciones_en_db"].get(pid, 0) > 0
        assert informe["posiciones_en_db"].get(pid_directo, 0) > 0
    informe["duracion_prueba_s"] = time.perf_counter() - inicio
    informe["limites"] = "CPU local; ASGI y WebSocket en proceso; no mide GPU, red física ni precisión táctica"
    (salida / "informe.json").write_text(json.dumps(informe, indent=2), encoding="utf8")
    return informe


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(ejecutar(args.video.resolve(), args.salida.resolve()), indent=2))
