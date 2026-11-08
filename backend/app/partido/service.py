"""Lógica de negocio de Operación del Partido  —  CU-30 … CU-39.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Partido
from app.deportivo.schemas import Direccion, EstadoPartido
from app.partido.models import RelojPartido
from app.partido.schemas import (
    Descuento,
    EstadoEnVivo,
    IndicadorCalidad,
    IniciarPartido,
    MensajeWorker,
)
from app.vision.models import Calibracion

log = logging.getLogger(__name__)

SEGUNDOS_PRIMER_TIEMPO = 45 * 60.0

RelojSistema = Callable[[], datetime]


def ahora_utc() -> datetime:
    """Reloj por defecto del servidor en UTC."""
    return datetime.now(UTC)


def obtener_reloj() -> RelojSistema:
    """Dependencia de FastAPI para inyectar el reloj en pruebas sin usar sleep."""
    return ahora_utc


def _en_utc(instante: datetime) -> datetime:
    """Normaliza marcas de tiempo leídas de SQLite (sin tzinfo) o PostgreSQL a UTC."""
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)


# ---------------- CU-31 · Normalización espacial por dirección de ataque ----------------


def normalizar_coordenadas(
    x_m: float,
    y_m: float,
    largo_m: float,
    ancho_m: float,
    ataca_hacia: Direccion | str,
    parte: int,
) -> tuple[float, float]:
    """CU-31: lleva cualquier punto (x_m, y_m) a la convención «nuestro equipo ataca hacia +x».

    `ataca_hacia` es la dirección de ataque en el PRIMER tiempo (`DER` = +x, `IZQ` = -x).
    En el segundo tiempo los equipos cambian de arco:
    - Parte 1 y `DER`: no cambia `(x_m, y_m)`.
    - Parte 1 e `IZQ`: rota 180° `(largo_m - x_m, ancho_m - y_m)`.
    - Parte 2 y `DER`: rota 180° `(largo_m - x_m, ancho_m - y_m)`.
    - Parte 2 e `IZQ`: no cambia `(x_m, y_m)`.
    """
    if parte not in (1, 2):
        raise ValueError(f"La parte debe ser 1 o 2 (recibido: {parte!r})")
    try:
        direccion = Direccion(ataca_hacia)
    except ValueError as e:
        raise ValueError(f"Dirección de ataque inválida: {ataca_hacia!r}") from e

    invertir = (
        direccion == Direccion.IZQUIERDA
        if parte == 1
        else direccion == Direccion.DERECHA
    )
    if invertir:
        return (largo_m - x_m, ancho_m - y_m)
    return (x_m, y_m)


# ---------------- CU-30, CU-31 · Control del partido y cronómetro (T-065) ----------------


def segundos_transcurridos(reloj: RelojPartido | None, ahora: datetime) -> float:
    """Tiempo del cronómetro en segundos: `acumulado_s + (ahora - inicio_utc)` si corre."""
    if reloj is None:
        return 0.0
    total = float(reloj.acumulado_s)
    if reloj.en_curso and reloj.inicio_utc is not None:
        delta = (_en_utc(ahora) - _en_utc(reloj.inicio_utc)).total_seconds()
        if delta > 0:
            total += delta
    return max(0.0, total)


def _construir_estado_en_vivo(
    partido: Partido, reloj: RelojPartido | None, ahora: datetime
) -> EstadoEnVivo:
    if reloj is None:
        parte = partido.parte
        minuto = partido.minuto_actual
        segundo = 0
        en_curso = False
    else:
        total_s = int(segundos_transcurridos(reloj, ahora))
        parte = reloj.parte
        minuto = total_s // 60
        segundo = total_s % 60
        en_curso = reloj.en_curso

    return EstadoEnVivo(
        partido_id=partido.id,
        parte=parte,
        minuto=minuto,
        segundo=segundo,
        en_curso=en_curso,
        goles_favor=partido.goles_favor,
        goles_contra=partido.goles_contra,
        posesion_local_pct=None,
        calidad=IndicadorCalidad(worker_conectado=False),
    )


async def _partido_del_club(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Partido:
    stmt = del_club(Partido, usuario).where(Partido.id == partido_id)
    partido = (await db.execute(stmt)).scalar_one_or_none()
    return verificar_pertenencia(partido, usuario)


async def _reloj_del_partido(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> RelojPartido | None:
    stmt = del_club(RelojPartido, usuario).where(RelojPartido.partido_id == partido_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _exigir_calibracion_valida(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> None:
    stmt = select(Calibracion).where(
        Calibracion.club_id == usuario.club_id,
        Calibracion.partido_id == partido_id,
    )
    calibracion = (await db.execute(stmt)).scalar_one_or_none()
    if calibracion is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede iniciar el partido: no hay calibración para este partido",
        )
    if not calibracion.valida:
        detalle_error = (
            f"{calibracion.error_medio_m:.2f} m"
            if calibracion.error_medio_m is not None
            else "desconocido"
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede iniciar el partido: calibración no válida, error medio {detalle_error}",
        )


async def iniciar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: IniciarPartido,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30, CU-31: inicia el primer tiempo exigiendo calibración válida y dirección de ataque."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.PROGRAMADO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede iniciar un partido en estado {partido.estado}",
        )

    await _exigir_calibracion_valida(db, usuario, partido_id)

    instante = _en_utc(ahora())
    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None:
        reloj = RelojPartido(club_id=usuario.club_id, partido_id=partido.id)
        db.add(reloj)

    reloj.parte = 1
    reloj.en_curso = True
    reloj.inicio_utc = instante
    reloj.acumulado_s = 0.0
    reloj.descuento_1_min = 0
    reloj.descuento_2_min = 0

    partido.estado = EstadoPartido.EN_CURSO.value
    partido.ataca_hacia = datos.ataca_hacia.value
    partido.parte = 1
    partido.minuto_actual = 0

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def entretiempo_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: en dos llamadas, pausa el 1er tiempo y luego arranca el 2do tiempo en el min 45."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede gestionar el entretiempo de un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None or reloj.parte != 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El entretiempo solo aplica durante o al cierre del primer tiempo",
        )

    instante = _en_utc(ahora())
    if reloj.en_curso:
        # 1.ª llamada: pausa el reloj al cerrar el primer tiempo (parte=1, en_curso=False)
        reloj.acumulado_s = segundos_transcurridos(reloj, instante)
        reloj.inicio_utc = None
        reloj.en_curso = False
        reloj.parte = 1
        partido.parte = 1
        partido.minuto_actual = int(reloj.acumulado_s) // 60
    else:
        # 2.ª llamada: con parte=1 pausado, arranca el segundo tiempo en el minuto 45
        reloj.parte = 2
        reloj.en_curso = True
        reloj.acumulado_s = SEGUNDOS_PRIMER_TIEMPO
        reloj.inicio_utc = instante
        partido.parte = 2
        partido.minuto_actual = 45

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def registrar_descuento(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: Descuento,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: agrega tiempo de descuento a la parte en curso (solo con el reloj corriendo)."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede agregar descuento a un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None or not reloj.en_curso:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se puede agregar tiempo de descuento con el reloj corriendo",
        )

    instante = _en_utc(ahora())
    if reloj.parte == 1:
        reloj.descuento_1_min = datos.minutos
    else:
        reloj.descuento_2_min = datos.minutos

    partido.minuto_actual = int(segundos_transcurridos(reloj, instante)) // 60

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def finalizar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: detiene el cronómetro y pasa el partido a FINALIZADO."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede finalizar un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    instante = _en_utc(ahora())
    if reloj is not None:
        reloj.acumulado_s = segundos_transcurridos(reloj, instante)
        reloj.inicio_utc = None
        reloj.en_curso = False
        partido.parte = reloj.parte
        partido.minuto_actual = int(reloj.acumulado_s) // 60

    partido.estado = EstadoPartido.FINALIZADO.value

    await db.commit()
    await db.refresh(partido)
    if reloj is not None:
        await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def obtener_estado_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30, CU-39: devuelve el estado actual del partido y su cronómetro."""
    partido = await _partido_del_club(db, usuario, partido_id)
    reloj = await _reloj_del_partido(db, usuario, partido_id)
    return _construir_estado_en_vivo(partido, reloj, _en_utc(ahora()))


