"""Lógica de negocio de Operación del Partido  —  CU-30 … CU-39.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import logging
from typing import Any, Protocol

from sqlalchemy import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.core.tenancy import verificar_pertenencia
from app.partido.schemas import MensajeWorker

log = logging.getLogger(__name__)


# ---------------- Acceso a partidos (T-032) ----------------
#
# Los WebSockets necesitan saber si un partido existe y es del club del
# usuario. La tabla `partido` todavía no existe (T-047, Susana), así que la
# consulta queda detrás de esta interfaz.
#
# >>> PUNTO ÚNICO DE CONEXIÓN CON EL MODELO REAL <<<
# Cuando exista el modelo (con `club_id` desnormalizado), reemplazar por:
#
#     from app.deportivo.models import Partido
#     MODELO_PARTIDO = Partido
#
# ⚠️ PROVISORIO hasta T-047 (Susana): con None, los WebSockets aceptan
# cualquier partido_id (ver `PartidosSinTabla`). Al arrancar la API se avisa
# en el log (`avisar_provisorios`).
MODELO_PARTIDO: type[Any] | None = None


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
    if MODELO_PARTIDO is None:
        return PartidosSinTabla()
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
    if MODELO_PARTIDO is None:
        log.warning("PROVISORIO hasta T-047 (Susana): no existe la tabla partido; "
                    "los WebSockets aceptan cualquier partido_id, aislados por club.")
    if MODELO_POSICION is None:
        log.warning("PROVISORIO: no existe la tabla posicion; la ingesta difunde "
                    "en vivo pero no guarda las posiciones.")
