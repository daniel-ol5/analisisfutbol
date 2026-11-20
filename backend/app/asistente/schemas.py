"""Contrato del asistente de uso."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Plataforma = Literal["web", "movil"]
EstadoPaso = Literal["hecho", "pendiente"]

LARGO_MAX_PREGUNTA = 500
MAX_HISTORIAL = 6


class PasoProgreso(BaseModel):
    clave: str
    titulo: str
    estado: EstadoPaso
    ruta: str | None = Field(
        description="Pantalla para hacer el paso en esta plataforma; nula si no existe "
        "aquí o si el rol no puede hacerlo."
    )
    solo_web: bool = False
    disponible: bool = Field(True, description="Falso si la función todavía no existe.")
    tu_rol_puede: bool
    nota: str | None = None


class Progreso(BaseModel):
    plataforma: Plataforma
    partido_id: int | None = Field(
        description="Partido de referencia: el que está en curso, el próximo programado "
        "o el último jugado."
    )
    pasos: list[PasoProgreso]
    siguiente: PasoProgreso | None
    asistente_activo: bool = Field(description="Si se pueden hacer preguntas a la IA.")


class MensajeHistorial(BaseModel):
    rol: Literal["usuario", "asistente"]
    texto: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class Pregunta(BaseModel):
    pregunta: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAX_PREGUNTA),
    ]
    pantalla_actual: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    plataforma: Plataforma = "web"
    historial: list[MensajeHistorial] = Field(default_factory=list, max_length=MAX_HISTORIAL)


class Accion(BaseModel):
    texto: str
    ruta: str


class Respuesta(BaseModel):
    respuesta: str
    acciones: list[Accion] = Field(default_factory=list)
