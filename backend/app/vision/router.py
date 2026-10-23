"""Endpoints de Vision por Computadora  —  CU-18 … CU-29.

Responsables segun el Sprint Planning:
    CU-19 a CU-23  calibracion y homografia  · S2 · Jhon
    CU-24 a CU-26  worker de vision          · S3 · Alex  (corre fuera de este backend)
    CU-27 a CU-29  video y modelos           · S3 · Araceli
"""

from fastapi import APIRouter, Depends, Response, UploadFile, status

from app.core.deps import Actual, Db, requiere_rol
from app.core.pendiente import RESPUESTA_501, pendiente
from app.vision import service
from app.vision.schemas import (
    Calibracion,
    CalibracionGuardar,
    ErrorCalibracion,
    LanzarProceso,
    Modelo,
    ModeloCrear,
    Video,
)

router = APIRouter(responses=RESPUESTA_501)


# ---------------- CU-19, CU-20, CU-21, CU-22 · Calibracion ----------------

@router.get("/partidos/{partido_id}/calibracion", response_model=Calibracion,
            summary="CU-19 · Ver la calibracion vigente del partido")
async def ver_calibracion(partido_id: int, usuario: Actual, db: Db) -> Calibracion:
    calibracion = await service.obtener_calibracion(db, usuario, partido_id)
    return Calibracion.model_validate(calibracion)


@router.post("/partidos/{partido_id}/calibracion", response_model=Calibracion,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={200: {"model": Calibracion,
                              "description": "El partido ya tenia calibracion: se actualizo"}},
             summary="CU-19, CU-20 · Calibrar camara y registrar medidas de cancha")
async def calibrar(partido_id: int, datos: CalibracionGuardar, usuario: Actual, db: Db,
                   response: Response) -> Calibracion:
    # 201 al crear, 200 al actualizar una calibracion existente (upsert).
    calibracion, creada = await service.guardar_calibracion(db, usuario, partido_id, datos)
    if not creada:
        response.status_code = status.HTTP_200_OK
    return Calibracion.model_validate(calibracion)


@router.post("/partidos/{partido_id}/calibracion/validar", response_model=ErrorCalibracion,
             summary="CU-21 · Calcular el error de reproyeccion sin guardar")
async def validar_calibracion(partido_id: int, datos: CalibracionGuardar,
                              usuario: Actual, db: Db) -> ErrorCalibracion:
    pendiente("CU-21", "Sprint 2", "Jhon")


@router.get("/sedes/{sede}/calibracion-previa", response_model=Calibracion,
            summary="CU-22 · Recuperar una calibracion anterior de la misma sede")
async def calibracion_previa(sede: str, usuario: Actual, db: Db) -> Calibracion:
    pendiente("CU-22", "Sprint 2", "Jhon")


# ---------------- CU-29 · Modelos ----------------

@router.get("/modelos", response_model=list[Modelo], summary="CU-29 · Listar versiones del modelo")
async def listar_modelos(usuario: Actual, db: Db) -> list[Modelo]:
    pendiente("CU-29", "Sprint 3", "Araceli")


@router.post("/modelos", response_model=Modelo, status_code=status.HTTP_201_CREATED,
             summary="CU-29 · Registrar una version entrenada")
async def registrar_modelo(datos: ModeloCrear, usuario: Actual, db: Db) -> Modelo:
    pendiente("CU-29", "Sprint 3", "Araceli")


@router.post("/modelos/{modelo_id}/activar", response_model=Modelo,
             summary="CU-29 · Activar una version (solo una activa por vez)")
async def activar_modelo(modelo_id: int, usuario: Actual, db: Db) -> Modelo:
    pendiente("CU-29", "Sprint 3", "Araceli")


# ---------------- CU-27, CU-28 · Video ----------------

@router.get("/partidos/{partido_id}/videos", response_model=list[Video],
            summary="CU-28 · Listar videos del partido")
async def listar_videos(partido_id: int, usuario: Actual, db: Db) -> list[Video]:
    pendiente("CU-28", "Sprint 3", "Araceli")


@router.post("/partidos/{partido_id}/videos", response_model=Video,
             status_code=status.HTTP_201_CREATED,
             summary="CU-28 · Cargar video de partido")
async def cargar_video(partido_id: int, archivo: UploadFile, usuario: Actual, db: Db) -> Video:
    pendiente("CU-28", "Sprint 3", "Araceli")


@router.get("/videos/{video_id}", response_model=Video,
            summary="CU-27 · Estado del procesamiento")
async def estado_video(video_id: int, usuario: Actual, db: Db) -> Video:
    pendiente("CU-27", "Sprint 3", "Araceli")


@router.post("/videos/{video_id}/procesar", response_model=Video,
             summary="CU-27 · Lanzar el procesamiento en segundo plano")
async def procesar_video(video_id: int, datos: LanzarProceso, usuario: Actual, db: Db) -> Video:
    pendiente("CU-27", "Sprint 3", "Araceli")


@router.delete("/videos/{video_id}/procesar", status_code=status.HTTP_204_NO_CONTENT,
               summary="CU-27 · Cancelar un procesamiento en curso")
async def cancelar_proceso(video_id: int, usuario: Actual, db: Db) -> None:
    pendiente("CU-27", "Sprint 3", "Araceli")
