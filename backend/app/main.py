"""Área Técnica — API.

Monta los seis paquetes del modelo de casos de uso. Cada uno se registra con su
`tag`, de modo que la documentación en /api/docs queda agrupada por paquete de
forma automática, espejando el modelo sin que nadie la mantenga a mano.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analisis.router import router as analisis
from app.asistencia.router import router as asistencia
from app.core.config import settings
from app.deportivo.router import router as deportivo
from app.partido.router import router as partido
from app.seguridad.router import router as seguridad
from app.vision.router import router as vision

# El esquema lo gestiona Alembic, no la aplicacion:
#   alembic upgrade head
# Docker lo corre solo al levantar el servicio api.

app = FastAPI(
    title=settings.proyecto,
    version=settings.version,
    description=(
        "Sistema de análisis táctico de fútbol por visión computacional. "
        "Los endpoints están agrupados según los seis paquetes del modelo de casos de uso."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origenes,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(seguridad,  prefix="/api/seguridad",  tags=["P1 · Seguridad y Administración"])
app.include_router(deportivo,  prefix="/api/deportivo",  tags=["P2 · Gestión Deportiva"])
app.include_router(vision,     prefix="/api/vision",     tags=["P3 · Visión por Computadora"])
app.include_router(partido,    prefix="/api/partido",    tags=["P4 · Operación del Partido"])
app.include_router(analisis,   prefix="/api/analisis",   tags=["P5 · Análisis Táctico"])
app.include_router(asistencia, prefix="/api/asistencia", tags=["P6 · Asistencia y Reportes"])


@app.get("/api/salud", tags=["Sistema"], summary="Estado de la API")
async def salud() -> dict[str, str]:
    return {"estado": "ok", "proyecto": settings.proyecto, "version": settings.version}
