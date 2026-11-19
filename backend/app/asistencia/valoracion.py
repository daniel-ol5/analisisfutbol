"""Valoración y lectura de recomendaciones  —  CU-50, CU-51 (T-090, T-091).

Módulo aparte del motor de reglas (`service.py`, `motor.py`, `contexto.py`, de
Daniel): aquí solo se cambia el estado de una recomendación ya creada.

Qué hace cada valoración (decisión del equipo, T-091):

| Valoración | `util`                         | `estado`    | ¿Sigue activa? |
|------------|--------------------------------|-------------|----------------|
| Útil       | True                           | VISTA       | Sí             |
| No útil    | False                          | DESCARTADA  | No             |
| Aplicada   | True si no se indicó otra cosa | APLICADA    | No             |

Una recomendación se valora una sola vez: la segunda responde 409.
El porcentaje de útiles es útiles / valoradas (las que tienen `util` no nulo).
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.asistencia import models
from app.asistencia.schemas import EstadoRecomendacion, Recomendacion, Valoracion
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Partido


async def _del_club(
    db: AsyncSession, usuario: UsuarioActual, recomendacion_id: int
) -> models.Recomendacion:
    """La recomendación, solo si su partido es del club del usuario (si no, 404)."""
    rec = await db.get(models.Recomendacion, recomendacion_id)
    partido = None
    if rec is not None:
        stmt = del_club(Partido, usuario).where(Partido.id == rec.partido_id)
        partido = (await db.execute(stmt)).scalar_one_or_none()
    verificar_pertenencia(partido, usuario)
    assert rec is not None
    return rec


def _ya_valorada(rec: models.Recomendacion) -> bool:
    return rec.util is not None or rec.estado in (
        EstadoRecomendacion.APLICADA.value, EstadoRecomendacion.DESCARTADA.value)


async def valorar(db: AsyncSession, usuario: UsuarioActual, recomendacion_id: int,
                  datos: Valoracion) -> Recomendacion:
    """CU-51: útil, no útil o aplicada, con comentario opcional."""
    rec = await _del_club(db, usuario, recomendacion_id)
    if _ya_valorada(rec):
        raise HTTPException(status.HTTP_409_CONFLICT, "La recomendación ya fue valorada")
    if not datos.aplicada and datos.util is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Indica si fue útil, no útil o si se aplicó")

    if datos.aplicada:
        rec.estado = EstadoRecomendacion.APLICADA.value
        rec.util = True if datos.util is None else datos.util
    elif datos.util:
        rec.estado = EstadoRecomendacion.VISTA.value
        rec.util = True
    else:
        rec.estado = EstadoRecomendacion.DESCARTADA.value
        rec.util = False
    if rec.vista_en is None:
        rec.vista_en = datetime.now(UTC)   # valorarla implica haberla visto
    rec.comentario = datos.comentario.strip() or None

    await db.commit()
    await db.refresh(rec)
    return Recomendacion.model_validate(rec)


async def marcar_vista(db: AsyncSession, usuario: UsuarioActual,
                       recomendacion_id: int) -> Recomendacion:
    """T-090: el cliente la mostró. Idempotente: no cambia una ya vista o valorada."""
    rec = await _del_club(db, usuario, recomendacion_id)
    if rec.estado == EstadoRecomendacion.PENDIENTE.value:
        rec.estado = EstadoRecomendacion.VISTA.value
    if rec.vista_en is None:
        rec.vista_en = datetime.now(UTC)
    await db.commit()
    await db.refresh(rec)
    return Recomendacion.model_validate(rec)


async def recomendaciones_utiles_pct(db: AsyncSession, partido_id: int) -> float | None:
    """Porcentaje de útiles sobre las valoradas del partido; None si no hay ninguna valorada.

    Para el informe post-partido (CU-55, T-098 de Jhon). Recibe un partido cuya
    pertenencia al club YA se verificó.
    """
    r = models.Recomendacion
    valoradas, utiles = (await db.execute(
        select(func.count(r.util), func.count().filter(r.util.is_(True)))
        .where(r.partido_id == partido_id)
    )).one()
    if not valoradas:
        return None
    return round(100 * utiles / valoradas, 1)
