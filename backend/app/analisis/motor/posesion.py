"""Posesión y pases  —  T-074 (CU-42) y T-076 (CU-46).

Funciones puras sobre una muestra; el estado entre muestras vive en
`DetectorPases`, que no conoce la base ni el reloj.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

from app.analisis.motor.muestras import Muestra
from app.analisis.parametros import Parametros

EQUIPOS_CAMPO = ("LOCAL", "VISITANTE")


class EstadoPosesion(StrEnum):
    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"
    DISPUTA = "DISPUTA"
    SIN_BALON = "SIN_BALON"


@dataclass(frozen=True, slots=True)
class Poseedor:
    estado: EstadoPosesion
    track_id: int | None = None


def poseedor_de(muestra: Muestra, equipos: dict[int, str], p: Parametros) -> Poseedor:
    """CU-42: el jugador de campo más cercano al balón, si está a `radio_posesion_m` o menos.

    - Sin balón visible: SIN_BALON (ese tiempo no se asigna a nadie).
    - Balón lejos de todos: DISPUTA.
    - Árbitros y desconocidos no poseen. El empate se rompe por `track_id`
      para que el resultado no dependa del orden de llegada.
    """
    if muestra.balon is None:
        return Poseedor(EstadoPosesion.SIN_BALON)
    bx, by = muestra.balon
    mejor: tuple[float, int, str] | None = None
    for punto in muestra.jugadores:
        equipo = equipos.get(punto.track_id, punto.equipo)
        if equipo not in EQUIPOS_CAMPO:
            continue
        candidato = (math.hypot(punto.x - bx, punto.y - by), punto.track_id, equipo)
        if mejor is None or candidato[:2] < mejor[:2]:
            mejor = candidato
    if mejor is not None and mejor[0] <= p.radio_posesion_m + 1e-9:
        return Poseedor(EstadoPosesion(mejor[2]), mejor[1])
    return Poseedor(EstadoPosesion.DISPUTA)


@dataclass(frozen=True, slots=True)
class Pase:
    t: float
    equipo: str          # el del que pasa
    origen_track: int
    destino_track: int
    completado: bool     # destino del mismo equipo


@dataclass(slots=True)
class _Tenencia:
    track_id: int
    equipo: str
    t: float                       # última muestra en que lo tuvo
    balon: tuple[float, float]     # dónde estaba el balón en ese momento


class DetectorPases:
    """Pase: el poseedor ESTABLE pasa de A a B (A ≠ B).

    - Estable = `muestras_poseedor_estable` muestras seguidas como poseedor.
    - Entre la última muestra de A y la primera de B puede haber hasta
      `pase_max_hueco_s` de disputa o sin balón.
    - El balón tiene que haber recorrido al menos `pase_min_recorrido_m`: si
      no, es un quite y no un pase.
    - B del mismo equipo: completado. B rival: intentado y no completado.
    """

    def __init__(self, p: Parametros) -> None:
        self.p = p
        self._estable: _Tenencia | None = None
        self._candidato: _Tenencia | None = None   # primera muestra de la racha actual
        self._racha = 0

    @property
    def estable(self) -> tuple[int, str] | None:
        return (self._estable.track_id, self._estable.equipo) if self._estable else None

    def procesar(self, t: float, poseedor: Poseedor, balon: tuple[float, float] | None,
                 equipo: str | None) -> Pase | None:
        if poseedor.track_id is None or balon is None or equipo is None:
            self._candidato, self._racha = None, 0
            return None

        tid = poseedor.track_id
        if self._estable is not None and self._estable.track_id == tid:
            # A sigue con el balón (aunque sea tras una disputa corta).
            self._estable.t, self._estable.balon = t, balon
            self._candidato, self._racha = None, 0
            return None

        if self._candidato is None or self._candidato.track_id != tid:
            self._candidato, self._racha = _Tenencia(tid, equipo, t, balon), 0
        self._racha += 1
        if self._racha < self.p.muestras_poseedor_estable:
            return None

        # B se volvió estable.
        primera_de_b = self._candidato
        anterior = self._estable
        self._estable = _Tenencia(tid, equipo, t, balon)
        self._candidato, self._racha = None, 0
        if anterior is None:
            return None
        hueco = primera_de_b.t - anterior.t
        recorrido = math.hypot(primera_de_b.balon[0] - anterior.balon[0],
                               primera_de_b.balon[1] - anterior.balon[1])
        if hueco > self.p.pase_max_hueco_s + 1e-9 or recorrido < self.p.pase_min_recorrido_m:
            return None
        return Pase(t=t, equipo=anterior.equipo, origen_track=anterior.track_id,
                    destino_track=tid, completado=anterior.equipo == equipo)
