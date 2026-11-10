"""Métricas físicas de un track  —  T-075 (CU-43).

Distancia sobre la trayectoria suavizada, velocidad en una ventana de 1 s y
sprints sostenidos. Estado por track, sin base ni reloj.
"""

import math
from collections import deque
from dataclasses import dataclass

from app.analisis.motor.suavizado import Suavizador, SuavizadorEMAUmbral
from app.analisis.parametros import Parametros

_EPS = 1e-6


@dataclass(frozen=True, slots=True)
class PasoFisico:
    distancia_m: float = 0.0
    tiempo_s: float = 0.0
    velocidad_ms: float | None = None
    sprint_desde_t: float | None = None
    """Si en esta muestra se confirmó un sprint, el instante en que empezó."""


class EstadoFisico:
    """Lo que hace falta recordar de un track entre muestras."""

    def __init__(self, p: Parametros, suavizador: Suavizador | None = None) -> None:
        self.p = p
        self.suavizador = suavizador or SuavizadorEMAUmbral(p.suavizado_alpha,
                                                           p.suavizado_umbral_m)
        self._crudo: tuple[float, float, float] | None = None     # t, x, y
        self._suave: tuple[float, float] | None = None
        self._ventana: deque[tuple[float, float, float]] = deque()  # t, x, y suavizados
        self._sprint_desde: float | None = None
        self._sprint_contado = False

    def _reiniciar(self, t: float, x: float, y: float) -> None:
        self.suavizador.reiniciar(x, y)
        self._suave = (x, y)
        self._ventana.clear()
        self._ventana.append((t, x, y))
        self._sprint_desde, self._sprint_contado = None, False

    def procesar(self, t: float, x: float, y: float) -> PasoFisico:
        p = self.p
        if self._crudo is None:
            self._crudo = (t, x, y)
            self._reiniciar(t, x, y)
            return PasoFisico()

        t0, x0, y0 = self._crudo
        self._crudo = (t, x, y)
        dt = t - t0
        tiempo = min(dt, p.max_hueco_s)
        if dt <= 0:
            return PasoFisico()

        if math.hypot(x - x0, y - y0) / dt > p.velocidad_max_valida_ms:
            # Salto del tracking (ID cambiado de persona, reflejo): no son metros
            # corridos. Se reinicia el suavizado en la posición nueva.
            self._reiniciar(t, x, y)
            return PasoFisico(tiempo_s=tiempo)

        sx, sy = self.suavizador.actualizar(x, y)
        px, py = self._suave or (sx, sy)
        self._suave = (sx, sy)
        distancia = math.hypot(sx - px, sy - py)

        self._ventana.append((t, sx, sy))
        while self._ventana and t - self._ventana[0][0] > p.ventana_velocidad_s + _EPS:
            self._ventana.popleft()
        velocidad = None
        ref_t, ref_x, ref_y = self._ventana[0]
        lapso = t - ref_t
        # Con menos de 0,8 s de ventana (inicio o tras un hueco) no se mide.
        if lapso >= 0.8 * p.ventana_velocidad_s - _EPS:
            v = math.hypot(sx - ref_x, sy - ref_y) / lapso
            if v <= p.velocidad_max_valida_ms:
                velocidad = v

        sprint_desde = None
        if velocidad is not None and velocidad > p.umbral_sprint_ms:
            if self._sprint_desde is None:
                self._sprint_desde = t
            if (not self._sprint_contado
                    and t - self._sprint_desde >= p.duracion_min_sprint_s - _EPS):
                self._sprint_contado = True
                sprint_desde = self._sprint_desde
        else:
            self._sprint_desde, self._sprint_contado = None, False

        return PasoFisico(distancia, tiempo, velocidad, sprint_desde)
