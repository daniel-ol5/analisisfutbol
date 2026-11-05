"""Pruebas de Pb-17 (T-055) con datos sinteticos: mAP@50 e IDF1.

No reemplazan la medicion real (eso exige el clip de referencia grabado,
anotado a mano, y el modelo corriendo con GPU — ver `vision/README.md`):
validan que el calculo en si (la integracion con `pycocotools`/
`motmetrics` y la conversion de formato) es correcto, para no descubrir un
bug de esa integracion justo cuando se tenga el clip real.

Criterio de aceptacion de T-055: mAP@50 de jugador >= 0,85 e IDF1 >= 0,70
sobre el clip de referencia.
"""

import pytest

from evaluacion import EvaluacionInvalida, calcular_idf1, calcular_map50
from seguimiento.tipos import Clase, Deteccion


def _deteccion(
    tid: int,
    caja: tuple[float, float, float, float],
    clase: Clase = Clase.JUGADOR,
    conf: float = 0.9,
) -> Deteccion:
    return Deteccion.desde_caja(tid=tid, clase=clase, caja=caja, conf=conf)


# ---------------- calcular_map50 ----------------

def test_map50_es_1_cuando_las_cajas_coinciden_exactamente():
    verdad = [[_deteccion(1, (10, 10, 30, 50)), _deteccion(2, (60, 10, 80, 50))]]
    detecciones = [[_deteccion(1, (10, 10, 30, 50)), _deteccion(2, (60, 10, 80, 50))]]

    assert calcular_map50(detecciones, verdad) == pytest.approx(1.0)


def test_map50_es_0_sin_ninguna_deteccion():
    verdad = [[_deteccion(1, (10, 10, 30, 50))]]
    assert calcular_map50([[]], verdad) == 0.0


def test_map50_baja_con_cajas_mal_ubicadas():
    """Cajas desplazadas lo bastante para no superar IoU=0,5 cuentan como fallo."""
    verdad = [[_deteccion(1, (10, 10, 30, 50))] for _ in range(10)]
    # desplazadas 40px en x: sin solapamiento con una caja de 20px de ancho
    detecciones = [[_deteccion(1, (50, 10, 70, 50))] for _ in range(10)]

    assert calcular_map50(detecciones, verdad) < 0.5


def test_map50_ignora_otras_clases_y_sin_verdad_de_la_clase_pedida_falla():
    verdad = [[_deteccion(1, (10, 10, 30, 50), clase=Clase.BALON)]]
    with pytest.raises(EvaluacionInvalida):
        calcular_map50([[]], verdad, clase=Clase.JUGADOR)


def test_map50_exige_un_cuadro_de_verdad_por_cada_cuadro_de_deteccion():
    with pytest.raises(ValueError):
        calcular_map50([[], []], [[]])


# ---------------- calcular_idf1 ----------------

def _clip_sin_cambios_de_id(n_cuadros: int = 10) -> list[list[Deteccion]]:
    """Dos jugadores que se mueven en linea recta, siempre con el mismo tid."""
    return [
        [
            _deteccion(1, (10.0 + i, 10.0, 30.0 + i, 50.0)),
            _deteccion(2, (60.0 - i, 10.0, 80.0 - i, 50.0)),
        ]
        for i in range(n_cuadros)
    ]


def test_idf1_es_1_cuando_el_seguimiento_no_cambia_de_id():
    verdad = _clip_sin_cambios_de_id()
    assert calcular_idf1(verdad, verdad) == pytest.approx(1.0)


def test_idf1_baja_cuando_el_tracker_intercambia_los_id_a_mitad_del_clip():
    verdad = _clip_sin_cambios_de_id(n_cuadros=10)
    detecciones = [list(cuadro) for cuadro in verdad]
    # a partir del cuadro 5, el tracker confunde a los dos jugadores entre si
    for i in range(5, len(detecciones)):
        a, b = detecciones[i]
        detecciones[i] = [
            Deteccion.desde_caja(tid=2, clase=a.clase, caja=a.caja, conf=a.conf),
            Deteccion.desde_caja(tid=1, clase=b.clase, caja=b.caja, conf=b.conf),
        ]

    assert calcular_idf1(detecciones, verdad) < 1.0


def test_idf1_ignora_otras_clases_y_sin_verdad_de_la_clase_pedida_falla():
    verdad = [[_deteccion(1, (10, 10, 30, 50), clase=Clase.BALON)]]
    with pytest.raises(EvaluacionInvalida):
        calcular_idf1([[]], verdad, clase=Clase.JUGADOR)


def test_idf1_exige_un_cuadro_de_verdad_por_cada_cuadro_de_deteccion():
    with pytest.raises(ValueError):
        calcular_idf1([[], []], [[]])
