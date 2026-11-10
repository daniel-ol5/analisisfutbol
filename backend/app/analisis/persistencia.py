"""Lectura y escritura de lo que usa el motor  —  T-074, T-075, T-076.

Compartido por el motor en vivo (`vivo.py`) y el recálculo (`metricas.py`).
Todas las funciones reciben un `partido_id` cuya pertenencia al club YA se
verificó (con `tenancy` en los endpoints; por el token de ingesta en vivo):
las tablas de métricas no tienen `club_id`, cuelgan de `partido`.
"""

from collections.abc import AsyncIterator, Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis.models import MetricaIntervalo, MetricaTrackIntervalo
from app.analisis.motor.motor import (
    AcumEquipo,
    AcumIntervalo,
    AcumTrack,
    ContextoPartido,
    MotorPartido,
    TramoArquero,
    minutos_de,
)
from app.analisis.motor.muestras import FilaPosicion, Muestra, muestras_de_filas
from app.analisis.motor.posesion import EQUIPOS_CAMPO
from app.analisis.parametros import PARAMETROS, Parametros
from app.deportivo.models import Jugador, Partido, Posicion
from app.partido.models import AsignacionTrack
from app.vision.models import Calibracion

LOTE_LECTURA = 5000


async def contexto_de(db: AsyncSession, partido: Partido,
                      p: Parametros = PARAMETROS) -> ContextoPartido:
    """Dirección de ataque, lado propio y medidas reales de la cancha (si hay calibración)."""
    calibracion = (await db.execute(
        select(Calibracion.largo_m, Calibracion.ancho_m)
        .where(Calibracion.club_id == partido.club_id, Calibracion.partido_id == partido.id)
        .order_by(Calibracion.id.desc()).limit(1)
    )).first()
    largo, ancho = (calibracion if calibracion is not None
                    else (p.largo_cancha_m, p.ancho_cancha_m))
    return ContextoPartido(
        partido_id=partido.id,
        lado_propio="LOCAL" if partido.es_local else "VISITANTE",
        ataca_hacia=partido.ataca_hacia,
        largo_m=float(largo), ancho_m=float(ancho),
    )


async def tramos_de(db: AsyncSession, partido: Partido) -> list[AsignacionTrack]:
    stmt = (select(AsignacionTrack)
            .where(AsignacionTrack.club_id == partido.club_id,
                   AsignacionTrack.partido_id == partido.id)
            .order_by(AsignacionTrack.track_id, AsignacionTrack.desde_t, AsignacionTrack.id))
    return list((await db.execute(stmt)).scalars().all())


def equipos_de(tramos: Iterable[AsignacionTrack]) -> dict[int, str]:
    """El equipo de cada track: el de su primer tramo (= el de su primer mensaje)."""
    equipos: dict[int, str] = {}
    for tramo in sorted(tramos, key=lambda a: (a.desde_t, a.id)):
        equipos.setdefault(tramo.track_id, tramo.equipo_detectado)
    return equipos


async def arqueros_de(db: AsyncSession, partido: Partido) -> list[TramoArquero]:
    """Tramos de `asignacion_track` cuyo jugador es arquero (ARQ)."""
    stmt = (select(AsignacionTrack.track_id, AsignacionTrack.desde_t, AsignacionTrack.hasta_t)
            .join(Jugador, Jugador.id == AsignacionTrack.jugador_id)
            .where(AsignacionTrack.club_id == partido.club_id,
                   AsignacionTrack.partido_id == partido.id,
                   Jugador.posicion == "ARQ"))
    return [TramoArquero(tid, float(d), float(h) if h is not None else None)
            for tid, d, h in (await db.execute(stmt)).all()]


async def muestras_de(db: AsyncSession, partido_id: int,
                      equipos: dict[int, str]) -> AsyncIterator[Muestra]:
    """Las filas de `posicion` del partido, ordenadas por `t`, como muestras del motor."""
    stmt = (select(Posicion.t, Posicion.track_id, Posicion.x_m, Posicion.y_m, Posicion.es_balon)
            .where(Posicion.partido_id == partido_id)
            .order_by(Posicion.t, Posicion.id))
    resultado = await db.stream(stmt.execution_options(yield_per=LOTE_LECTURA))

    async def filas() -> AsyncIterator[FilaPosicion]:
        async for t, tid, x, y, es_balon in resultado:
            yield FilaPosicion(float(t), tid, float(x), float(y), bool(es_balon))

    # `muestras_de_filas` es síncrona: se le pasan las filas de a lotes.
    pendientes: list[FilaPosicion] = []
    async for fila in filas():
        if pendientes and fila.t != pendientes[-1].t and len(pendientes) >= LOTE_LECTURA:
            for muestra in muestras_de_filas(pendientes, equipos):
                yield muestra
            pendientes = []
        pendientes.append(fila)
    for muestra in muestras_de_filas(pendientes, equipos):
        yield muestra


