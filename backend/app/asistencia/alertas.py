"""CU-52 (HU-46): alertas de fatiga y de riesgo de expulsión, sin red ni base de datos.

Criterios de HU-46 y de T-095:

- Fatiga: el jugador supera el 120 % del promedio de distancia, o su velocidad
  máxima desciende un 25 % respecto al primer tiempo.
- Riesgo de expulsión: jugador con tarjeta amarilla activa si el partido entra en
  fase de fricción.
- No se genera alerta de fatiga para jugadores que entraron hace menos de 15 minutos.

Cómo se concreta cada uno, con los datos que hay:

- "Distancia" se mide en el último bloque cerrado de 5 minutos y como ritmo
  (m/min sobre el tiempo que estuvo en cancha en ese bloque), para comparar con
  justicia a quien entró o salió a mitad del bloque. El promedio es el de los
  jugadores propios con datos en ese mismo bloque.
- "Velocidad máxima" del último bloque del segundo tiempo contra la mejor del
  primer tiempo del mismo jugador.
- "Fase de fricción": al menos 2 tarjetas (de cualquier equipo) en los últimos
  10 minutos. Es lo que registra el cuerpo técnico; las faltas no se cargan.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.asistencia.motor import ORDEN_PRIORIDAD
from app.asistencia.schemas import Alerta, DatoSoporte, Prioridad, TipoAlerta

FIN_PRIMER_TIEMPO_MIN = 45
UMBRAL_DISTANCIA = 1.20          # 120 % del promedio del equipo
CAIDA_VELOCIDAD = 0.25           # 25 % menos que su máxima del primer tiempo
MINUTOS_MIN_EN_CANCHA = 15       # T-095: antes de esto no hay alerta de fatiga
MINUTOS_MIN_EN_BLOQUE = 2.0      # menos tiempo en el bloque no alcanza para un ritmo fiable
JUGADORES_MIN_PROMEDIO = 3       # el promedio de 1 o 2 jugadores no representa al equipo
VENTANA_FRICCION_MIN = 10
TARJETAS_FRICCION = 2


@dataclass(frozen=True, slots=True)
class Bloque:
    """Métricas físicas de un jugador en un intervalo cerrado de 5 minutos."""

    minuto_desde: int
    minuto_hasta: int
    distancia_m: float
    velocidad_max_kmh: float
    minutos_jugados: float

    @property
    def ritmo_m_min(self) -> float | None:
        if self.minutos_jugados < MINUTOS_MIN_EN_BLOQUE:
            return None
        return self.distancia_m / self.minutos_jugados


@dataclass(frozen=True, slots=True)
class Jugador:
    jugador_id: int
    nombre: str | None = None
    dorsal: int | None = None
    entro_min: int = 0           # 0 para los titulares
    en_cancha: bool = True       # False si fue sustituido o expulsado
    amarillas: int = 0


def _quien(j: Jugador) -> str:
    if j.dorsal is not None and j.nombre:
        return f"#{j.dorsal} {j.nombre}"
    return j.nombre or (f"#{j.dorsal}" if j.dorsal is not None else f"el jugador {j.jugador_id}")


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _ultimo_bloque(bloques: Mapping[int, list[Bloque]]) -> tuple[int, int] | None:
    finales = [(b.minuto_desde, b.minuto_hasta) for lista in bloques.values() for b in lista]
    return max(finales) if finales else None


def alertas_fatiga(
    bloques: Mapping[int, list[Bloque]], jugadores: Mapping[int, Jugador], minuto: int
) -> list[Alerta]:
    """Una alerta por jugador en cancha que cumple al menos uno de los dos criterios."""
    ultimo = _ultimo_bloque(bloques)
    if ultimo is None:
        return []
    del_bloque = {jid: next((b for b in lista if (b.minuto_desde, b.minuto_hasta) == ultimo), None)
                  for jid, lista in bloques.items()}
    ritmos = [b.ritmo_m_min for b in del_bloque.values() if b is not None and b.ritmo_m_min is not None]
    promedio = sum(ritmos) / len(ritmos) if len(ritmos) >= JUGADORES_MIN_PROMEDIO else None

    alertas = []
    for jugador_id, bloque in del_bloque.items():
        jugador = jugadores.get(jugador_id, Jugador(jugador_id))
        if bloque is None or not jugador.en_cancha:
            continue
        if minuto - jugador.entro_min < MINUTOS_MIN_EN_CANCHA:
            continue
        motivos: list[str] = []
        soporte: list[DatoSoporte] = []

        ritmo = bloque.ritmo_m_min
        if promedio and ritmo is not None and ritmo >= UMBRAL_DISTANCIA * promedio:
            motivos.append(f"recorrió {ritmo:.0f} m/min entre el {bloque.minuto_desde}' y el "
                           f"{bloque.minuto_hasta}', el {100 * ritmo / promedio:.0f} % del "
                           f"promedio del equipo ({promedio:.0f} m/min)")
            soporte.append(DatoSoporte(metrica="ritmo_m_min", valor=round(ritmo, 1),
                                       umbral=round(UMBRAL_DISTANCIA * promedio, 1)))

        if bloque.minuto_desde >= FIN_PRIMER_TIEMPO_MIN:
            primer_tiempo = [b.velocidad_max_kmh for b in bloques[jugador_id]
                             if b.minuto_hasta <= FIN_PRIMER_TIEMPO_MIN]
            mejor = max(primer_tiempo, default=0.0)
            if mejor > 0 and bloque.velocidad_max_kmh <= (1 - CAIDA_VELOCIDAD) * mejor:
                caida = 100 * (1 - bloque.velocidad_max_kmh / mejor)
                motivos.append(f"su velocidad máxima bajó a {bloque.velocidad_max_kmh:.1f} km/h, "
                               f"un {caida:.0f} % menos que en el primer tiempo ({mejor:.1f} km/h)")
                soporte.append(DatoSoporte(metrica="velocidad_max_kmh",
                                           valor=bloque.velocidad_max_kmh,
                                           umbral=round((1 - CAIDA_VELOCIDAD) * mejor, 1)))
        if motivos:
            alertas.append(Alerta(
                tipo=TipoAlerta.FATIGA, jugador_id=jugador_id, nombre=jugador.nombre,
                dorsal=jugador.dorsal, minuto=minuto,
                mensaje=f"Vigilar el estado físico de {_quien(jugador)}: considerar el cambio",
                justificacion=_mayuscula(f"{_quien(jugador)} " + " y ".join(motivos) + "."),
                prioridad=Prioridad.MEDIA, datos_soporte=soporte,
            ))
    return alertas


def tarjetas_recientes(tarjetas: Iterable[tuple[str, int]], minuto: int) -> int:
    """Tarjetas (de cualquier equipo) en los últimos 10 minutos, incluido el actual."""
    return sum(1 for _, m in tarjetas if minuto - VENTANA_FRICCION_MIN < m <= minuto)


def alertas_expulsion(
    jugadores: Mapping[int, Jugador], tarjetas_partido: Iterable[tuple[str, int]], minuto: int
) -> list[Alerta]:
    """Amonestados que siguen en cancha, solo si el partido está en fase de fricción."""
    recientes = tarjetas_recientes(tarjetas_partido, minuto)
    if recientes < TARJETAS_FRICCION:
        return []
    return [
        Alerta(
            tipo=TipoAlerta.RIESGO_EXPULSION, jugador_id=j.jugador_id, nombre=j.nombre,
            dorsal=j.dorsal, minuto=minuto,
            mensaje=_mayuscula(f"{_quien(j)} está amonestado: pedirle que evite el contacto"),
            justificacion=f"Tiene amarilla y hubo {recientes} tarjetas en los últimos "
                          f"{VENTANA_FRICCION_MIN} minutos: el partido está en fase de fricción.",
            prioridad=Prioridad.ALTA,
            datos_soporte=[DatoSoporte(metrica="tarjetas_ultimos_10min", valor=recientes,
                                       umbral=TARJETAS_FRICCION)],
        )
        for j in jugadores.values() if j.en_cancha and j.amarillas >= 1
    ]


def ordenar(alertas: Iterable[Alerta]) -> list[Alerta]:
    """Más urgente primero; a igual prioridad, por dorsal."""
    return sorted(alertas, key=lambda a: (ORDEN_PRIORIDAD[a.prioridad],
                                          a.dorsal if a.dorsal is not None else 999, a.jugador_id))
