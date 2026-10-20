"""Autenticación de WebSockets y códigos de cierre  —  T-032.

El navegador no deja mandar el header `Authorization` en un WebSocket, y el
token en la URL termina en los logs de acceso. Por eso la conexión se acepta y
el **primer mensaje** tiene que ser la autenticación:

    {"tipo": "auth", "token": "<access_token>"}

Si no llega en `TIEMPO_AUTENTICACION_S`, o no es válido, se cierra con uno de
los códigos de abajo. El contrato completo está en docs/api/websockets.md.
"""

import asyncio
import contextlib
from collections.abc import Callable
from enum import IntEnum

from fastapi import WebSocket, WebSocketDisconnect

from app.core.deps import UsuarioActual, usuario_desde_token

TIEMPO_AUTENTICACION_S = 5.0


class Cierre(IntEnum):
    """Códigos de cierre propios (rango 4000-4999, reservado a aplicaciones)."""

    NORMAL = 1000
    MENSAJE_INVALIDO = 4400
    NO_AUTENTICADO = 4401
    NO_ENCONTRADO = 4404   # partido inexistente u otro club: no se distinguen a propósito
    TIEMPO_AGOTADO = 4408


async def cerrar(ws: WebSocket, codigo: Cierre, motivo: str) -> None:
    """Cierra sin fallar si el cliente ya se fue."""
    with contextlib.suppress(RuntimeError):
        await ws.close(code=codigo, reason=motivo)


async def autenticar[T: UsuarioActual](
    ws: WebSocket,
    validar: Callable[[str], T | None] = usuario_desde_token,
) -> T | None:
    """Acepta la conexión y espera el mensaje de autenticación.

    `validar` convierte el token en una identidad: por defecto la de un
    usuario (canal /vivo); la ingesta pasa `worker_desde_token`.
    Devuelve la identidad, o None después de haber cerrado la conexión.
    """
    await ws.accept()
    try:
        datos = await asyncio.wait_for(ws.receive_json(), TIEMPO_AUTENTICACION_S)
    except TimeoutError:
        await cerrar(ws, Cierre.TIEMPO_AGOTADO, "No se recibió la autenticación a tiempo")
        return None
    except WebSocketDisconnect:
        return None
    except (ValueError, KeyError, TypeError):
        await cerrar(ws, Cierre.MENSAJE_INVALIDO, "El primer mensaje debe ser JSON")
        return None

    if not isinstance(datos, dict) or datos.get("tipo") != "auth":
        await cerrar(ws, Cierre.MENSAJE_INVALIDO, 'El primer mensaje debe ser {"tipo": "auth"}')
        return None

    token = datos.get("token")
    if not isinstance(token, str) or not token:
        await cerrar(ws, Cierre.NO_AUTENTICADO, "Falta el token de acceso")
        return None

    identidad = validar(token)
    if identidad is None:
        await cerrar(ws, Cierre.NO_AUTENTICADO, "Token inválido o expirado")
        return None
    return identidad
