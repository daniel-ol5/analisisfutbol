"""Evaluación y consulta de recomendaciones tácticas (CU-49)."""

import logging
from collections.abc import Mapping

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.asistencia import models
from app.asistencia.motor import ORDEN_PRIORIDAD, ReglaInvalida, evaluar_regla
from app.asistencia.schemas import EstadoRecomendacion, Prioridad, Recomendacion, Regla
from app.core.deps import UsuarioActual
from app.core.tenancy import verificar_pertenencia
from app.deportivo.models import Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import EventoManual, RelojPartido
from app.partido.schemas import Lado, TipoEventoManual

log = logging.getLogger(__name__)
MAX_RECOMENDACIONES_ACTIVAS = 3


async def _reglas_disponibles(
    db: AsyncSession, club_id: int, activas: bool | None
) -> list[models.ReglaTactica]:
    tabla = models.ReglaTactica
    stmt = select(tabla).where(or_(tabla.club_id.is_(None), tabla.club_id == club_id))
    if activas is not None:
        stmt = stmt.where(tabla.activa.is_(activas))
    return list((await db.scalars(stmt.order_by(tabla.id))).all())


async def listar_reglas(db: AsyncSession, usuario: UsuarioActual, activas: bool | None) -> list[Regla]:
    return [Regla.model_validate(r) for r in await _reglas_disponibles(db, usuario.club_id, activas)]


async def _disciplina(db: AsyncSession, partido: Partido, minuto: int) -> dict[str, float]:
    """Cuenta tarjetas propias registradas y vigentes, incluida una segunda amarilla como roja."""
    equipo = Lado.LOCAL.value if partido.es_local else Lado.VISITANTE.value
    e = EventoManual
    conteos = (await db.execute(
        select(
            func.count().filter(e.tipo == TipoEventoManual.AMARILLA.value, e.minuto >= minuto - 9),
            func.count().filter(e.tipo == TipoEventoManual.ROJA.value),
        ).where(e.club_id == partido.club_id, e.partido_id == partido.id, e.equipo == equipo,
                e.anulado_en.is_(None), e.minuto <= minuto)
    )).one()
    return {"amarillas_propias_10min": conteos[0], "rojas_propias": conteos[1]}


async def evaluar_en_vivo(
    db: AsyncSession, partido_id: int, club_id: int, t: float, observadas: Mapping[str, float]
) -> bool:
    """Evalúa una muestra de estado real. False indica que el reloj está detenido.

    Se bloquea la fila de partido en PostgreSQL para serializar comprobación de
    cooldown, escritura y finalización. La ingesta también serializa el acceso
    al estado táctico de este partido dentro del proceso.
    """
    partido = await db.scalar(
        select(Partido).join(RelojPartido, RelojPartido.partido_id == Partido.id)
        .where(Partido.id == partido_id, Partido.club_id == club_id,
               Partido.estado == EstadoPartido.EN_CURSO.value,
               RelojPartido.club_id == club_id, RelojPartido.en_curso.is_(True))
        .with_for_update(of=Partido)
    )
    if partido is None:
        return False

    reglas = await _reglas_disponibles(db, club_id, activas=True)
    if not reglas:
        return True
    minuto = int(t // 60)
    metricas = {**observadas, **await _disciplina(db, partido, minuto), "minuto": minuto}
    pendientes: list[models.Recomendacion] = []
    for registro in reglas:
        try:
            regla = Regla.model_validate(registro)
            disparo = evaluar_regla(regla, metricas)
        except (ReglaInvalida, ValidationError) as exc:
            log.warning("Regla táctica %s inválida: %s", registro.id, exc)
            continue
        if disparo is not None:
            pendientes.append(models.Recomendacion(
                partido_id=partido.id, regla_id=regla.id, t=t, minuto=minuto,
                mensaje=disparo.mensaje, justificacion=disparo.justificacion,
                datos_soporte=[d.model_dump() for d in disparo.datos_soporte],
                prioridad=regla.prioridad.value,
            ))

    if pendientes:
        r = models.Recomendacion
        cooldown = {regla.id: regla.cooldown_s for regla in reglas}
        filas = (await db.execute(
            select(r.regla_id, func.max(r.t)).where(
                r.partido_id == partido.id, r.regla_id.in_([p.regla_id for p in pendientes]),
            ).group_by(r.regla_id)
        )).all()
        ultimos = {regla_id: ultimo_t for regla_id, ultimo_t in filas}
        db.add_all(p for p in pendientes if t - ultimos.get(p.regla_id, float("-inf")) >= cooldown[p.regla_id])
        await db.commit()
    return True


async def listar_recomendaciones(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, solo_activas: bool
) -> list[Recomendacion]:
    verificar_pertenencia(await db.get(Partido, partido_id), usuario)
    r = models.Recomendacion
    stmt = select(r).where(r.partido_id == partido_id).order_by(r.t.desc(), r.id.desc())
    if solo_activas:
        ids_activas = select(models.ReglaTactica.id).where(models.ReglaTactica.activa.is_(True))
        stmt = stmt.where(r.regla_id.in_(ids_activas))
    filas = (await db.scalars(stmt)).all()
    if not solo_activas:
        return [Recomendacion.model_validate(fila) for fila in filas]

    ultimas: dict[int, models.Recomendacion] = {}
    for fila in filas:
        ultimas.setdefault(fila.regla_id, fila)
    visibles = (
        fila for fila in ultimas.values()
        if fila.estado in (EstadoRecomendacion.PENDIENTE, EstadoRecomendacion.VISTA)
    )
    ordenadas = sorted(visibles, key=lambda f: (ORDEN_PRIORIDAD[Prioridad(f.prioridad)], -f.t, -f.id))
    return [Recomendacion.model_validate(fila) for fila in ordenadas[:MAX_RECOMENDACIONES_ACTIVAS]]
