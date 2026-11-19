"""Pruebas de `_adaptar` sin ultralytics ni GPU: se simula un `Results.boxes`
con el mismo contrato (`.xyxy`, `.id`, `.cls`, `.conf`, cada uno con
`.tolist()`), como lo expone un tensor de torch/numpy.
"""

from dataclasses import dataclass

from deteccion.modelo import ConfigModelo
from seguimiento.tipos import Clase
from seguimiento.tracker import _adaptar


class _Tensor:
    def __init__(self, valor):
        self._valor = valor

    def tolist(self):
        return self._valor


@dataclass
class _Cajas:
    xyxy: _Tensor
    id: _Tensor | None
    cls: _Tensor
    conf: _Tensor


@dataclass
class _Resultado:
    boxes: _Cajas | None
    cajas_antes_del_tracker: _Cajas | None = None


def _config(confianza_min: float = 0.3) -> ConfigModelo:
    return ConfigModelo(confianza_min=confianza_min, clases={0: Clase.JUGADOR, 32: Clase.BALON})


def test_sin_cajas_devuelve_lista_vacia():
    assert _adaptar(_Resultado(boxes=None), _config()) == []


def test_sin_ids_todavia_devuelve_lista_vacia():
    cajas = _Cajas(xyxy=_Tensor([[0, 0, 1, 1]]), id=None, cls=_Tensor([0.0]), conf=_Tensor([0.9]))
    assert _adaptar(_Resultado(boxes=cajas), _config()) == []


def test_recupera_balon_original_cuando_el_tracker_lo_descarta():
    originales = _Cajas(
        xyxy=_Tensor([[10, 20, 18, 28], [0, 0, 10, 20], [10, 20, 18, 28], [0, 0, 80, 60]]),
        id=None,
        cls=_Tensor([32, 0, 32, 32]),
        conf=_Tensor([0.7, 0.9, 0.1, 0.8]),
    )
    jugadores = _Cajas(
        xyxy=_Tensor([[0, 0, 10, 20]]), id=_Tensor([7]), cls=_Tensor([0]), conf=_Tensor([0.9])
    )
    detecciones = _adaptar(_Resultado(jugadores, originales), _config())
    assert [(d.tid, d.clase) for d in detecciones] == [(7, Clase.JUGADOR), (-1, Clase.BALON)]
    assert detecciones[1].caja == (10, 20, 18, 28)


def test_filtra_por_confianza_y_por_clase_desconocida():
    cajas = _Cajas(
        xyxy=_Tensor([[0.0, 0.0, 10.0, 20.0], [5.0, 5.0, 15.0, 25.0], [1.0, 1.0, 2.0, 2.0]]),
        id=_Tensor([1.0, 2.0, 3.0]),
        cls=_Tensor([0.0, 32.0, 99.0]),  # jugador, balon, clase desconocida
        conf=_Tensor([0.9, 0.1, 0.95]),  # balon bajo el umbral; clase 99 no esta mapeada
    )

    detecciones = _adaptar(_Resultado(boxes=cajas), _config(confianza_min=0.3))

    assert len(detecciones) == 1
    d = detecciones[0]
    assert d.tid == 1
    assert d.clase is Clase.JUGADOR
    assert d.conf == 0.9
    assert d.caja == (0.0, 0.0, 10.0, 20.0)
    assert d.punto_apoyo == (5.0, 20.0)


def test_descarta_cajas_degeneradas_gigantes_y_duplicados_de_tid():
    # Caja 1: Jugador normal (w=20, h=50) -> ACEPTADA
    # Caja 2: Caja gigante aberrante de tribuna (w=200, h=600) -> DESCARTADA
    # Caja 3: Mismo TID 1 duplicado en el mismo fotograma -> DESCARTADA
    # Caja 4: Balón normal (w=12, h=12) -> ACEPTADA
    cajas = _Cajas(
        xyxy=_Tensor([
            [100.0, 200.0, 120.0, 250.0],
            [50.0, 10.0, 300.0, 700.0],
            [105.0, 202.0, 122.0, 252.0],
            [300.0, 400.0, 312.0, 412.0],
        ]),
        id=_Tensor([1.0, 6.0, 1.0, 99.0]),
        cls=_Tensor([0.0, 0.0, 0.0, 32.0]),
        conf=_Tensor([0.88, 0.75, 0.85, 0.92]),
    )
    # Si el tracker ya entregó el balón, las cajas originales no lo duplican.
    detecciones = _adaptar(_Resultado(cajas, cajas), _config(confianza_min=0.3))
    assert len(detecciones) == 2
    assert [d.tid for d in detecciones] == [1, 99]
    assert detecciones[0].clase == Clase.JUGADOR
    assert detecciones[1].clase == Clase.BALON
