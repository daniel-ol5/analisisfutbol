"""Métricas de bloque por equipo  —  T-076 (CU-46).

Una muestra por segundo, sobre coordenadas normalizadas con
`normalizar_coordenadas` (CU-31, Jhon): cada equipo ataca hacia +x, así que
«más retrasado» es «menor x» en los dos tiempos.

- Arquero: el jugador asignado como ARQ; si no hay, el más retrasado dentro de
  su propia área. Si nadie está en el área, no se excluye a nadie.
- Altura de línea: x media de los 4 jugadores de campo más retrasados, sin el arquero.
- Amplitud: y máxima - y mínima de los jugadores de campo.
- Compacidad: distancia media de los jugadores de campo a su centroide.
"""

import math
from dataclasses import dataclass

from app.analisis.parametros import Parametros
from app.deportivo.schemas import Direccion
from app.partido.service import normalizar_coordenadas


@dataclass(frozen=True, slots=True)
class MuestraBloque:
    altura_linea_m: float | None
    amplitud_m: float | None
    compacidad_m: float | None


def direccion_de(equipo: str, lado_propio: str, ataca_hacia: str | None) -> str:
    """`ataca_hacia` es del equipo propio en el 1er tiempo; el rival ataca al revés."""
    propia = Direccion(ataca_hacia or Direccion.DERECHA.value)
    if equipo == lado_propio:
        return propia.value
    return (Direccion.IZQUIERDA if propia == Direccion.DERECHA else Direccion.DERECHA).value


def bloque_equipo(
    puntos: list[tuple[int, float, float]],
    arqueros_asignados: set[int],
    *,
    direccion: str,
    parte: int,
    largo_m: float,
    ancho_m: float,
    p: Parametros,
) -> MuestraBloque:
    """`puntos` son (track_id, x, y) crudos de un equipo en un instante."""
    normal = [
        (tid, *normalizar_coordenadas(x, y, largo_m, ancho_m, direccion, parte))
        for tid, x, y in puntos
    ]
    if not normal:
        return MuestraBloque(None, None, None)

    asignados = [n for n in normal if n[0] in arqueros_asignados]
    if asignados:
        arquero = min(asignados, key=lambda n: (n[1], n[0]))
    else:
        medio = ancho_m / 2
        en_area = [n for n in normal
                   if n[1] <= p.area_largo_m and abs(n[2] - medio) <= p.area_ancho_m / 2]
        arquero = min(en_area, key=lambda n: (n[1], n[0])) if en_area else None

    campo = [n for n in normal if n is not arquero]
    altura = None
    if len(campo) >= p.jugadores_linea:
        retrasados = sorted(n[1] for n in campo)[: p.jugadores_linea]
        altura = sum(retrasados) / len(retrasados)
    amplitud = compacidad = None
    if len(campo) >= 2:
        ys = [n[2] for n in campo]
        amplitud = max(ys) - min(ys)
        cx = sum(n[1] for n in campo) / len(campo)
        cy = sum(ys) / len(campo)
        compacidad = sum(math.hypot(n[1] - cx, n[2] - cy) for n in campo) / len(campo)
    return MuestraBloque(altura, amplitud, compacidad)
