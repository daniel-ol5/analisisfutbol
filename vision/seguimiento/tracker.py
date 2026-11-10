"""Seguimiento con ByteTrack sobre las detecciones de YOLO  —  CU-24.

ByteTrack viene integrado en ultralytics: `modelo.track(...)` ya lo aplica
por cuadro. Este modulo solo adapta esa salida al tipo `Deteccion` del
proyecto y filtra por confianza y clase (CU-25 reusa estas detecciones para
clasificar el equipo por color de camiseta).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seguimiento.tipos import Clase, Deteccion

_CONFIG_TRACKER_DEFECTO = (
    Path(__file__).parent / "tracker_futbol.yaml"
    if (Path(__file__).parent / "tracker_futbol.yaml").exists()
    else Path(__file__).parent / "bytetrack_futbol.yaml"
)

if TYPE_CHECKING:
    # Solo se usan como anotaciones de tipo (con `from __future__ import
    # annotations` nunca se evaluan en tiempo de ejecucion): importarlas a
    # nivel de modulo crea un ciclo real con `deteccion.modelo`, que a su vez
    # importa `seguimiento.tipos` — ver `deteccion/__init__.py` y
    # `seguimiento/__init__.py`. Ese ciclo solo falla cuando el paquete
    # `deteccion` se importa antes que `seguimiento` en un proceso nuevo (p.
    # ej. un entrypoint real o un script que hace `from deteccion.modelo
    # import ...` primero), por eso la suite de tests no lo detectaba.
    from deteccion.modelo import ConfigModelo, ModeloDeteccion


def seguir(
    modelo: ModeloDeteccion,
    fuente: str,
    vid_stride: int = 6,
    tracker_config: str | Path | None = None,
) -> Iterator[list[Deteccion]]:
    """Un `yield` por cuadro procesado, con la lista de detecciones trackeadas.

    `vid_stride=6` da 5 FPS desde una fuente de 30: es lo que hace posible el
    tiempo real en una laptop (ver vision/README.md). `fuente` es la ruta de
    un video grabado durante el desarrollo, o la URL RTSP de la camara el dia
    de la demostracion: es el mismo pipeline, solo cambia el origen.
    """
    tracker_path = str(tracker_config or (_CONFIG_TRACKER_DEFECTO if _CONFIG_TRACKER_DEFECTO.exists() else "bytetrack.yaml"))
    dispositivo = modelo.dispositivo_efectivo() if hasattr(modelo, "dispositivo_efectivo") else modelo.config.dispositivo
    kwargs: dict[str, Any] = {
        "source": fuente,
        "tracker": tracker_path,
        "vid_stride": vid_stride,
        "conf": modelo.config.confianza_min,
        "iou": modelo.config.iou_nms,
        "device": dispositivo,
        "stream": True,
        "persist": True,
        "verbose": False,
    }
    if hasattr(modelo.config, "tamano_img") and modelo.config.tamano_img:
        kwargs["imgsz"] = modelo.config.tamano_img

    resultados = modelo.modelo.track(**kwargs)
    for resultado in resultados:
        yield _adaptar(resultado, modelo.config)


def _adaptar(resultado: Any, config: ConfigModelo) -> list[Deteccion]:
    """Convierte un `Results` de ultralytics en `list[Deteccion]`.

    Funcion pura (no toca el modelo): se puede probar con un `resultado` de
    prueba, sin ultralytics ni GPU.
    """
    cajas = resultado.boxes
    if cajas is None or cajas.id is None:
        return []

    detecciones = []
    vistos_tid: set[int] = set()
    for caja, tid, clase_id, conf in zip(
        cajas.xyxy.tolist(), cajas.id.tolist(), cajas.cls.tolist(), cajas.conf.tolist(), strict=True
    ):
        clase = config.clases.get(int(clase_id))
        if clase is None or conf < config.confianza_min:
            continue
        x1, y1, x2, y2 = caja
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)

        # Filtro de cordura geométrica: descarta falsos positivos degenerados
        # como vallas publicitarias gigantes, gradas o artefactos de compresión.
        if clase in (Clase.JUGADOR, Clase.PORTERO, Clase.ARBITRO):
            if h < 6.0 or h > 220.0 or w < 3.0 or w > 140.0:
                continue
            if h / max(w, 1.0) < 0.6:  # Un jugador o árbitro no puede ser 2x más ancho que alto
                continue
        elif clase == Clase.BALON:
            if w > 45.0 or h > 45.0 or (w > 0 and h > 0 and (w / h > 2.5 or h / w > 2.5)):
                continue

        tid_int = int(tid)
        # Evitar duplicados del mismo Track ID dentro del mismo fotograma
        if tid_int in vistos_tid:
            continue
        vistos_tid.add(tid_int)

        detecciones.append(Deteccion.desde_caja(tid_int, clase, (x1, y1, x2, y2), float(conf)))
    return detecciones
