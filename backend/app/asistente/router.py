"""Endpoints del asistente de uso (web y móvil).

La web y el móvil hablan solo con estos endpoints; la clave de OpenAI vive
únicamente en el backend.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.asistente import service
from app.asistente.prompt import guia
from app.asistente.proveedor import ProveedorIA, obtener_proveedor
from app.asistente.schemas import Plataforma, Pregunta, Progreso, Respuesta
from app.core.deps import Actual, Db

# La guía se carga al arrancar: si falta el archivo, la API no levanta.
guia()

router = APIRouter()

_ERRORES = {
    429: {"description": "Se alcanzó el límite diario de preguntas del usuario"},
    503: {"description": "El asistente está apagado o la IA no respondió"},
}


@router.get("/progreso", response_model=Progreso,
            summary="Asistente · Pasos del flujo hechos y pendientes del club")
async def progreso(
    usuario: Actual, db: Db,
    plataforma: Annotated[Plataforma, Query()] = "web",
) -> Progreso:
    return await service.progreso(db, usuario, plataforma)


@router.post("/preguntar", response_model=Respuesta, responses=_ERRORES,
             summary="Asistente · Responder una duda sobre cómo usar Área Técnica")
async def preguntar(
    datos: Pregunta, usuario: Actual, db: Db,
    proveedor: Annotated[ProveedorIA, Depends(obtener_proveedor)],
) -> Respuesta:
    return await service.preguntar(db, usuario, datos, proveedor)
