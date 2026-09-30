"""Endpoints de Asistencia y Reportes  —  CU-49 … CU-58.

Responsables segun el Sprint Planning:
    CU-49              motor de reglas y catalogo  · S4 · Daniel
    CU-50, CU-51       recomendaciones y valoracion · S4 · Alejandra
    CU-52, CU-53, CU-54 alertas, push y catalogo    · S4 · Araceli
    CU-55, CU-56       informes y exportacion       · S4 · Jhon
"""

from fastapi import APIRouter, Query, Response, status

from app.asistencia.schemas import (
    FormatoExportacion,
    Informe,
    PruebaRegla,
    Recomendacion,
    Regla,
    ReglaCrear,
    ReglaEditar,
    ResultadoPrueba,
    Valoracion,
)
from app.core.deps import Actual, Db
from app.core.pendiente import RESPUESTA_501, pendiente

router = APIRouter(responses=RESPUESTA_501)


# ---------------- CU-49, CU-54 · Reglas tacticas ----------------

@router.get("/reglas", response_model=list[Regla],
            summary="CU-54 · Listar el catalogo de reglas del club mas las globales")
async def listar_reglas(usuario: Actual, db: Db, activas: bool | None = None) -> list[Regla]:
    pendiente("CU-54", "Sprint 4", "Araceli")


@router.post("/reglas", response_model=Regla, status_code=status.HTTP_201_CREATED,
             summary="CU-54 · Crear una regla propia del club")
async def crear_regla(datos: ReglaCrear, usuario: Actual, db: Db) -> Regla:
    pendiente("CU-54", "Sprint 4", "Araceli")


@router.patch("/reglas/{regla_id}", response_model=Regla,
              summary="CU-54 · Editar, activar o desactivar una regla")
async def editar_regla(regla_id: int, datos: ReglaEditar, usuario: Actual, db: Db) -> Regla:
    pendiente("CU-54", "Sprint 4", "Araceli")


@router.post("/reglas/{regla_id}/probar", response_model=ResultadoPrueba,
             summary="CU-54 · Probar una regla contra un partido ya registrado")
async def probar_regla(regla_id: int, datos: PruebaRegla, usuario: Actual, db: Db) -> ResultadoPrueba:
    pendiente("CU-54", "Sprint 4", "Araceli")


# ---------------- CU-50, CU-51, CU-52 · Recomendaciones ----------------

@router.get("/partidos/{partido_id}/recomendaciones", response_model=list[Recomendacion],
            summary="CU-50 · Recomendaciones activas, maximo 3 y priorizadas")
async def recomendaciones(partido_id: int, usuario: Actual, db: Db,
                          solo_activas: bool = Query(True,
                              description="True devuelve como maximo las 3 de mayor prioridad")
                          ) -> list[Recomendacion]:
    pendiente("CU-50", "Sprint 4", "Alejandra")


@router.post("/recomendaciones/{recomendacion_id}/valorar", response_model=Recomendacion,
             summary="CU-51 · Marcar util, no util o aplicada")
async def valorar(recomendacion_id: int, datos: Valoracion, usuario: Actual, db: Db) -> Recomendacion:
    pendiente("CU-51", "Sprint 4", "Alejandra")


@router.get("/partidos/{partido_id}/alertas", response_model=list[Recomendacion],
            summary="CU-52 · Alertas de fatiga y riesgo de expulsion")
async def alertas(partido_id: int, usuario: Actual, db: Db) -> list[Recomendacion]:
    # Regla: no se genera alerta de fatiga para jugadores que entraron hace menos de 15 minutos.
    pendiente("CU-52", "Sprint 4", "Araceli")


# ---------------- CU-53 · Notificaciones ----------------

@router.post("/dispositivos", status_code=status.HTTP_204_NO_CONTENT,
             summary="CU-53 · Registrar el token del dispositivo para recibir push")
async def registrar_dispositivo(token: str, usuario: Actual, db: Db) -> None:
    # Regla: solo las recomendaciones de prioridad CRITICA generan notificacion.
    pendiente("CU-53", "Sprint 4", "Araceli")


# ---------------- CU-55, CU-56 · Informes ----------------

@router.post("/partidos/{partido_id}/informe", response_model=Informe,
             status_code=status.HTTP_202_ACCEPTED,
             summary="CU-55 · Generar el informe post-partido en segundo plano")
async def generar_informe(partido_id: int, usuario: Actual, db: Db) -> Informe:
    pendiente("CU-55", "Sprint 4", "Jhon")


@router.get("/informes/{informe_id}", response_model=Informe,
            summary="CU-55 · Estado y descarga del informe")
async def ver_informe(informe_id: int, usuario: Actual, db: Db) -> Informe:
    pendiente("CU-55", "Sprint 4", "Jhon")


@router.get("/partidos/{partido_id}/exportar",
            summary="CU-56 · Exportar metricas a CSV",
            responses={200: {"content": {"text/csv": {}}, "description": "Archivo CSV en UTF-8"}})
async def exportar(partido_id: int, usuario: Actual, db: Db,
                   formato: FormatoExportacion = FormatoExportacion.METRICAS_EQUIPO) -> Response:
    pendiente("CU-56", "Sprint 4", "Jhon")
