"""Entrada del motor: una muestra del partido  —  T-074, T-075, T-076.

El motor en vivo y el recálculo reciben exactamente la misma estructura, armada
por una de estas dos funciones:

- `muestra_de_mensaje`: desde un `MensajeWorker` (en vivo).
- `muestras_de_filas`: desde las filas de la tabla `posicion` (recálculo y
  reconstrucción tras un reinicio).

Para que ambos caminos no puedan divergir, `t`, `x` e `y` se redondean a la
precisión de las columnas de `posicion` (2 decimales): en vivo el motor ve lo
mismo que después leerá de la base.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from app.partido.schemas import MensajeWorker

DECIMALES = 2   # Numeric(8,2) para t y Numeric(6,2) para x_m, y_m
DESCONOCIDO = "DESCONOCIDO"


@dataclass(frozen=True, slots=True)
class Punto:
    track_id: int
    equipo: str      # LOCAL | VISITANTE | ARBITRO | DESCONOCIDO
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Muestra:
    t: float
    jugadores: tuple[Punto, ...]
    balon: tuple[float, float] | None


def _r(valor: float) -> float:
    return round(float(valor), DECIMALES)


def muestra_de_mensaje(mensaje: MensajeWorker) -> Muestra:
    balon = mensaje.balon
    return Muestra(
        t=_r(mensaje.t),
        jugadores=tuple(
            Punto(j.tid, j.equipo.value, _r(j.x), _r(j.y)) for j in mensaje.jugadores
        ),
        balon=(_r(balon.x), _r(balon.y)) if balon is not None else None,
    )


@dataclass(frozen=True, slots=True)
class FilaPosicion:
    """Lo que el motor necesita de una fila de `posicion`."""

    t: float
    track_id: int
    x_m: float
    y_m: float
    es_balon: bool


def muestras_de_filas(
    filas: Iterable[FilaPosicion], equipos: Mapping[int, str]
) -> Iterator[Muestra]:
    """Agrupa filas ordenadas por `t` en muestras.

    El equipo de cada track sale de `equipos` (el `equipo_detectado` de
    `asignacion_track`, que es el del primer mensaje: lo mismo que usa el motor
    en vivo). Un track sin registro queda DESCONOCIDO y no participa de la
    posesión ni de las métricas de equipo.
    """
    t_actual: float | None = None
    jugadores: list[Punto] = []
    balon: tuple[float, float] | None = None
    for fila in filas:
        t = _r(fila.t)
        if t_actual is not None and t != t_actual:
            yield Muestra(t_actual, tuple(jugadores), balon)
            jugadores, balon = [], None
        t_actual = t
        if fila.es_balon:
            if balon is None:
                balon = (_r(fila.x_m), _r(fila.y_m))
        else:
            jugadores.append(Punto(fila.track_id, equipos.get(fila.track_id, DESCONOCIDO),
                                   _r(fila.x_m), _r(fila.y_m)))
    if t_actual is not None:
        yield Muestra(t_actual, tuple(jugadores), balon)
