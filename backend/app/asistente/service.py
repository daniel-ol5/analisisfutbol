"""Lógica del asistente de uso: progreso, límite diario y preguntas a la IA."""

import json
import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.asistente.models import ConsultaAsistente
from app.asistente.progreso import calcular_progreso
from app.asistente.prompt import construir_mensajes
from app.asistente.proveedor import ErrorProveedorIA, ProveedorIA
from app.asistente.rutas import ruta_valida
from app.asistente.schemas import Accion, Plataforma, Pregunta, Progreso, Respuesta
from app.core.config import settings
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club
from app.deportivo.models import Partido

log = logging.getLogger(__name__)

MAX_ACCIONES = 3
NO_DISPONIBLE = (
    "El asistente no está disponible en este momento. Inténtalo más tarde; "
    "mientras tanto puedes seguir los pasos de «Tu progreso»."
)


async def progreso(db: AsyncSession, usuario: UsuarioActual, plataforma: Plataforma) -> Progreso:
    return await calcular_progreso(db, usuario, plataforma, settings.asistente_activo)


def _hoy():
    return datetime.now(UTC).date()


async def _usadas_hoy(db: AsyncSession, usuario: UsuarioActual) -> int:
    stmt = select(ConsultaAsistente.cantidad).where(
        ConsultaAsistente.club_id == usuario.club_id,
        ConsultaAsistente.usuario_id == usuario.id,
        ConsultaAsistente.fecha == _hoy(),
    )
    return (await db.execute(stmt)).scalar_one_or_none() or 0


async def _contar_pregunta(db: AsyncSession, usuario: UsuarioActual) -> None:
    stmt = insert(ConsultaAsistente).values(
        club_id=usuario.club_id, usuario_id=usuario.id, fecha=_hoy(), cantidad=1
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_consulta_asistente_usuario_fecha",
        set_={"cantidad": ConsultaAsistente.cantidad + 1},
    )
    await db.execute(stmt)
    await db.commit()


async def _partidos_del_club(db: AsyncSession, usuario: UsuarioActual) -> set[int]:
    stmt = del_club(Partido, usuario).with_only_columns(Partido.id)
    return set((await db.execute(stmt)).scalars().all())


def _interpretar(crudo: str) -> tuple[str, list[dict]]:
    """Texto del modelo → (respuesta, acciones). Tolera un modelo que no devuelva JSON."""
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        return crudo.strip(), []
    if not isinstance(datos, dict):
        return crudo.strip(), []
    respuesta = datos.get("respuesta")
    acciones = datos.get("acciones")
    return (
        respuesta.strip() if isinstance(respuesta, str) else "",
        acciones if isinstance(acciones, list) else [],
    )


async def preguntar(
    db: AsyncSession, usuario: UsuarioActual, datos: Pregunta, proveedor: ProveedorIA
) -> Respuesta:
    if not settings.asistente_activo:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_DISPONIBLE)

    limite = settings.asistente_max_preguntas_dia
    if await _usadas_hoy(db, usuario) >= limite:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Llegaste al límite de {limite} preguntas por hoy. Vuelve a intentarlo mañana.",
        )

    estado = await calcular_progreso(db, usuario, datos.plataforma, True)
    mensajes = construir_mensajes(
        datos.pregunta, datos.historial, usuario.rol, datos.plataforma,
        datos.pantalla_actual, estado,
    )
    try:
        crudo = await proveedor.responder(mensajes)
    except ErrorProveedorIA as e:
        # Nunca se registra la pregunta ni la clave: solo el tipo de fallo.
        log.warning("asistente: el proveedor de IA falló (%s)", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_DISPONIBLE) from None

    await _contar_pregunta(db, usuario)
    texto, acciones = _interpretar(crudo)
    if not texto:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_DISPONIBLE)

    partidos = await _partidos_del_club(db, usuario)
    validas: list[Accion] = []
    for a in acciones:
        if not isinstance(a, dict):
            continue
        ruta, etiqueta = a.get("ruta"), a.get("texto")
        if (isinstance(ruta, str) and isinstance(etiqueta, str) and etiqueta.strip()
                and ruta_valida(ruta, datos.plataforma, usuario.rol, partidos)):
            validas.append(Accion(texto=etiqueta.strip()[:60], ruta=ruta.strip()))
        if len(validas) == MAX_ACCIONES:
            break
    log.info("asistente: respuesta entregada (club=%s, plataforma=%s, acciones=%d)",
             usuario.club_id, datos.plataforma, len(validas))
    return Respuesta(respuesta=texto, acciones=validas)
