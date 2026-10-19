"""Hub de WebSockets: un canal por partido  —  T-032.

El worker de visión publica posiciones acá y el hub las difunde a todos los
clientes conectados a ese partido — panel web, app del DT, app del asistente.

Los routers dependen de la interfaz `Hub` a través de `obtener_hub()`, nunca de
una implementación concreta. Hoy el estado vive en memoria (`HubMemoria`), así
que solo funciona con un proceso. Cuando haya más de una instancia, se escribe
un `HubRedis` con pub/sub que cumpla la misma interfaz y se cambia únicamente
`obtener_hub()`: los routers no se tocan.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Protocol

from fastapi import WebSocket

log = logging.getLogger(__name__)


def canal_partido(club_id: int, partido_id: int) -> str:
    """Nombre del canal de un partido.

    Lleva el club además del partido: aunque una verificación fallara, dos
    clubes con el mismo `partido_id` nunca comparten canal. El formato con `:`
    es el habitual para nombres de canal de Redis.
    """
    return f"club:{club_id}:partido:{partido_id}"


class Hub(Protocol):
    """Interfaz que usan los routers. Todo es async para que una
    implementación sobre la red (Redis) entre sin cambiar las llamadas."""

    async def suscribir(self, canal: str, ws: WebSocket) -> None: ...

    async def desuscribir(self, canal: str, ws: WebSocket) -> None: ...

    async def difundir(self, canal: str, mensaje: dict[str, Any]) -> None: ...

    async def conectados(self, canal: str) -> int: ...


class HubMemoria:
    """Implementación en memoria, válida con un solo proceso de la API."""

    # Un cliente que tarda más que esto en recibir se descarta: no puede
    # frenar la difusión a los demás a 5 mensajes por segundo.
    TIEMPO_ENVIO_S = 2.0

    def __init__(self) -> None:
        self._canales: dict[str, set[WebSocket]] = defaultdict(set)

    async def suscribir(self, canal: str, ws: WebSocket) -> None:
        self._canales[canal].add(ws)

    async def desuscribir(self, canal: str, ws: WebSocket) -> None:
        conectados = self._canales.get(canal)
        if conectados is None:
            return
        conectados.discard(ws)
        if not conectados:
            del self._canales[canal]

    async def difundir(self, canal: str, mensaje: dict[str, Any]) -> None:
        """Envía a todos los suscritos al canal, en paralelo.

        Las conexiones que fallan o no responden a tiempo se descartan en vez
        de cortar la difusión: un cliente caído no puede dejar sin datos a los
        demás.
        """
        destinos = list(self._canales.get(canal, ()))
        if not destinos:
            return

        resultados = await asyncio.gather(
            *(asyncio.wait_for(ws.send_json(mensaje), self.TIEMPO_ENVIO_S) for ws in destinos),
            return_exceptions=True,
        )
        for ws, resultado in zip(destinos, resultados, strict=True):
            if isinstance(resultado, BaseException):
                log.info("Se descarta un cliente de %s: %r", canal, resultado)
                await self.desuscribir(canal, ws)

    async def conectados(self, canal: str) -> int:
        return len(self._canales.get(canal, ()))


_hub: Hub = HubMemoria()


def obtener_hub() -> Hub:
    """Dependencia de FastAPI. Único punto a cambiar para pasar a Redis."""
    return _hub
