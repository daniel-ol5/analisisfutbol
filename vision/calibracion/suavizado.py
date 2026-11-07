"""Suavizado de trayectorias  —  CU-26.

Filtrado temporal en metros (ya proyectados por `calibracion.homografia`),
antes de calcular cualquier metrica de distancia recorrida: un jugador
detenido no deberia acumular metros solo por el ruido de deteccion y
proyeccion (que entra en pixeles y se amplifica al pasar a metros).

Un umbral de desplazamiento minimo por si solo no alcanza: una caminata
aleatoria de ruido alrededor de un punto fijo cruza ese umbral todo el
tiempo, en direcciones distintas, y la distancia se sigue acumulando. Por
eso se combina con un promedio exponencial (EMA) que primero estabiliza la
posicion, y el umbral se aplica sobre esa posicion ya suavizada (asi un
jugador detenido no "camina" por el ruido residual que sobrevive al EMA).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PosicionTiempo:
    """Una posicion en metros (ya proyectada por `calibracion.homografia`) con su instante."""

    t: float
    x: float
    y: float


def suavizar_trayectoria(
    posiciones: list[PosicionTiempo],
    alpha: float = 0.2,
    umbral_m: float = 0.2,
) -> list[PosicionTiempo]:
    """Filtra ruido con un promedio exponencial (EMA) mas un umbral de desplazamiento minimo.

    `alpha`: cuanto pesa la posicion nueva sobre la suavizada previa (0-1;
    mas bajo = mas estable pero mas lento siguiendo el movimiento real).
    `umbral_m`: la posicion reportada solo se actualiza si el EMA se alejo
    al menos esto de la ultima posicion reportada; si no, se repite la
    anterior.
    """
    if not posiciones:
        return []

    primera = posiciones[0]
    suavizadas = [primera]
    ema_x, ema_y = primera.x, primera.y
    reportada_x, reportada_y = primera.x, primera.y

    for actual in posiciones[1:]:
        ema_x += alpha * (actual.x - ema_x)
        ema_y += alpha * (actual.y - ema_y)

        desplazamiento = ((ema_x - reportada_x) ** 2 + (ema_y - reportada_y) ** 2) ** 0.5
        if desplazamiento >= umbral_m:
            reportada_x, reportada_y = ema_x, ema_y

        suavizadas.append(PosicionTiempo(t=actual.t, x=reportada_x, y=reportada_y))

    return suavizadas


def distancia_recorrida(posiciones: list[PosicionTiempo]) -> float:
    """Suma de los desplazamientos entre posiciones consecutivas, en metros."""
    total = 0.0
    for anterior, actual in zip(posiciones, posiciones[1:]):
        total += ((actual.x - anterior.x) ** 2 + (actual.y - anterior.y) ** 2) ** 0.5
    return total
