"""Métricas de bloque por equipo  —  T-076 (CU-46), T-102 (CU-45).

Una muestra por segundo, sobre coordenadas normalizadas con
`normalizar_coordenadas` (CU-31, Jhon): cada equipo ataca hacia +x, así que
«más retrasado» es «menor x» en los dos tiempos, y x es la distancia al arco
propio en metros.

- Arquero: el jugador asignado como ARQ; si no hay, el más retrasado dentro de
  su propia área. Si nadie está en el área, no se excluye a nadie.
- Altura de línea: x media de los 4 jugadores de campo más retrasados, sin el arquero.
- Amplitud (ancho): y máxima - y mínima de los jugadores de campo, es decir, la
  distancia entre los dos jugadores más abiertos.
- Compacidad: área, en m², del polígono envolvente (casco convexo) de los
  jugadores de campo. Menos área = equipo más junto.

Suavizado (CU-45, criterio 3): `retener_ausentes` completa lo que la cámara ve
con la última posición conocida de los jugadores que desaparecieron hace poco,
para que la pérdida transitoria de un defensor no haga saltar la línea.
"""

from dataclasses import dataclass
from math import hypot

from app.analisis.parametros import Parametros
from app.deportivo.schemas import Direccion
from app.partido.service import normalizar_coordenadas


@dataclass(frozen=True, slots=True)
class MuestraBloque:
    altura_linea_m: float | None
    amplitud_m: float | None
    compacidad_m2: float | None
    distancia_centro_m: float | None = None


def area_envolvente(puntos: list[tuple[float, float]]) -> float:
    """Área (m²) del casco convexo de `puntos` (cadena monótona de Andrew + fórmula del área).

    Con menos de 3 puntos distintos, o todos alineados, el polígono no tiene área: 0.
    """
    unicos = sorted(set(puntos))
    if len(unicos) < 3:
        return 0.0

    def giro(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    inferior: list[tuple[float, float]] = []
    for p in unicos:
        while len(inferior) >= 2 and giro(inferior[-2], inferior[-1], p) <= 0:
            inferior.pop()
        inferior.append(p)
    superior: list[tuple[float, float]] = []
    for p in reversed(unicos):
        while len(superior) >= 2 and giro(superior[-2], superior[-1], p) <= 0:
            superior.pop()
        superior.append(p)
    casco = inferior[:-1] + superior[:-1]
    doble_area = sum(casco[i][0] * casco[(i + 1) % len(casco)][1]
                     - casco[(i + 1) % len(casco)][0] * casco[i][1]
                     for i in range(len(casco)))
    return abs(doble_area) / 2


def retener_ausentes(
    visibles: list[tuple[int, float, float]],
    ultimas: dict[int, tuple[float, float, float]],
    equipo_de_track: dict[int, str],
    equipo: str,
    t: float,
    retencion_s: float,
) -> list[tuple[int, float, float]]:
    """`visibles` más los jugadores del equipo vistos hace `retencion_s` o menos y ausentes ahora.

    `ultimas` guarda (t, x, y) crudos de la última vez que se vio cada track. Pasado
    `retencion_s` el jugador deja de contar: ahí la ausencia ya no es transitoria.
    """
    presentes = {tid for tid, _, _ in visibles}
    retenidos = [
        (tid, x, y) for tid, (visto_t, x, y) in ultimas.items()
        if tid not in presentes and equipo_de_track.get(tid) == equipo
        and 0 <= t - visto_t <= retencion_s
    ]
    return visibles + sorted(retenidos)


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
    amplitud = compacidad = distancia_centro = None
    if len(campo) >= 2:
        xs = [n[1] for n in campo]
        ys = [n[2] for n in campo]
        centro_x = sum(xs) / len(campo)
        centro_y = sum(ys) / len(campo)
        coordenadas = list(zip(xs, ys, strict=True))
        amplitud = max(ys) - min(ys)
        compacidad = area_envolvente(coordenadas)
        distancia_centro = sum(hypot(x - centro_x, y - centro_y) for x, y in coordenadas) / len(campo)
    return MuestraBloque(altura, amplitud, compacidad, distancia_centro)
