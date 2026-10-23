"""Lógica de negocio de Visión por Computadora  —  CU-18 … CU-29.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.vision.models import Calibracion
from app.vision.schemas import CalibracionGuardar


async def _buscar_calibracion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Calibracion | None:
    """Calibración del partido dentro del club del usuario, o None."""
    stmt = del_club(Calibracion, usuario).where(Calibracion.partido_id == partido_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def obtener_calibracion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Calibracion:
    """CU-19: calibración vigente del partido. 404 si no existe o es de otro club."""
    return verificar_pertenencia(await _buscar_calibracion(db, usuario, partido_id), usuario)


async def guardar_calibracion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, datos: CalibracionGuardar
) -> tuple[Calibracion, bool]:
    """CU-19, CU-20: guarda los puntos y las medidas reales de la cancha.

    Hay una calibración por partido: si ya existe se actualiza (upsert), así las
    medidas y los puntos son editables. Devuelve (calibración, creada).

    NO calcula la homografía: eso es T-029. Por eso `matriz_h` y los errores
    quedan en None y `valida` en False. Al editar también se reinician: la
    matriz calculada con los puntos anteriores ya no corresponde a los nuevos.
    """
    calibracion = await _buscar_calibracion(db, usuario, partido_id)
    creada = calibracion is None
    if calibracion is None:
        calibracion = Calibracion(club_id=usuario.club_id, partido_id=partido_id)
        db.add(calibracion)

    calibracion.largo_m = datos.largo_m
    calibracion.ancho_m = datos.ancho_m
    calibracion.puntos_imagen = [p.model_dump() for p in datos.puntos_imagen]
    calibracion.puntos_cancha = [p.model_dump() for p in datos.puntos_cancha]
    calibracion.coef_distorsion = datos.coef_distorsion
    # TODO T-029: calcular matriz_h, error_medio_m, error_max_m y valida aca.
    calibracion.matriz_h = None
    calibracion.error_medio_m = None
    calibracion.error_max_m = None
    calibracion.valida = False

    try:
        await db.commit()
    except IntegrityError:
        # Dos POST simultaneos creando la calibracion del mismo partido: gana uno.
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La calibración de este partido se modificó al mismo tiempo. Inténtalo de nuevo",
        ) from None
    await db.refresh(calibracion)
    return calibracion, creada