# ---------------- Acceso a partidos (T-032) ----------------
#
# Los WebSockets necesitan saber si un partido existe y es del club del
# usuario. La consulta queda detrás de esta interfaz porque un WebSocket vive
# todo el encuentro y no debe retener la sesión HTTP durante 90 minutos.
MODELO_PARTIDO: type[Any] = Partido


class RepositorioPartidos(Protocol):
    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> None:
        """No devuelve nada si el partido es accesible; si no, lanza 404."""
        ...


class PartidosEnTabla:
    """Verificación real, a través de `tenancy`.

    Abre su propia sesión corta en vez de recibir la de la petición: un
    WebSocket vive todo el partido y no puede retener una conexión del pool
    durante 90 minutos.
    """

    def __init__(self, modelo: type[Any],
                 sesiones: async_sessionmaker[AsyncSession] = SessionLocal) -> None:
        self.modelo = modelo
        self.sesiones = sesiones

    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> None:
        async with self.sesiones() as db:
            verificar_pertenencia(await db.get(self.modelo, partido_id), usuario)


class PartidosSinTabla:
    """Provisorio mientras no exista la tabla: acepta cualquier `partido_id`.

    No hay fuga entre clubes aun así: el canal del Hub lleva el `club_id` del
    token (`canal_partido`), de modo que un usuario de otro club que use el
    mismo número cae en un canal vacío, nunca en el ajeno.
    """

    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> None:
        log.warning("Partido %s sin verificar: la tabla partido no existe (T-047)", partido_id)


