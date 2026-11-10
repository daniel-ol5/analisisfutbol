"""Consultas de métricas  —  T-074 (CU-42), T-075 (CU-43), T-076 (CU-46).

Lo guardado son los intervalos CERRADOS (`metrica_intervalo`,
`metrica_track_intervalo`). Si el partido se está jugando en este proceso, se
suma el intervalo en curso que todavía vive en el motor: así los acumulados
están al día sin esperar al cierre del intervalo.

Las métricas físicas se guardan por track; aquí se convierten a jugador con
las vigencias de `asignacion_track`. Un track sin jugador suma a su equipo pero
no aparece como jugador.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis import persistencia
from app.analisis.motor.motor import (
    AcumIntervalo,
    MotorPartido,
    minutos_de,
    porcentajes,
    sumar_intervalos,
)
from app.analisis.parametros import PARAMETROS
from app.analisis.schemas import (
    Intervalo,
    MetricaEquipo,
    MetricaJugador,
    MetricasJugadorPorIntervalo,
    MetricasPartido,
)
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Jugador, Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import AsignacionTrack
from app.partido.schemas import Lado

MS_A_KMH = 3.6


async def partido_del_club(db: AsyncSession, usuario: UsuarioActual, partido_id: int) -> Partido:
    stmt = del_club(Partido, usuario).where(Partido.id == partido_id)
    return verificar_pertenencia((await db.execute(stmt)).scalar_one_or_none(), usuario)


def motor_en_vivo(partido_id: int) -> MotorPartido | None:
    from app.analisis.vivo import obtener_analisis_en_vivo
    return obtener_analisis_en_vivo().motor(partido_id)


async def _intervalos(db: AsyncSession, partido_id: int, *, con_tracks: bool,
                      motor: MotorPartido | None) -> list[AcumIntervalo]:
    """Los cerrados guardados más, si se pasa el motor en vivo, el intervalo en curso."""
    guardados = await persistencia.intervalos_guardados(db, partido_id, con_tracks=con_tracks)
    abierto = motor.abierto if motor is not None else None
    if abierto is not None:
        guardados = [i for i in guardados if i.indice != abierto.indice] + [abierto]
    return guardados


# ---------------- Equipo (CU-42, CU-46) ----------------


def _r(valor: float | None, decimales: int = 2) -> float | None:
    return round(valor, decimales) if valor is not None else None


def metrica_equipo(acum: AcumIntervalo, lado: Lado) -> MetricaEquipo:
    local, visitante, _ = porcentajes(acum)
    e = acum.equipos[lado.value]
    return MetricaEquipo(
        equipo=lado,
        posesion_pct=local if lado == Lado.LOCAL else visitante,
        pases_intentados=e.pases_intentados,
        pases_completados=e.pases_completados,
        distancia_m=round(e.distancia_m, 1),
        tiros=0,                     # fuera de alcance en S3
        entradas_ultimo_tercio=0,    # fuera de alcance en S3
        altura_linea_m=_r(e.altura_linea_m),
        amplitud_m=_r(e.amplitud_m),
        compacidad_m=_r(e.compacidad_m),
    )


def intervalo_de(acum: AcumIntervalo) -> Intervalo:
    desde, hasta = minutos_de(acum, PARAMETROS)
    return Intervalo(
        minuto_desde=desde, minuto_hasta=hasta,
        local=metrica_equipo(acum, Lado.LOCAL),
        visitante=metrica_equipo(acum, Lado.VISITANTE),
        posesion_disputa_pct=porcentajes(acum)[2],
    )


async def metricas_partido(db: AsyncSession, usuario: UsuarioActual,
                           partido_id: int) -> MetricasPartido:
    """CU-42: acumulado del partido y últimos 5 minutos."""
    partido = await partido_del_club(db, usuario, partido_id)
    motor = motor_en_vivo(partido.id)
    intervalos = await _intervalos(db, partido.id, con_tracks=False, motor=motor)
    total = sumar_intervalos(intervalos)

    if motor is not None and motor.t is not None:
        ultimos: AcumIntervalo | None = motor.ultimos()   # ventana móvil exacta
    else:
        ultimos = intervalos[-1] if intervalos else None  # sin motor: el último intervalo

    return MetricasPartido(
        partido_id=partido.id,
        acumulado_local=metrica_equipo(total, Lado.LOCAL),
        acumulado_visitante=metrica_equipo(total, Lado.VISITANTE),
        ultimos_5_min_local=metrica_equipo(ultimos, Lado.LOCAL) if ultimos else None,
        ultimos_5_min_visitante=metrica_equipo(ultimos, Lado.VISITANTE) if ultimos else None,
        posesion_disputa_pct=porcentajes(total)[2],
    )


async def listar_intervalos(db: AsyncSession, usuario: UsuarioActual,
                            partido_id: int) -> list[Intervalo]:
    """CU-46: solo los intervalos ya cerrados (incluido el último parcial al finalizar)."""
    partido = await partido_del_club(db, usuario, partido_id)
    guardados = await persistencia.intervalos_guardados(db, partido.id)
    return [intervalo_de(i) for i in guardados]


# ---------------- Jugadores (CU-43) ----------------


def _jugador_del_tramo(tramos: list[AsignacionTrack], t_desde: float,
                       t_hasta: float) -> int | None:
    """El jugador del tramo que más se superpone con lo observado del track en el intervalo."""
    mejor: tuple[float, int | None] | None = None
    for tramo in tramos:
        fin = tramo.hasta_t if tramo.hasta_t is not None else float("inf")
        if tramo.desde_t > t_hasta or fin < t_desde:
            continue
        solape = min(fin, t_hasta) - max(tramo.desde_t, t_desde)
        if mejor is None or solape > mejor[0]:
            mejor = (solape, tramo.jugador_id)
    return mejor[1] if mejor is not None else None


@dataclass
class _Fisico:
    equipo: str
    distancia_m: float = 0.0
    velocidad_max_ms: float = 0.0
    sprints: int = 0
    tiempo_s: float = 0.0
    tiempo_por_track: dict[int, float] = field(default_factory=lambda: defaultdict(float))

    def sumar(self, tid: int, distancia: float, vmax: float, sprints: int, tiempo: float) -> None:
        self.distancia_m += distancia
        self.velocidad_max_ms = max(self.velocidad_max_ms, vmax)
        self.sprints += sprints
        self.tiempo_s += tiempo
        self.tiempo_por_track[tid] += tiempo


@dataclass
class _PorJugador:
    total: dict[int, _Fisico]
    por_intervalo: dict[int, dict[int, _Fisico]]   # jugador → intervalo → físico


async def _por_jugador(db: AsyncSession, partido: Partido, intervalos: list[AcumIntervalo],
                       equipo: Lado | None) -> _PorJugador:
    tramos_por_track: dict[int, list[AsignacionTrack]] = defaultdict(list)
    for tramo in await persistencia.tramos_de(db, partido):
        tramos_por_track[tramo.track_id].append(tramo)

    total: dict[int, _Fisico] = {}
    por_intervalo: dict[int, dict[int, _Fisico]] = defaultdict(dict)
    for intervalo in intervalos:
        for tid, t in intervalo.tracks.items():
            if equipo is not None and t.equipo != equipo.value:
                continue
            jugador_id = _jugador_del_tramo(tramos_por_track.get(tid, []), t.t_desde, t.t_hasta)
            if jugador_id is None:
                continue   # sin asignar: suma al equipo, no aparece como jugador
            datos = (tid, t.distancia_m, t.velocidad_max_ms, t.sprints, t.tiempo_s)
            total.setdefault(jugador_id, _Fisico(t.equipo)).sumar(*datos)
            por_intervalo[jugador_id].setdefault(
                intervalo.indice, _Fisico(t.equipo)).sumar(*datos)
    return _PorJugador(total, por_intervalo)


async def _jugadores(db: AsyncSession, ids: Iterable[int], partido: Partido) -> dict[int, Jugador]:
    ids = list(ids)
    if not ids:
        return {}
    stmt = select(Jugador).where(Jugador.club_id == partido.club_id, Jugador.id.in_(ids))
    return {j.id: j for j in (await db.execute(stmt)).scalars().all()}


def _metrica_jugador(jugador_id: int, f: _Fisico, jugador: Jugador | None) -> MetricaJugador:
    track_principal = max(f.tiempo_por_track.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    return MetricaJugador(
        jugador_id=jugador_id,
        track_id=track_principal,
        nombre=f"{jugador.nombre} {jugador.apellido}" if jugador else None,
        dorsal=jugador.dorsal if jugador else None,
        distancia_m=round(f.distancia_m, 1),
        velocidad_max_kmh=round(f.velocidad_max_ms * MS_A_KMH, 1),
        sprints=f.sprints,
        minutos_jugados=round(f.tiempo_s / 60),
    )


async def jugadores_de_partido(db: AsyncSession, partido: Partido, motor: MotorPartido | None,
                               equipo: Lado | None = None) -> list[tuple[str, MetricaJugador]]:
    """(equipo, métrica) por jugador asignado, ordenado por distancia. Sin verificar club."""
    intervalos = await _intervalos(db, partido.id, con_tracks=True, motor=motor)
    datos = await _por_jugador(db, partido, intervalos, equipo)
    fichas = await _jugadores(db, datos.total, partido)
    filas = [(f.equipo, _metrica_jugador(jid, f, fichas.get(jid)))
             for jid, f in datos.total.items()]
    filas.sort(key=lambda par: (-par[1].distancia_m, par[1].jugador_id or 0))
    return filas


def _lado(equipo: str | None) -> Lado | None:
    if equipo is None:
        return None
    try:
        return Lado(equipo.upper())
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "equipo debe ser LOCAL o VISITANTE") from e


async def metricas_jugadores(db: AsyncSession, usuario: UsuarioActual, partido_id: int,
                             equipo: str | None) -> list[MetricaJugador]:
    """CU-43: acumulado por jugador (incluye el intervalo en curso)."""
    lado = _lado(equipo)
    partido = await partido_del_club(db, usuario, partido_id)
    filas = await jugadores_de_partido(db, partido, motor_en_vivo(partido.id), lado)
    return [m for _, m in filas]


async def metricas_jugadores_intervalos(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, equipo: str | None,
) -> list[MetricasJugadorPorIntervalo]:
    """CU-43 + CU-46: por jugador, una entrada por intervalo cerrado."""
    lado = _lado(equipo)
    partido = await partido_del_club(db, usuario, partido_id)
    intervalos = await _intervalos(db, partido.id, con_tracks=True, motor=None)
    por_indice = {i.indice: i for i in intervalos}
    datos = await _por_jugador(db, partido, intervalos, lado)
    respuesta = []
    orden = sorted(datos.total, key=lambda j: (-datos.total[j].distancia_m, j))
    for jugador_id in orden:
        entradas = []
        for indice, f in sorted(datos.por_intervalo[jugador_id].items()):
            desde, hasta = minutos_de(por_indice[indice], PARAMETROS)
            entradas.append({
                "minuto_desde": desde, "minuto_hasta": hasta,
                "distancia_m": round(f.distancia_m, 1),
                "velocidad_max_kmh": round(f.velocidad_max_ms * MS_A_KMH, 1),
                "sprints": f.sprints,
                "minutos_jugados": round(f.tiempo_s / 60, 1),
            })
        respuesta.append(MetricasJugadorPorIntervalo(jugador_id=jugador_id, intervalos=entradas))
    return respuesta


# ---------------- Recalcular (CU-46) ----------------


async def recalcular(db: AsyncSession, usuario: UsuarioActual, partido_id: int) -> MetricasPartido:
    """Borra y vuelve a calcular las métricas pasando las filas de `posicion` por el motor.

    Es el mismo motor que en vivo, así que da lo mismo; sirve tras reasignar
    arqueros, tras procesar un video grabado (CU-27) o si algo falló en vivo.
    No se permite con el partido EN_CURSO: el motor en vivo es el dueño.
    """
    partido = await partido_del_club(db, usuario, partido_id)
    if partido.estado == EstadoPartido.EN_CURSO.value:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No se puede recalcular un partido EN_CURSO: se calcula en vivo")
    motor = await motor_desde_tabla(db, partido)
    motor.cerrar()
    await persistencia.borrar_metricas(db, partido.id)
    await persistencia.guardar_intervalos(db, partido.id, motor.intervalos.values())
    await db.commit()
    return await metricas_partido(db, usuario, partido_id)


async def motor_desde_tabla(db: AsyncSession, partido: Partido) -> MotorPartido:
    """Un motor alimentado con todo lo guardado en `posicion` (recálculo y reconstrucción)."""
    contexto = await persistencia.contexto_de(db, partido)
    tramos = await persistencia.tramos_de(db, partido)
    motor = MotorPartido(contexto, PARAMETROS, await persistencia.arqueros_de(db, partido))
    await persistencia.alimentar(db, motor, partido.id, persistencia.equipos_de(tramos))
    return motor