async def alimentar(db: AsyncSession, motor: MotorPartido, partido_id: int,
                    equipos: dict[int, str]) -> None:
    """Pasa por el motor todas las posiciones guardadas del partido."""
    async for muestra in muestras_de(db, partido_id, equipos):
        motor.procesar(muestra)


# ---------------- Escritura ----------------


def _filas_intervalo(partido_id: int, intervalo: AcumIntervalo,
                     p: Parametros) -> tuple[list[dict], list[dict]]:
    desde, hasta = minutos_de(intervalo, p)
    t_desde = intervalo.t_desde if intervalo.t_desde is not None else 0.0
    t_hasta = intervalo.t_hasta if intervalo.t_hasta is not None else t_desde
    equipos = [
        {"partido_id": partido_id, "intervalo": intervalo.indice, "equipo": equipo,
         "minuto_desde": desde, "minuto_hasta": hasta, "t_desde": t_desde, "t_hasta": t_hasta,
         "parcial": intervalo.parcial, "disputa_s": intervalo.disputa_s,
         **{campo: getattr(acum, campo) for campo in AcumEquipo.__slots__}}
        for equipo, acum in intervalo.equipos.items()
    ]
    tracks = [
        {"partido_id": partido_id, "intervalo": intervalo.indice, "track_id": tid,
         "equipo": t.equipo, "t_desde": t.t_desde, "t_hasta": t.t_hasta,
         "tiempo_s": t.tiempo_s, "distancia_m": t.distancia_m,
         "velocidad_max_ms": t.velocidad_max_ms, "sprints": t.sprints}
        for tid, t in intervalo.tracks.items()
    ]
    return equipos, tracks


async def guardar_intervalos(db: AsyncSession, partido_id: int,
                             intervalos: Iterable[AcumIntervalo],
                             p: Parametros = PARAMETROS) -> None:
    """Reemplaza las filas de esos intervalos (borrar + insertar: igual en SQLite y PostgreSQL)."""
    intervalos = list(intervalos)
    if not intervalos:
        return
    indices = [i.indice for i in intervalos]
    for modelo in (MetricaIntervalo, MetricaTrackIntervalo):
        await db.execute(delete(modelo).where(modelo.partido_id == partido_id,
                                              modelo.intervalo.in_(indices)))
    filas_equipo: list[dict] = []
    filas_track: list[dict] = []
    for intervalo in intervalos:
        e, t = _filas_intervalo(partido_id, intervalo, p)
        filas_equipo += e
        filas_track += t
    await db.execute(insert(MetricaIntervalo), filas_equipo)
    if filas_track:
        await db.execute(insert(MetricaTrackIntervalo), filas_track)


async def borrar_metricas(db: AsyncSession, partido_id: int) -> None:
    for modelo in (MetricaIntervalo, MetricaTrackIntervalo):
        await db.execute(delete(modelo).where(modelo.partido_id == partido_id))


# ---------------- Lectura de lo guardado ----------------


async def intervalos_guardados(db: AsyncSession, partido_id: int, *,
                               con_tracks: bool = False) -> list[AcumIntervalo]:
    """Los intervalos cerrados del partido, como acumuladores del motor."""
    filas = (await db.execute(
        select(MetricaIntervalo).where(MetricaIntervalo.partido_id == partido_id)
        .order_by(MetricaIntervalo.intervalo, MetricaIntervalo.equipo)
    )).scalars().all()
    por_indice: dict[int, AcumIntervalo] = {}
    for f in filas:
        acum = por_indice.get(f.intervalo)
        if acum is None:
            acum = por_indice[f.intervalo] = AcumIntervalo(
                indice=f.intervalo, t_desde=f.t_desde, t_hasta=f.t_hasta,
                disputa_s=f.disputa_s, cerrado=True, parcial=f.parcial)
        if f.equipo in EQUIPOS_CAMPO:
            acum.equipos[f.equipo] = AcumEquipo(
                **{campo: getattr(f, campo) for campo in AcumEquipo.__slots__})

    if con_tracks:
        tracks = (await db.execute(
            select(MetricaTrackIntervalo).where(MetricaTrackIntervalo.partido_id == partido_id)
        )).scalars().all()
        for t in tracks:
            acum = por_indice.get(t.intervalo)
            if acum is not None:
                acum.tracks[t.track_id] = AcumTrack(
                    equipo=t.equipo, t_desde=t.t_desde, t_hasta=t.t_hasta,
                    tiempo_s=t.tiempo_s, distancia_m=t.distancia_m,
                    velocidad_max_ms=t.velocidad_max_ms, sprints=t.sprints)
    return [por_indice[i] for i in sorted(por_indice)]
