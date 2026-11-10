"""Motor de análisis de un partido  —  T-074, T-075, T-076.

Un `MotorPartido` por partido, en memoria, sin base de datos ni reloj: recibe
`Muestra`s ordenadas por `t` y mantiene

- un acumulador por intervalo de 5 minutos (equipos y tracks),
- los totales del partido,
- cubos de 1 s para «los últimos 5 minutos» (ventana móvil).

En vivo lo alimenta el almacén de posiciones (`app/analisis/vivo.py`); para
recalcular se le pasan las filas de `posicion` ordenadas por `t`. Es el MISMO
código en los dos casos: el resultado no puede divergir.

Incremental (CU-46): cuando llega la primera muestra de un intervalo nuevo, el
anterior se cierra y `procesar` lo informa en `Salida.cerrados` para que se
guarde y se difunda en ese momento, no al final del partido.
"""

import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field, fields

from app.analisis.motor.bloque import bloque_equipo, direccion_de
from app.analisis.motor.fisicas import EstadoFisico
from app.analisis.motor.muestras import Muestra
from app.analisis.motor.posesion import (
    EQUIPOS_CAMPO,
    DetectorPases,
    EstadoPosesion,
    Poseedor,
    poseedor_de,
)
from app.analisis.parametros import PARAMETROS, Parametros

# ---------------- Acumuladores ----------------


@dataclass(slots=True)
class AcumEquipo:
    posesion_s: float = 0.0
    pases_intentados: int = 0
    pases_completados: int = 0
    distancia_m: float = 0.0
    suma_altura_m: float = 0.0
    n_altura: int = 0
    suma_amplitud_m: float = 0.0
    suma_compacidad_m: float = 0.0
    n_forma: int = 0

    def sumar(self, otro: "AcumEquipo") -> None:
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(otro, f.name))

    @property
    def altura_linea_m(self) -> float | None:
        return self.suma_altura_m / self.n_altura if self.n_altura else None

    @property
    def amplitud_m(self) -> float | None:
        return self.suma_amplitud_m / self.n_forma if self.n_forma else None

    @property
    def compacidad_m(self) -> float | None:
        return self.suma_compacidad_m / self.n_forma if self.n_forma else None


@dataclass(slots=True)
class AcumTrack:
    equipo: str
    t_desde: float
    t_hasta: float
    tiempo_s: float = 0.0
    distancia_m: float = 0.0
    velocidad_max_ms: float = 0.0
    sprints: int = 0


def _equipos_vacios() -> dict[str, AcumEquipo]:
    return {e: AcumEquipo() for e in EQUIPOS_CAMPO}


@dataclass(slots=True)
class AcumIntervalo:
    indice: int
    t_desde: float | None = None
    t_hasta: float | None = None
    disputa_s: float = 0.0
    equipos: dict[str, AcumEquipo] = field(default_factory=_equipos_vacios)
    tracks: dict[int, AcumTrack] = field(default_factory=dict)
    cerrado: bool = False
    parcial: bool = False

    def ver(self, t: float) -> None:
        if self.t_desde is None or t < self.t_desde:
            self.t_desde = t
        if self.t_hasta is None or t > self.t_hasta:
            self.t_hasta = t

    def sumar_equipos(self, otro: "AcumIntervalo") -> None:
        self.disputa_s += otro.disputa_s
        for e in EQUIPOS_CAMPO:
            self.equipos[e].sumar(otro.equipos[e])


def sumar_intervalos(intervalos: Iterable[AcumIntervalo]) -> AcumIntervalo:
    """Totales de equipo de varios intervalos (los tracks no se suman aquí)."""
    total = AcumIntervalo(indice=-1)
    for intervalo in intervalos:
        total.sumar_equipos(intervalo)
        if intervalo.t_desde is not None:
            total.ver(intervalo.t_desde)
        if intervalo.t_hasta is not None:
            total.ver(intervalo.t_hasta)
    return total


def porcentajes(acum: AcumIntervalo) -> tuple[float, float, float]:
    """(local, visitante, disputa) en %, que suman 100. Sin tiempo con balón: (0, 0, 0)."""
    local = acum.equipos["LOCAL"].posesion_s
    visitante = acum.equipos["VISITANTE"].posesion_s
    total = local + visitante + acum.disputa_s
    if total <= 0:
        return 0.0, 0.0, 0.0
    pct_l = round(100 * local / total, 2)
    pct_v = round(100 * visitante / total, 2)
    return pct_l, pct_v, round(max(0.0, 100 - pct_l - pct_v), 2)


# ---------------- Contexto y salida ----------------


