"""Proveedores de IA del asistente.

`obtener_proveedor` es el ÚNICO lugar donde se elige el proveedor: para cambiar
de servicio se cambia aquí, y las pruebas lo reemplazan por `ProveedorFalso`
con `app.dependency_overrides`. La clave de OpenAI solo se lee del entorno
(`settings.openai_api_key`) y nunca sale del backend.
"""

import json
from functools import lru_cache
from typing import Protocol

import openai
from openai import AsyncOpenAI

from app.asistente.prompt import RECHAZO
from app.core.config import settings

Mensajes = list[dict[str, str]]


class ErrorProveedorIA(Exception):
    """El proveedor no respondió. El mensaje nunca incluye la clave ni la pregunta."""


class ProveedorIA(Protocol):
    async def responder(self, mensajes: Mensajes) -> str:
        """Devuelve el texto del modelo: un JSON con `respuesta` y `acciones`."""
        ...


class ProveedorOpenAI:
    def __init__(self, clave: str, modelo: str, timeout_s: float,
                 base_url: str | None = None) -> None:
        self._modelo = modelo
        self._cliente = (
            AsyncOpenAI(api_key=clave, timeout=timeout_s, max_retries=1, base_url=base_url)
            if clave else None
        )

    async def responder(self, mensajes: Mensajes) -> str:
        if self._cliente is None:
            raise ErrorProveedorIA("sin_clave")
        try:
            r = await self._cliente.chat.completions.create(
                model=self._modelo,
                messages=mensajes,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                max_completion_tokens=700,
            )
        except openai.OpenAIError as e:
            # Solo el tipo: el texto de algunos errores repite parte de la clave.
            raise ErrorProveedorIA(type(e).__name__) from None
        return r.choices[0].message.content or ""


class ProveedorFalso:
    """Respuestas fijas y sin red, para pruebas y CI.

    Contesta a las preguntas que mencionan algo del sistema y rechaza el resto
    con la frase fija, como debe hacer el modelo real según sus instrucciones.
    """

    PALABRAS = ("calibr", "cámara", "camara", "partido", "equipo", "jugador", "plantel",
                "métrica", "metrica", "recomendaci", "usuario", "alineaci", "asign", "video",
                "área técnica", "area tecnica", "siguiente", "paso")

    def __init__(self, falla: bool = False, acciones: list[dict[str, str]] | None = None) -> None:
        self.falla = falla
        self.acciones = acciones if acciones is not None else [
            {"texto": "Ir a calibrar", "ruta": "/vision/calibracion"}
        ]
        self.ultimos_mensajes: Mensajes = []

    async def responder(self, mensajes: Mensajes) -> str:
        self.ultimos_mensajes = mensajes
        if self.falla:
            raise ErrorProveedorIA("falso")
        pregunta = mensajes[-1]["content"].lower()
        if any(p in pregunta for p in self.PALABRAS):
            return json.dumps({
                "respuesta": "1. Abre Visión y video.\n2. Entra a Calibración.",
                "acciones": self.acciones,
            })
        return json.dumps({"respuesta": RECHAZO, "acciones": []})


@lru_cache
def _proveedor_openai() -> ProveedorOpenAI:
    return ProveedorOpenAI(
        settings.openai_api_key.get_secret_value(),
        settings.openai_model,
        settings.asistente_timeout_s,
    )


def obtener_proveedor() -> ProveedorIA:
    return _proveedor_openai()