def obtener_repositorio_partidos() -> RepositorioPartidos:
    """Dependencia de FastAPI."""
    return PartidosEnTabla(MODELO_PARTIDO)


# ---------------- Persistencia de posiciones (T-033) ----------------
#
# La tabla `posicion` necesita la tabla `partido` (T-047), así que todavía no
# existe. La inserción masiva ya está escrita en `PosicionesEnLote`.
#
# >>> PUNTO ÚNICO DE CONEXIÓN CON EL MODELO REAL <<<
# Cuando exista el modelo, con las columnas de docs/diagramas/modelo-datos.puml
# (partido_id, t, track_id, x_m, y_m, confianza), reemplazar por:
#
#     from app.partido.models import Posicion
#     MODELO_POSICION = Posicion
#
# ⚠️ PROVISORIO: con None, las posiciones se difunden en vivo pero no se guardan.
MODELO_POSICION: type[Any] | None = None


def filas_de(mensaje: MensajeWorker) -> list[dict[str, Any]]:
    """Una fila por punto detectado: los jugadores y, si se ve, el balón."""
    puntos = [*mensaje.jugadores, *([mensaje.balon] if mensaje.balon else [])]
    return [
        {"partido_id": mensaje.partido, "t": mensaje.t, "track_id": p.tid,
         "x_m": p.x, "y_m": p.y, "confianza": p.conf}
        for p in puntos
    ]


class AlmacenPosiciones(Protocol):
    async def agregar(self, mensaje: MensajeWorker) -> None: ...

    async def vaciar(self) -> None:
        """Guarda lo pendiente. Se llama también al desconectarse el worker."""
        ...


class PosicionesEnLote:
    """Acumula mensajes y los inserta de a lotes, con un solo INSERT masivo.

    A 5 Hz con 23 puntos, un partido son ~620.000 filas: de a una serían horas
    (ver la nota de `posicion` en el modelo de datos). `insert(Modelo)` con una
    lista de diccionarios es la inserción masiva de SQLAlchemy 2, el equivalente
    al `bulk_create` de Django: un único `executemany` por lote.
    """

    TAMANO_LOTE = 25   # mensajes: 5 s de partido, unas 575 filas

    def __init__(self, modelo: type[Any],
                 sesiones: async_sessionmaker[AsyncSession] = SessionLocal,
                 tamano_lote: int = TAMANO_LOTE) -> None:
        self.modelo = modelo
        self.sesiones = sesiones
        self.tamano_lote = tamano_lote
        self._filas: list[dict[str, Any]] = []
        self._mensajes = 0

    async def agregar(self, mensaje: MensajeWorker) -> None:
        self._filas.extend(filas_de(mensaje))
        self._mensajes += 1
        if self._mensajes >= self.tamano_lote:
            await self.vaciar()

    async def vaciar(self) -> None:
        if not self._filas:
            return
        filas, self._filas, self._mensajes = self._filas, [], 0
        try:
            async with self.sesiones() as db:
                await db.execute(insert(self.modelo), filas)
                await db.commit()
        except SQLAlchemyError:
            # Perder un lote es preferible a cortar la ingesta: el panel en vivo
            # sigue funcionando aunque la base falle un momento.
            log.exception("No se pudo guardar un lote de %d posiciones", len(filas))


class PosicionesDescartadas:
    """Provisorio mientras no exista la tabla: no guarda nada."""

    async def agregar(self, mensaje: MensajeWorker) -> None:
        pass

    async def vaciar(self) -> None:
        pass


def obtener_almacen_posiciones() -> AlmacenPosiciones:
    """Dependencia de FastAPI. Devuelve uno nuevo por conexión de worker."""
    if MODELO_POSICION is None:
        return PosicionesDescartadas()
    return PosicionesEnLote(MODELO_POSICION)


# ---------------- Aviso al arrancar ----------------

def avisar_provisorios() -> None:
    """Deja en el log, al arrancar la API, lo que funciona en modo provisorio."""
    if MODELO_POSICION is None:
        log.warning("PROVISORIO: no existe la tabla posicion; la ingesta difunde "
                    "en vivo pero no guarda las posiciones.")