@dataclass(frozen=True, slots=True)
class ContextoPartido:
    partido_id: int
    lado_propio: str = "LOCAL"        # LOCAL si el equipo del club juega de local
    ataca_hacia: str | None = "DER"   # del equipo propio en el 1er tiempo (CU-31)
    largo_m: float = PARAMETROS.largo_cancha_m
    ancho_m: float = PARAMETROS.ancho_cancha_m


@dataclass(frozen=True, slots=True)
class TramoArquero:
    track_id: int
    desde_t: float
    hasta_t: float | None


@dataclass(slots=True)
class Salida:
    cerrados: list[int] = field(default_factory=list)
    corregidos: list[int] = field(default_factory=list)
    nuevo_segundo: bool = False
    nuevo_minuto: bool = False


# ---------------- Motor ----------------


class MotorPartido:
    def __init__(self, contexto: ContextoPartido, p: Parametros = PARAMETROS,
                 arqueros: Iterable[TramoArquero] = ()) -> None:
        self.contexto = contexto
        self.p = p
        self.arqueros = list(arqueros)
        self.intervalos: dict[int, AcumIntervalo] = {}
        self.total = AcumIntervalo(indice=-1)
        self._actual: AcumIntervalo | None = None
        self._cubos: deque[tuple[int, AcumIntervalo]] = deque()
        self._equipos: dict[int, str] = {}
        self._fisicos: dict[int, EstadoFisico] = {}
        self._pases = DetectorPases(p)
        self._poseedor: Poseedor | None = None
        self._t: float | None = None
        self._segundo: int | None = None
        self._minuto: int | None = None

    # ---- consultas ----

    @property
    def t(self) -> float | None:
        return self._t

    @property
    def abierto(self) -> AcumIntervalo | None:
        """El intervalo en curso (todavía no cerrado)."""
        return self._actual if self._actual is not None and not self._actual.cerrado else None

    @property
    def poseedor(self) -> Poseedor | None:
        return self._poseedor

    def equipo_de(self, track_id: int) -> str | None:
        return self._equipos.get(track_id)

    def indice(self, t: float) -> int:
        return int(t // self.p.intervalo_s)

    def ultimos(self, segundos: float | None = None) -> AcumIntervalo:
        """Totales de equipo de la ventana móvil (por defecto, un intervalo: 5 min)."""
        ventana = self.p.intervalo_s if segundos is None else segundos
        if self._t is None:
            return AcumIntervalo(indice=-1)
        desde = math.floor(self._t - ventana)
        return sumar_intervalos(c for s, c in self._cubos if s > desde)

    def actualizar_arqueros(self, tramos: Iterable[TramoArquero]) -> None:
        self.arqueros = list(tramos)

    # ---- acumulación ----

    def _cubo(self, t: float) -> AcumIntervalo:
        segundo = math.floor(t)
        for s, cubo in reversed(self._cubos):
            if s == segundo:
                return cubo
            if s < segundo:
                break
        cubo = AcumIntervalo(indice=segundo)
        self._cubos.append((segundo, cubo))
        return cubo

    def _destinos(self, t: float, intervalo: AcumIntervalo) -> tuple[AcumIntervalo, ...]:
        return (intervalo, self._cubo(t), self.total)

    def _abrir(self, indice: int) -> AcumIntervalo:
        intervalo = AcumIntervalo(indice=indice)
        self.intervalos[indice] = intervalo
        self._actual = intervalo
        return intervalo

    def _sumar_posesion(self, t: float, estado: EstadoPosesion, dt: float) -> None:
        if self._actual is None:
            return
        for destino in self._destinos(t, self._actual):
            if estado == EstadoPosesion.DISPUTA:
                destino.disputa_s += dt
            else:
                destino.equipos[estado.value].posesion_s += dt

    def _arqueros_en(self, t: float) -> set[int]:
        return {
            a.track_id for a in self.arqueros
            if a.desde_t <= t and (a.hasta_t is None or t <= a.hasta_t)
        }

    def _muestra_bloque(self, m: Muestra, intervalo: AcumIntervalo) -> None:
        ctx = self.contexto
        parte = 1 if m.t < self.p.segundos_primer_tiempo else 2
        arqueros = self._arqueros_en(m.t)
        for equipo in EQUIPOS_CAMPO:
            puntos = [(j.track_id, j.x, j.y) for j in m.jugadores
                      if self._equipos.get(j.track_id) == equipo]
            if not puntos:
                continue
            b = bloque_equipo(
                puntos, arqueros,
                direccion=direccion_de(equipo, ctx.lado_propio, ctx.ataca_hacia),
                parte=parte, largo_m=ctx.largo_m, ancho_m=ctx.ancho_m, p=self.p,
            )
            for destino in self._destinos(m.t, intervalo):
                acum = destino.equipos[equipo]
                if b.altura_linea_m is not None:
                    acum.suma_altura_m += b.altura_linea_m
                    acum.n_altura += 1
                if b.amplitud_m is not None and b.compacidad_m is not None:
                    acum.suma_amplitud_m += b.amplitud_m
                    acum.suma_compacidad_m += b.compacidad_m
                    acum.n_forma += 1

    # ---- entrada ----

    def procesar(self, m: Muestra) -> Salida:
        salida = Salida()
        if self._t is not None and m.t <= self._t:
            return salida   # repetida o fuera de orden: se ignora

        # 1. El estado de posesión de la muestra anterior vale hasta esta (máx. 1 s).
        if self._t is not None and self._poseedor is not None \
                and self._poseedor.estado != EstadoPosesion.SIN_BALON:
            self._sumar_posesion(self._t, self._poseedor.estado,
                                 min(m.t - self._t, self.p.max_hueco_s))

        # 2. Intervalo nuevo: se cierra el anterior (CU-46, incremental).
        indice = self.indice(m.t)
        if self._actual is None:
            self._abrir(indice)
        elif indice != self._actual.indice:
            self._actual.cerrado = True
            salida.cerrados.append(self._actual.indice)
            self._abrir(indice)
        intervalo = self._actual
        assert intervalo is not None
        intervalo.ver(m.t)

        # 3. Métricas físicas por track (CU-43).
        for punto in m.jugadores:
            tid = punto.track_id
            equipo = self._equipos.setdefault(tid, punto.equipo)
            fisico = self._fisicos.get(tid)
            if fisico is None:
                fisico = self._fisicos[tid] = EstadoFisico(self.p)
            paso = fisico.procesar(m.t, punto.x, punto.y)

            track = intervalo.tracks.get(tid)
            if track is None:
                track = intervalo.tracks[tid] = AcumTrack(equipo, m.t, m.t)
            track.t_hasta = m.t
            track.tiempo_s += paso.tiempo_s
            track.distancia_m += paso.distancia_m
            if paso.velocidad_ms is not None and paso.velocidad_ms > track.velocidad_max_ms:
                track.velocidad_max_ms = paso.velocidad_ms
            if equipo in EQUIPOS_CAMPO and paso.distancia_m:
                for destino in self._destinos(m.t, intervalo):
                    destino.equipos[equipo].distancia_m += paso.distancia_m

            if paso.sprint_desde_t is not None:
                # Se cuenta en el intervalo donde EMPEZÓ, aunque ya esté cerrado.
                origen = self.intervalos.get(self.indice(paso.sprint_desde_t), intervalo)
                acum = origen.tracks.get(tid)
                if acum is None:
                    acum = origen.tracks[tid] = AcumTrack(equipo, paso.sprint_desde_t,
                                                          paso.sprint_desde_t)
                acum.sprints += 1
                if origen.cerrado and origen.indice not in salida.corregidos:
                    salida.corregidos.append(origen.indice)

        # 4. Posesión de esta muestra y pases (CU-42).
        poseedor = poseedor_de(m, self._equipos, self.p)
        self._poseedor = poseedor
        equipo_poseedor = poseedor.estado.value if poseedor.track_id is not None else None
        pase = self._pases.procesar(m.t, poseedor, m.balon, equipo_poseedor)
        if pase is not None:
            for destino in self._destinos(m.t, intervalo):
                destino.equipos[pase.equipo].pases_intentados += 1
                destino.equipos[pase.equipo].pases_completados += int(pase.completado)

        # 5. Bloque: una muestra por segundo de partido.
        segundo = math.floor(m.t)
        if segundo != self._segundo:
            self._segundo = segundo
            salida.nuevo_segundo = True
            self._muestra_bloque(m, intervalo)
        minuto = math.floor(m.t / 60)
        if minuto != self._minuto:
            self._minuto = minuto
            salida.nuevo_minuto = True

        self._t = m.t
        self.total.ver(m.t)
        limite = segundo - self.p.intervalo_s - 1
        while self._cubos and self._cubos[0][0] < limite:
            self._cubos.popleft()
        return salida

    def cerrar(self) -> int | None:
        """Fin del partido: cierra el intervalo en curso como PARCIAL. Devuelve su índice."""
        if self._actual is None or self._actual.cerrado:
            return None
        self._actual.cerrado = True
        self._actual.parcial = True
        return self._actual.indice


def minutos_de(intervalo: AcumIntervalo, p: Parametros = PARAMETROS) -> tuple[int, int]:
    """(minuto_desde, minuto_hasta). El parcial termina en el minuto de su última muestra."""
    por_intervalo = int(p.intervalo_s // 60)
    desde = intervalo.indice * por_intervalo
    hasta = desde + por_intervalo
    if intervalo.parcial and intervalo.t_hasta is not None:
        hasta = min(hasta, max(desde + 1, math.ceil(intervalo.t_hasta / 60)))
    return desde, hasta
