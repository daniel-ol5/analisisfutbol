"""Lógica de negocio de Visión por Computadora  —  CU-18 … CU-29.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

from datetime import UTC, datetime

import cv2
import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Partido
from app.vision.calibracion import CalibracionInsuficiente, calibrar, corregir_puntos
from app.vision.calibracion import CalibracionIntrinseca as CalibracionIntrinsecaLente
from app.vision.homografia import (
    UMBRAL_ERROR_MEDIO_M,
    HomografiaError,
    ResultadoHomografia,
    calcular_homografia,
    es_valida,
)
from app.vision.models import Calibracion, ModeloML
from app.vision.schemas import ActivarModelo, CalibracionGuardar, ErrorCalibracion, ModeloCrear


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


def _puntos_imagen(datos: CalibracionGuardar) -> list[tuple[float, float]] | np.ndarray:
    """T-036 (CU-23): los puntos marcados, corregidos del lente si llegó la
    calibración intrínseca completa. Si no, tal cual (como antes de T-036).

    Se corrige con `alfa=0`: el worker tiene que usar el mismo `alfa` al
    corregir cada detección antes de aplicar `matriz_h`.
    """
    puntos = [(p.x, p.y) for p in datos.puntos_imagen]
    if not datos.tiene_intrinseca:
        return puntos
    intrinseca = CalibracionIntrinsecaLente.desde_dict({
        "matriz_camara": datos.matriz_camara, "coef_distorsion": datos.coef_distorsion,
        "tamano_imagen": datos.tamano_imagen})
    try:
        return corregir_puntos(puntos, intrinseca, alfa=0.0)
    except cv2.error:
        raise HTTPException(422, "No se pudo corregir la distorsión con esa matriz_camara "
                                 "y esos coef_distorsion") from None


def _calcular(datos: CalibracionGuardar) -> ResultadoHomografia:
    """Homografía de los puntos recibidos. Datos inservibles -> 422 con el motivo."""
    try:
        return calcular_homografia(
            _puntos_imagen(datos),   # T-036: corregidos antes de la homografía
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
    # T-036: `resultado` ya se calculó con los puntos corregidos si llegó la intrínseca.
    calibracion.matriz_camara = datos.matriz_camara
    calibracion.tamano_imagen = datos.tamano_imagen
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


# ---------------- CU-23 · Calibración intrínseca del lente (T-036) ----------------

MIN_FOTOS_TABLERO = 5
MAX_FOTOS_TABLERO = 20
MAX_BYTES_FOTO = 10 * 1024 * 1024   # 10 MB por foto


def calibrar_intrinseca(fotos: list[bytes], patron: tuple[int, int]) -> CalibracionIntrinsecaLente:
    """CU-23: K y coeficientes del lente a partir de fotos de un tablero de ajedrez.

    Es CPU puro (decodificar y `cv2.calibrateCamera`, cientos de ms): el router
    la llama con `run_in_threadpool` para no bloquear el event loop. No guarda
    nada: el resultado se envía después en POST /partidos/{id}/calibracion.
    """
    imagenes = []
    for i, datos in enumerate(fotos):
        imagen = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_GRAYSCALE)
        if imagen is None:
            raise HTTPException(422, f"La foto {i} no es una imagen JPG o PNG legible")
        imagenes.append(imagen)
    try:
        return calibrar(imagenes, patron)
    except CalibracionInsuficiente as e:
        raise HTTPException(422, (
            f"{e}. El tablero debe verse ENTERO en cada foto, con {patron[0]} x {patron[1]} "
            "esquinas interiores (columnas y filas en los parámetros)")) from None
    except ValueError as e:   # fotos de distinto tamaño
        raise HTTPException(422, str(e)) from None


# ---------------- CU-22 · Calibración previa de la sede (T-035) ----------------

ADVERTENCIA_CAMARA_MOVIDA = (
    "Calibración reutilizada de un partido anterior en la misma sede. Antes de "
    "usarla, verifica que la cámara no se haya movido (posición, altura, "
    "inclinación o zoom): si se movió, hay que volver a calibrar. Una forma "
    "rápida de comprobarlo es POST /calibracion/validar con puntos marcados "
    "sobre el cuadro actual."
)


def normalizar_sede(sede: str) -> str:
    """Clave de comparación: sin mayúsculas, sin espacios al inicio o al final
    y con los espacios repetidos colapsados ("  Cancha   Norte " = "cancha norte")."""
    return " ".join(sede.split()).casefold()


async def calibracion_previa(db: AsyncSession, usuario: UsuarioActual, sede: str) -> Calibracion:
    """CU-22: la calibración válida más reciente del club en un partido de esa sede.

    La sede vive en `partido` (texto libre), así que se une `calibracion` con
    `partido` por `partido_id`, las dos filtradas por el club con `tenancy`.
    La comparación se hace en Python y no en SQL: `lower()` de SQLite no pasa a
    minúsculas las letras acentuadas ("ESTADIO ÑUÑOA"), y colapsar espacios no
    se escribe igual en SQLite y PostgreSQL. Son pocas filas: una calibración
    por partido del club.

    "Más reciente" es por `creada_en` (y luego por id). 404 si no hay ninguna.
    """
    clave = normalizar_sede(sede)
    partidos = del_club(Partido, usuario).subquery()
    stmt = (
        del_club(Calibracion, usuario)
        .add_columns(partidos.c.sede)
        .join(partidos, partidos.c.id == Calibracion.partido_id)
        .where(Calibracion.valida.is_(True))
        .order_by(Calibracion.creada_en.desc(), Calibracion.id.desc())
    )
    if clave:
        for calibracion, sede_partido in (await db.execute(stmt)).all():
            if normalizar_sede(sede_partido) == clave:
                return calibracion
    raise HTTPException(status.HTTP_404_NOT_FOUND,
                        "No hay una calibración válida previa del club en esa sede")


# ---------------- CU-29 · Modelos ----------------

async def listar_modelos(db: AsyncSession, usuario: UsuarioActual) -> list[ModeloML]:
    """CU-29: versiones del club, la más nueva primero (la activa puede no serlo)."""
    stmt = del_club(ModeloML, usuario).order_by(ModeloML.entrenado_en.desc())
    return list((await db.execute(stmt)).scalars().all())


async def registrar_modelo(
    db: AsyncSession, usuario: UsuarioActual, datos: ModeloCrear
) -> ModeloML:
    """CU-29 (T-059): registra una version ya entrenada, nunca activa por defecto.

    Activarla es un paso aparte (`activar_modelo`): asi una version recien
    subida se puede revisar antes de que el worker la use en el siguiente
    procesamiento.
    """
    modelo = ModeloML(club_id=usuario.club_id, **datos.model_dump())
    db.add(modelo)
    try:
        await db.commit()
    except IntegrityError:
        # Mismo club + nombre + version ya registrado (uq_modelo_club_nombre_version).
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya existe un modelo '{datos.nombre}' version '{datos.version}' en este club",
        ) from None
    await db.refresh(modelo)
    return modelo


# T-064: las métricas que se comparan al activar, con su nombre para el mensaje.
METRICAS = {
    "map50_jugador": "mAP@50 jugador",
    "map50_balon": "mAP@50 balón",
    "idf1": "IDF1",
}


def metricas_que_empeoran(nueva: ModeloML, vigente: ModeloML) -> list[str]:
    """T-064: qué métricas de `nueva` son peores que las de `vigente`.

    Se compara solo lo que la vigente tiene medido. Si la vigente tiene una
    métrica y la nueva no la informa, no se puede asegurar que no empeore:
    cuenta como peor.
    """
    peores = []
    for campo, nombre in METRICAS.items():
        antes = getattr(vigente, campo)
        ahora = getattr(nueva, campo)
        if antes is None:
            continue
        if ahora is None:
            peores.append(f"{nombre} sin medir (la activa tiene {antes:.2f})")
        elif ahora < antes:
            peores.append(f"{nombre} {ahora:.2f} < {antes:.2f}")
    return peores


async def activar_modelo(
    db: AsyncSession,
    usuario: UsuarioActual,
    modelo_id: int,
    datos: ActivarModelo | None = None,
) -> ModeloML:
    """CU-29 (T-059, T-064): activa una version; a lo sumo una activa por club.

    T-064: una version con metricas peores que la vigente no se activa (409).
    Para "volver atras" sin reentrenar (T-059) se fuerza con `forzar` y un
    motivo, que queda registrado junto con quien lo hizo. El worker usa la
    version activa en el siguiente procesamiento. 404 si no existe o es de
    otro club.
    """
    datos = datos or ActivarModelo()
    modelo = verificar_pertenencia(
        (await db.execute(del_club(ModeloML, usuario).where(ModeloML.id == modelo_id)))
        .scalar_one_or_none(),
        usuario,
    )
    vigente = (
        await db.execute(
            del_club(ModeloML, usuario).where(ModeloML.activo, ModeloML.id != modelo.id)
        )
    ).scalar_one_or_none()
    peores = metricas_que_empeoran(modelo, vigente) if vigente else []
    if peores and not datos.forzar:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La versión {modelo.version} tiene métricas peores que la activa "
            f"({vigente.nombre} {vigente.version}): {'; '.join(peores)}. "
            "Para activarla igual (volver atrás), indica el motivo.",
        )
    # Primero se desactivan todas las del club (incluida esta, no importa) y
    # despues se activa solo esta: nunca hay un instante con dos activas.
    await db.execute(
        update(ModeloML).where(ModeloML.club_id == usuario.club_id).values(activo=False)
    )
    modelo.activo = True
    modelo.activado_en = datetime.now(UTC)
    modelo.activado_por_id = usuario.id
    # El motivo solo tiene sentido si hizo falta forzar.
    modelo.motivo_activacion = datos.motivo.strip() if peores and datos.motivo else None
    await db.commit()
    await db.refresh(modelo)
    return modelo
