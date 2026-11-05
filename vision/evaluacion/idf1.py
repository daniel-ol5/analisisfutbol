"""IDF1 del seguimiento sobre el clip de referencia  —  Pb-17 (T-055).

IDF1 (identification F1) mide que tan bien se preservan los IDs de
seguimiento entre cuadros: no alcanza con detectar bien (eso lo mide
`evaluacion.mapa.calcular_map50`) si el `tid` de un jugador cambia a mitad
de la jugada, porque eso rompe cualquier metrica de distancia recorrida
(CU-26/CU-28) aunque la caja este bien ubicada en cada cuadro.

Se usa `motmetrics` (ya declarada en requirements.txt, comentario "IDF1 del
seguimiento") en vez de reimplementar el emparejamiento optimo
(Kuhn-Munkres) y la formula de IDF1 a mano: es la libreria de referencia en
el benchmark MOT.

Nota de compatibilidad: `motmetrics` 1.4.0 (la version mas nueva publicada)
usa `np.asfarray` dentro de `motmetrics.distances.iou_matrix`, funcion que
NumPy elimino en la serie 2.0 (y `requirements.txt` ya pide `numpy>=2.1`).
Por eso aqui no se llama a esa funcion: se reimplementa el mismo calculo con
`motmetrics.distances.boxiou` (que si sigue funcionando, sin `asfarray`) en
`_matriz_distancia_iou`.
"""

from __future__ import annotations

from collections.abc import Sequence

import motmetrics as mm
import numpy as np

from evaluacion.mapa import EvaluacionInvalida
from seguimiento.tipos import Clase, Deteccion


def _a_xywh(caja: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Convierte `(x1, y1, x2, y2)` (formato de `Deteccion.caja`) a `(x, y, w, h)` (formato motmetrics)."""
    x1, y1, x2, y2 = caja
    return (x1, y1, x2 - x1, y2 - y1)


def _matriz_distancia_iou(cajas_a: list, cajas_b: list, iou_minimo: float) -> np.ndarray:
    """Equivalente a `motmetrics.distances.iou_matrix`, sin el `np.asfarray` roto en NumPy 2.

    Distancia = 1 - IoU; por encima de `1 - iou_minimo` (es decir, IoU por
    debajo de `iou_minimo`) se marca `np.nan` para que `motmetrics` no
    empareje esa pareja objeto/hipotesis.
    """
    a = np.asarray(cajas_a, dtype=float)
    b = np.asarray(cajas_b, dtype=float)
    if a.size == 0 or b.size == 0:
        return np.empty((0, 0))
    iou = mm.distances.boxiou(a[:, None], b[None, :])
    distancia = 1 - iou
    return np.where(distancia > 1 - iou_minimo, np.nan, distancia)


def calcular_idf1(
    detecciones_por_cuadro: Sequence[Sequence[Deteccion]],
    verdad_por_cuadro: Sequence[Sequence[Deteccion]],
    clase: Clase = Clase.JUGADOR,
    iou_minimo: float = 0.5,
) -> float:
    """IDF1 (0 a 1) de `detecciones_por_cuadro` contra `verdad_por_cuadro`, para una sola `clase`.

    Ambas secuencias tienen un elemento por cuadro del clip, en el mismo
    orden temporal; dentro de cada cuadro, el `tid` de cada deteccion de
    `clase` se empareja con el `tid` de verdad terreno de mayor IoU, siempre
    que sea >= `iou_minimo` (resuelto por Kuhn-Munkres dentro de
    `motmetrics.MOTAccumulator`).

    Lanza `EvaluacionInvalida` si `verdad_por_cuadro` no tiene ninguna caja
    de `clase` en ningun cuadro: igual que en `calcular_map50`, sin eso la
    metrica no esta definida.

    Criterio de aceptacion de T-055: IDF1 >= 0,70 sobre el clip de
    referencia (clip real + anotacion manual de `tid`, fuera del alcance de
    esta funcion: aqui solo se prueba la logica del calculo con datos
    sinteticos).
    """
    if len(detecciones_por_cuadro) != len(verdad_por_cuadro):
        raise ValueError(
            "detecciones_por_cuadro y verdad_por_cuadro deben tener un elemento por cuadro"
        )
    if not any(d.clase == clase for cuadro in verdad_por_cuadro for d in cuadro):
        raise EvaluacionInvalida(
            f"No hay cajas de verdad terreno de clase {clase}: IDF1 no esta definido"
        )

    acumulador = mm.MOTAccumulator(auto_id=True)
    for detecciones, verdad in zip(detecciones_por_cuadro, verdad_por_cuadro, strict=True):
        verdad_clase = [d for d in verdad if d.clase == clase]
        detecciones_clase = [d for d in detecciones if d.clase == clase]

        ids_verdad = [d.tid for d in verdad_clase]
        ids_hipotesis = [d.tid for d in detecciones_clase]
        distancias = _matriz_distancia_iou(
            [_a_xywh(d.caja) for d in verdad_clase],
            [_a_xywh(d.caja) for d in detecciones_clase],
            iou_minimo,
        )
        acumulador.update(ids_verdad, ids_hipotesis, distancias)

    metricas = mm.metrics.create()
    resumen = metricas.compute(acumulador, metrics=["idf1"], name="clip")
    return float(resumen["idf1"].iloc[0])
