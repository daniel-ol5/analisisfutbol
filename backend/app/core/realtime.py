"""Hub de WebSockets: un canal por partido.

El worker de visión publica posiciones acá y el hub las difunde a todos los
clientes conectados a ese partido — panel web, app del DT, app del asistente.

En el Sprint 1 el estado vive en memoria, así que solo funciona con un proceso.
Cuando haya más de una instancia hay que reemplazar el diccionario por Redis
pub/sub, sin cambiar la interfaz de esta clase.
"""

from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self._canales: dict[int, set[WebSocket]] = defaultdict(set)

    async def conectar(self, partido_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._canales[partido_id].add(ws)

    def desconectar(self, partido_id: int, ws: WebSocket) -> None:
        self._canales[partido_id].discard(ws)
        if not self._canales[partido_id]:
            del self._canales[partido_id]

    async def difundir(self, partido_id: int, mensaje: dict) -> None:
        """Envía a todos los conectados al partido.

        Las conexiones que fallan se descartan en vez de cortar la difusión:
        un cliente caído no puede dejar sin datos a los demás.
        """
        caidas: list[WebSocket] = []
        for ws in self._canales.get(partido_id, set()):
            try:
                await ws.send_json(mensaje)
            except Exception:
                caidas.append(ws)
        for ws in caidas:
            self.desconectar(partido_id, ws)

    def conectados(self, partido_id: int) -> int:
        return len(self._canales.get(partido_id, set()))


hub = Hub()
