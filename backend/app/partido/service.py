"""Lógica de negocio de Operación del Partido  —  CU-30 … CU-39.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import func, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Alineacion, AlineacionJugador, Jugador, Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import EventoManual as EventoManualModelo
from app.partido.schemas import EventoManualCrear, Lado, MensajeWorker, TipoEventoManual

log = logging.getLogger(__name__)

RelojSistema = Callable[[], datetime]


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def _en_utc(instante: datetime) -> datetime:
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)


# ---------------- CU-36, CU-37, CU-38 · Eventos manuales (T-066) ----------------


async def _partido_del_club(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Partido:
    stmt = del_club(Partido, usuario).where(Partido.id == partido_id)
    partido = (await db.execute(stmt)).scalar_one_or_none()
    return verificar_pertenencia(partido, usuario)


def _lado_propio(partido: Partido) -> Lado:
    return Lado.LOCAL if partido.es_local else Lado.VISITANTE


async def _exigir_jugador_alineado(
    db: AsyncSession, partido: Partido, jugador_id: int
) -> Jugador:
    stmt = (
        select(Jugador)
        .join(AlineacionJugador, AlineacionJugador.jugador_id == Jugador.id)
        .join(Alineacion, Alineacion.id == AlineacionJugador.alineacion_id)
        .where(
            Alineacion.partido_id == partido.id,
            Jugador.id == jugador_id,
            Jugador.club_id == partido.club_id,
            Jugador.equipo_id == partido.equipo_id,
        )
    )
    jugador = (await db.execute(stmt)).scalar_one_or_none()
    if jugador is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El jugador no pertenece a la alineacion de este partido",
        )
    return jugador


async def _validar_jugadores(
    db: AsyncSession, partido: Partido, datos: EventoManualCrear
) -> None:
    es_equipo_propio = datos.equipo == _lado_propio(partido)
    if not es_equipo_propio:
        if datos.jugador_id is not None or datos.jugador_entra_id is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "El rival no tiene un plantel registrado; no se aceptan ids del equipo propio",
            )
        return

    if datos.jugador_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El evento del equipo propio requiere jugador_id",
        )
    await _exigir_jugador_alineado(db, partido, datos.jugador_id)

    if datos.tipo == TipoEventoManual.SUSTITUCION:
        if datos.jugador_entra_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "La sustitucion del equipo propio requiere jugador_entra_id",
            )
        await _exigir_jugador_alineado(db, partido, datos.jugador_entra_id)


async def _evento_por_uuid(
    db: AsyncSession, usuario: UsuarioActual, uuid: str
) -> EventoManualModelo | None:
    stmt = del_club(EventoManualModelo, usuario).where(EventoManualModelo.uuid == uuid)
    return (await db.execute(stmt)).scalar_one_or_none()


def _mismo_evento(
    existente: EventoManualModelo, partido_id: int, datos: EventoManualCrear
) -> bool:
    return (
        existente.partido_id == partido_id
        and existente.tipo == datos.tipo.value
        and existente.equipo == datos.equipo.value
        and existente.jugador_id == datos.jugador_id
        and existente.jugador_entra_id == datos.jugador_entra_id
        and (datos.minuto is None or existente.minuto == datos.minuto)
    )


async def listar_eventos_manuales(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> list[EventoManualModelo]:
    await _partido_del_club(db, usuario, partido_id)
    stmt = (
        del_club(EventoManualModelo, usuario)
        .where(
            EventoManualModelo.partido_id == partido_id,
            EventoManualModelo.anulado_en.is_(None),
        )
        .order_by(EventoManualModelo.minuto, EventoManualModelo.creado_en, EventoManualModelo.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def registrar_evento_manual(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: EventoManualCrear,
    ahora: RelojSistema = ahora_utc,
) -> EventoManualModelo:
    """Registra un evento una sola vez, incluso si el cliente repite su UUID."""
    uuid = str(datos.uuid)
    existente = await _evento_por_uuid(db, usuario, uuid)
    if existente is not None:
        if not _mismo_evento(existente, partido_id, datos):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El UUID ya fue utilizado por un evento diferente",
            )
        return existente

    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se pueden registrar eventos en un partido {partido.estado}",
        )
    await _validar_jugadores(db, partido, datos)

    instante = _en_utc(ahora())
    minuto = partido.minuto_actual if datos.minuto is None else datos.minuto
    convertida_en_roja = False
    if datos.tipo == TipoEventoManual.AMARILLA and datos.jugador_id is not None:
        amarillas = await db.scalar(
            select(func.count())
            .select_from(EventoManualModelo)
            .where(
                EventoManualModelo.club_id == usuario.club_id,
                EventoManualModelo.partido_id == partido.id,
                EventoManualModelo.jugador_id == datos.jugador_id,
                EventoManualModelo.tipo == TipoEventoManual.AMARILLA.value,
                EventoManualModelo.anulado_en.is_(None),
            )
        )
        convertida_en_roja = bool(amarillas)

    evento = EventoManualModelo(
        club_id=usuario.club_id,
        partido_id=partido.id,
        uuid=uuid,
        tipo=datos.tipo.value,
        equipo=datos.equipo.value,
        jugador_id=datos.jugador_id,
        jugador_entra_id=datos.jugador_entra_id,
        minuto=minuto,
        origen="MANUAL",
        convertida_en_roja=convertida_en_roja,
        capturado_en=_en_utc(datos.capturado_en) if datos.capturado_en else instante,
        creado_en=instante,
        creado_por_id=usuario.id,
    )
    db.add(evento)

    if datos.tipo == TipoEventoManual.GOL:
        if datos.equipo == _lado_propio(partido):
            partido.goles_favor += 1
        else:
            partido.goles_contra += 1

    await db.commit()
    await db.refresh(evento)
    return evento


async def deshacer_evento_manual(
    db: AsyncSession,
    usuario: UsuarioActual,
    evento_id: int,
    ahora: RelojSistema = ahora_utc,
) -> None:
    stmt = del_club(EventoManualModelo, usuario).where(
        EventoManualModelo.id == evento_id,
        EventoManualModelo.anulado_en.is_(None),
    )
    evento = (await db.execute(stmt)).scalar_one_or_none()
    evento = verificar_pertenencia(evento, usuario)

    ultimo_stmt = (
        del_club(EventoManualModelo, usuario)
        .where(
            EventoManualModelo.partido_id == evento.partido_id,
            EventoManualModelo.anulado_en.is_(None),
        )
        .order_by(EventoManualModelo.creado_en.desc(), EventoManualModelo.id.desc())
        .limit(1)
    )
    ultimo = (await db.execute(ultimo_stmt)).scalar_one()
    if ultimo.id != evento.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se puede deshacer el ultimo evento activo del partido",
        )

    instante = _en_utc(ahora())
    edad_s = (instante - _en_utc(evento.creado_en)).total_seconds()
    if edad_s > 60:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El plazo de 60 segundos para deshacer el evento ya vencio",
        )

    partido = await _partido_del_club(db, usuario, evento.partido_id)
    if evento.tipo == TipoEventoManual.GOL.value:
        lado = Lado(evento.equipo)
        if lado == _lado_propio(partido):
            partido.goles_favor = max(0, partido.goles_favor - 1)
        else:
            partido.goles_contra = max(0, partido.goles_contra - 1)

    evento.anulado_en = instante
    evento.anulado_por_id = usuario.id
    await db.commit()


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
