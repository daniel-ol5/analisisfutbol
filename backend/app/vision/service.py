"""Lógica de negocio de Visión por Computadora  —  CU-18 … CU-29.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.vision.homografia import (
    UMBRAL_ERROR_MEDIO_M,
    HomografiaError,
    ResultadoHomografia,
    calcular_homografia,
    es_valida,
)
from app.vision.models import Calibracion
from app.vision.schemas import CalibracionGuardar, ErrorCalibracion


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


def _calcular(datos: CalibracionGuardar) -> ResultadoHomografia:
    """Homografía de los puntos recibidos. Datos inservibles -> 422 con el motivo."""
    try:
        return calcular_homografia(
            [(p.x, p.y) for p in datos.puntos_imagen],
            [(p.x, p.y) for p in datos.puntos_cancha],
        )
    except HomografiaError as e:
        # 422 literal: Starlette renombró la constante (UNPROCESSABLE_ENTITY está deprecada).
        raise HTTPException(422, str(e)) from None


def validar_calibracion(datos: CalibracionGuardar) -> ErrorCalibracion:
    """CU-21: error de reproyección SIN guardar nada ni consultar la base."""
    r = _calcular(datos)
    valida = es_valida(r.error_medio_m)
    if valida:
        mensaje = (
            f"Calibración válida: error medio {r.error_medio_m:.2f} m "
            f"(máximo {r.error_max_m:.2f} m en el punto {r.indice_peor})"
        )
    else:
        mensaje = (
            f"Calibración NO válida: el error medio {r.error_medio_m:.2f} m supera "
            f"{UMBRAL_ERROR_MEDIO_M:g} m y bloquea el inicio del partido. "
            f"El peor punto es el {r.indice_peor}"
        )
    return ErrorCalibracion(
        error_medio_m=r.error_medio_m,
        error_max_m=r.error_max_m,
        punto_peor=r.indice_peor,
        valida=valida,
        mensaje=mensaje,
    )


async def guardar_calibracion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, datos: CalibracionGuardar
) -> tuple[Calibracion, bool]:
    """CU-19, CU-20: guarda los puntos y las medidas reales de la cancha.

    Hay una calibración por partido: si ya existe se actualiza (upsert), así las
    medidas y los puntos son editables. Devuelve (calibración, creada).

    CU-21 (T-029): calcula la homografía y el error antes de tocar la base. Si los
    puntos no sirven (degenerados) responde 422 y NO guarda nada. Si el error medio
    supera el umbral SÍ se guarda, con `valida=False`, para que el usuario pueda
    verla y corregirla. Al editar se recalcula todo: la matriz anterior ya no
    corresponde a los puntos nuevos.
    """
    resultado = _calcular(datos)
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
    # TODO T-036: los puntos entran sin corregir la distorsion del lente (ver homografia.py).
    calibracion.matriz_h = resultado.matriz
    calibracion.error_medio_m = resultado.error_medio_m
    calibracion.error_max_m = resultado.error_max_m
    calibracion.valida = es_valida(resultado.error_medio_m)

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
