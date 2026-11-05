"""mAP@50 de deteccion sobre el clip de referencia  —  Pb-17 (T-055).

T-055 exige "mAP@50 de jugador >= 0,85 [...] sobre el clip de referencia"
para CU-24, pero esa evaluacion (correr el modelo sobre un clip grabado y
anotado a mano, y calcular la metrica) es un trabajo distinto al de
detectar/trackear en vivo: por eso vive en su propio modulo, que
`vision/README.md` ya asigna a Pb-17, no a CU-24.

Se usa `pycocotools` (ya declarada en requirements.txt, comentario
"Evaluacion del modelo") en vez de reimplementar el calculo de AP a mano:
es la libreria de referencia del benchmark COCO y evita errores sutiles en
la integral precision-recall (ver nota de estilo en
`seguimiento/color.py`: preferir `cv2.kmeans`/`cv2.findHomography` ya
probados antes que una formula propia).
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Sequence

from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

from seguimiento.tipos import Clase, Deteccion

_CATEGORIA_ID = 1  # un solo id: cada llamada evalua una sola `Clase` a la vez


class EvaluacionInvalida(ValueError):
    """El clip de referencia no tiene con que evaluar (verdad terreno vacia)."""


def _a_bbox_xywh(caja: tuple[float, float, float, float]) -> list[float]:
    """Convierte `(x1, y1, x2, y2)` (formato de `Deteccion.caja`) a `[x, y, w, h]` (formato COCO)."""
    x1, y1, x2, y2 = caja
    return [x1, y1, x2 - x1, y2 - y1]


def calcular_map50(
    detecciones_por_cuadro: Sequence[Sequence[Deteccion]],
    verdad_por_cuadro: Sequence[Sequence[Deteccion]],
    clase: Clase = Clase.JUGADOR,
) -> float:
    """mAP@IoU=0,50 de `detecciones_por_cuadro` contra `verdad_por_cuadro`, para una sola `clase`.

    Ambas secuencias tienen un elemento (lista de detecciones) por cuadro del
    clip, en el mismo orden; solo se evaluan las cajas de `clase` (jugador o
    balon por separado, nunca mezclados: T-055 pide la metrica "de jugador").

    Devuelve 0.0 si no hay ninguna deteccion (toda la verdad terreno queda
    sin emparejar), pero lanza `EvaluacionInvalida` si no hay ninguna caja de
    verdad terreno de `clase`: sin eso la metrica no esta definida (no hay
    nada contra que comparar), a diferencia de "cero aciertos" que si es un
    resultado valido.

    Criterio de aceptacion de T-055: mAP@50 de jugador >= 0,85 sobre el clip
    de referencia (clip real + anotacion manual, fuera del alcance de esta
    funcion: aqui solo se prueba la logica del calculo con datos sinteticos).
    """
    if len(detecciones_por_cuadro) != len(verdad_por_cuadro):
        raise ValueError(
            "detecciones_por_cuadro y verdad_por_cuadro deben tener un elemento por cuadro"
        )

    imagenes = [{"id": i} for i in range(len(verdad_por_cuadro))]
    categorias = [{"id": _CATEGORIA_ID, "name": str(clase)}]

    anotaciones_verdad = []
    anotaciones_deteccion = []
    for i, (detecciones, verdad) in enumerate(zip(detecciones_por_cuadro, verdad_por_cuadro, strict=True)):
        for d in verdad:
            if d.clase != clase:
                continue
            x, y, w, h = _a_bbox_xywh(d.caja)
            anotaciones_verdad.append({
                "id": len(anotaciones_verdad) + 1,
                "image_id": i,
                "category_id": _CATEGORIA_ID,
                "bbox": [x, y, w, h],
                "area": w * h,
                "iscrowd": 0,
            })
        for d in detecciones:
            if d.clase != clase:
                continue
            x, y, w, h = _a_bbox_xywh(d.caja)
            anotaciones_deteccion.append({
                "id": len(anotaciones_deteccion) + 1,
                "image_id": i,
                "category_id": _CATEGORIA_ID,
                "bbox": [x, y, w, h],
                "area": w * h,  # COCOeval la exige tambien en las detecciones (ver cocoeval.py:evaluateImg)
                "score": d.conf,
            })

    if not anotaciones_verdad:
        raise EvaluacionInvalida(
            f"No hay cajas de verdad terreno de clase {clase}: mAP@50 no esta definido"
        )

    coco_verdad = COCO()
    coco_verdad.dataset = {"images": imagenes, "annotations": anotaciones_verdad, "categories": categorias}
    coco_verdad.createIndex()

    # Se construye el COCO de detecciones a mano (en vez de `coco_verdad.loadRes`,
    # que lanza IndexError con una lista vacia): asi "cero detecciones" entra al
    # mismo camino que cualquier otro resultado y sale en 0.0, no en excepcion.
    coco_deteccion = COCO()
    coco_deteccion.dataset = {
        "images": imagenes,
        "annotations": anotaciones_deteccion,
        "categories": categorias,
    }
    coco_deteccion.createIndex()

    # pycocotools imprime su progreso en stdout por defecto: no aporta nada
    # a la salida de un test y ensucia el reporte de pytest.
    with contextlib.redirect_stdout(io.StringIO()):
        evaluador = COCOeval(coco_verdad, coco_deteccion, iouType="bbox")
        evaluador.evaluate()
        evaluador.accumulate()
        evaluador.summarize()

    return float(evaluador.stats[1])  # stats[1] = AP@IoU=0.50 (ver docs de pycocotools)
