"""Seguimiento con ByteTrack sobre las detecciones de YOLO  —  CU-24.

ByteTrack viene integrado en ultralytics: `modelo.track(...)` ya lo aplica
por cuadro. Este modulo solo adapta esa salida al tipo `Deteccion` del
proyecto y filtra por confianza y clase (CU-25 reusa estas detecciones para
clasificar el equipo por color de camiseta).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from seguimiento.tipos import Deteccion

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
) -> Iterator[list[Deteccion]]:
    """Un `yield` por cuadro procesado, con la lista de detecciones trackeadas.

    `vid_stride=6` da 5 FPS desde una fuente de 30: es lo que hace posible el
    tiempo real en una laptop (ver vision/README.md). `fuente` es la ruta de
    un video grabado durante el desarrollo, o la URL RTSP de la camara el dia
    de la demostracion: es el mismo pipeline, solo cambia el origen.
    """
    resultados = modelo.modelo.track(
        source=fuente,
        tracker="bytetrack.yaml",
        vid_stride=vid_stride,
        stream=True,
        persist=True,
        verbose=False,
    )
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
    for caja, tid, clase_id, conf in zip(
        cajas.xyxy.tolist(), cajas.id.tolist(), cajas.cls.tolist(), cajas.conf.tolist(), strict=True
    ):
        clase = config.clases.get(int(clase_id))
        if clase is None or conf < config.confianza_min:
            continue
        x1, y1, x2, y2 = caja
        detecciones.append(Deteccion.desde_caja(int(tid), clase, (x1, y1, x2, y2), float(conf)))
    return detecciones
