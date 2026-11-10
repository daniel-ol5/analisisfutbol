"""Suavizado incremental de trayectorias  —  T-075 (CU-43).

RÉPLICA del algoritmo de Alex en `vision/calibracion/suavizado.py`
(`suavizar_trayectoria(posiciones, alpha=0.2, umbral_m=0.2)`): promedio
exponencial (EMA) más un umbral de desplazamiento mínimo aplicado sobre la
posición ya suavizada.

Por qué una réplica y no un import: el backend no puede importar `vision/` en
producción (el Dockerfile solo copia `backend/`, y el paquete `calibracion`
choca con `app.vision.calibracion`). Para que no diverjan,
`tests/test_analisis_suavizado.py` carga el archivo de Alex con importlib y
compara los resultados con los mismos datos. Si Alex cambia su algoritmo, esa
prueba falla y hay que actualizar este archivo.

La diferencia es la forma, no el cálculo: el de Alex recibe la trayectoria
completa; el motor en vivo recibe un punto por vez, así que aquí el estado vive
en un objeto por track.
"""

import math
from collections.abc import Iterable
from itertools import pairwise
from typing import Protocol


class Suavizador(Protocol):
    """Suaviza la trayectoria de UN track, una muestra por vez."""

    def actualizar(self, x: float, y: float) -> tuple[float, float]:
        """Recibe la posición cruda y devuelve la suavizada."""
        ...

    def reiniciar(self, x: float, y: float) -> None:
        """Olvida la historia y arranca en (x, y): se usa tras un salto del tracking."""
        ...


class SuavizadorEMAUmbral:
    """Equivalente incremental de `suavizar_trayectoria` de Alex."""

    def __init__(self, alpha: float = 0.2, umbral_m: float = 0.2) -> None:
        self.alpha = alpha
        self.umbral_m = umbral_m
        self._ema: tuple[float, float] | None = None
        self._reportada: tuple[float, float] = (0.0, 0.0)

    def reiniciar(self, x: float, y: float) -> None:
        self._ema = (x, y)
        self._reportada = (x, y)

    def actualizar(self, x: float, y: float) -> tuple[float, float]:
        if self._ema is None:
            # La primera posición se reporta tal cual, igual que en el original.
            self.reiniciar(x, y)
            return self._reportada

        ema_x, ema_y = self._ema
        ema_x += self.alpha * (x - ema_x)
        ema_y += self.alpha * (y - ema_y)
        self._ema = (ema_x, ema_y)

        rep_x, rep_y = self._reportada
        desplazamiento = ((ema_x - rep_x) ** 2 + (ema_y - rep_y) ** 2) ** 0.5
        if desplazamiento >= self.umbral_m:
            self._reportada = (ema_x, ema_y)
        return self._reportada


def suavizar(
    puntos: Iterable[tuple[float, float, float]],
    alpha: float = 0.2,
    umbral_m: float = 0.2,
) -> list[tuple[float, float, float]]:
    """Versión por lotes, con (t, x, y): la usa la prueba de equivalencia."""
    suavizador = SuavizadorEMAUmbral(alpha, umbral_m)
    salida = []
    for t, x, y in puntos:
        sx, sy = suavizador.actualizar(x, y)
        salida.append((t, sx, sy))
    return salida


def distancia(puntos: list[tuple[float, float, float]]) -> float:
    """Suma de desplazamientos entre puntos consecutivos (t, x, y), en metros."""
    return sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in pairwise(puntos))
