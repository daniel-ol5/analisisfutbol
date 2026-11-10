"""Partidos sintéticos y deterministas para las pruebas de métricas (T-074…T-076)."""

import math
import random

from app.analisis.motor.muestras import Muestra, Punto
from app.partido.schemas import MensajeWorker

HZ = 5
PASO = 1 / HZ

# 4-4-2 sencillo. LOCAL ataca hacia +x en el 1er tiempo; tid 1 y 12 son arqueros.
BASE_LOCAL = [(5, 34), (25, 10), (22, 27), (22, 41), (25, 58),
              (45, 12), (42, 28), (42, 40), (45, 56), (65, 28), (65, 40)]
BASE_VISITANTE = [(100, 34), (80, 10), (83, 27), (83, 41), (80, 58),
                  (60, 12), (63, 28), (63, 40), (60, 56), (52, 30), (52, 38)]


def punto(tid: int, equipo: str, x: float, y: float) -> dict:
    return {"tid": tid, "equipo": equipo, "x": x, "y": y, "conf": 0.9}


def mensaje(partido: int, t: float, jugadores: list[dict],
            balon: tuple[float, float] | None) -> MensajeWorker:
    return MensajeWorker.model_validate({
        "partido": partido, "t": round(t, 2), "jugadores": jugadores,
        "balon": ({"tid": 0, "equipo": "DESCONOCIDO", "x": balon[0], "y": balon[1],
                   "conf": 0.7} if balon is not None else None),
        "calidad": {"worker_conectado": True, "fps": 5.0,
                    "jugadores_detectados": len(jugadores),
                    "balon_visible": balon is not None, "retraso_s": 0.2, "degradado": False},
    })


def muestra(t: float, jugadores: list[tuple[int, str, float, float]],
            balon: tuple[float, float] | None) -> Muestra:
    return Muestra(round(t, 2), tuple(Punto(*j) for j in jugadores), balon)


def partido_sintetico(partido: int, desde_s: float, hasta_s: float,
                      semilla: int = 7) -> list[MensajeWorker]:
    """22 jugadores que se mueven, un balón que circula y algún hueco sin balón.

    - Cada 4 s el balón cambia de dueño: 3 s pegado a él y 1 s viajando (disputa).
    - La secuencia de dueños mezcla compañeros y rivales: hay pases completados
      e interceptados.
    - Una muestra de cada 40 llega sin balón.
    - El jugador 7 hace un pique a 8 m/s entre los segundos 20 y 24 de cada minuto.
    """
    rnd = random.Random(semilla)
    dueños = [2, 3, 6, 7, 10, 14, 15, 18, 21, 8, 9, 11, 20, 19, 4, 5]
    mensajes = []
    n0 = round(desde_s * HZ)
    n1 = round(hasta_s * HZ)
    for n in range(n0, n1):
        t = n * PASO
        jugadores = []
        posiciones: dict[int, tuple[float, float]] = {}
        for i, (bx, by) in enumerate(BASE_LOCAL + BASE_VISITANTE):
            tid = i + 1
            equipo = "LOCAL" if tid <= 11 else "VISITANTE"
            x = bx + 3 * math.sin(t / 7 + tid)
            y = by + 2 * math.cos(t / 9 + tid)
            if tid == 7:
                fase = t % 60
                if 20 <= fase < 24:
                    x += 8 * (fase - 20)
                elif 24 <= fase < 28:
                    x += 32 - 8 * (fase - 24)
            x += rnd.gauss(0, 0.05)
            y += rnd.gauss(0, 0.05)
            posiciones[tid] = (x, y)
            jugadores.append(punto(tid, equipo, round(x, 3), round(y, 3)))

        ciclo, fase = divmod(t, 4.0)
        dueño = dueños[int(ciclo) % len(dueños)]
        siguiente = dueños[(int(ciclo) + 1) % len(dueños)]
        if fase < 3.0:
            px, py = posiciones[dueño]
            balon: tuple[float, float] | None = (px + 0.6, py + 0.3)
        else:
            # Viaja en línea recta del dueño al siguiente, lejos de todos a mitad de camino.
            ax, ay = posiciones[dueño]
            bx, by = posiciones[siguiente]
            a = fase - 3.0
            balon = (ax + (bx - ax) * a, ay + (by - ay) * a + 6 * math.sin(math.pi * a))
        if n % 40 == 17:
            balon = None
        mensajes.append(mensaje(partido, t, jugadores,
                                (round(balon[0], 3), round(balon[1], 3)) if balon else None))
    return mensajes
