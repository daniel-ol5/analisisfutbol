"""Proveedor desacoplado de notificaciones push para CU-53."""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MensajePush:
    titulo: str
    cuerpo: str
    datos: dict[str, str]


@dataclass(frozen=True)
class ResultadoPush:
    enviado: bool
    proveedor_id: str | None = None
    error: str | None = None
    token_invalido: bool = False


class ProveedorPush(Protocol):
    async def enviar(self, tokens: list[str], mensaje: MensajePush) -> list[ResultadoPush]: ...


class FirebaseProveedorPush:
    """Adaptador FCM; las credenciales se obtienen mediante ADC."""

    def __init__(self) -> None:
        import firebase_admin

        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            opciones = (
                {"projectId": settings.firebase_project_id}
                if settings.firebase_project_id
                else None
            )
            self._app = firebase_admin.initialize_app(options=opciones)

    async def enviar(self, tokens: list[str], mensaje: MensajePush) -> list[ResultadoPush]:
        from firebase_admin import messaging

        resultados: list[ResultadoPush] = []
        # FCM admite como maximo 500 destinos por solicitud multicast.
        for inicio in range(0, len(tokens), 500):
            lote = messaging.MulticastMessage(
                tokens=tokens[inicio : inicio + 500],
                notification=messaging.Notification(
                    title=mensaje.titulo,
                    body=mensaje.cuerpo,
                ),
                data=mensaje.datos,
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(headers={"apns-priority": "10"}),
            )
            respuesta = await messaging.send_each_for_multicast_async(lote, app=self._app)
            for envio in respuesta.responses:
                error = envio.exception
                resultados.append(
                    ResultadoPush(
                        enviado=envio.success,
                        proveedor_id=envio.message_id,
                        error=str(error)[:400] if error is not None else None,
                        token_invalido=isinstance(
                            error,
                            (messaging.UnregisteredError, messaging.SenderIdMismatchError),
                        ),
                    )
                )
        return resultados


_proveedor: ProveedorPush | None = None
_inicializado = False


def obtener_proveedor_push() -> ProveedorPush | None:
    """Crea FCM solo cuando se habilita; el backend funciona sin credenciales locales."""
    global _inicializado, _proveedor
    if not settings.firebase_push_habilitado:
        return None
    if not _inicializado:
        _inicializado = True
        try:
            _proveedor = FirebaseProveedorPush()
        except Exception:
            log.exception("No se pudo inicializar Firebase Cloud Messaging")
    return _proveedor
