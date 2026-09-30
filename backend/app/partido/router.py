"""Endpoints de Operacion del Partido  —  CU-30 … CU-39.

Responsables segun el Sprint Planning:
    CU-30, CU-31, CU-34, CU-35  control y asignacion · S3 · Jhon
    CU-33, CU-36 a CU-39        eventos y calidad    · S3 · Susana

El canal WebSocket no figura en el esquema OpenAPI porque el estandar no lo
cubre. Su contrato es el esquema `MensajeWorker` de este paquete:

    ws://<host>/api/partido/{partido_id}/vivo     el DT y el analista escuchan
    ws://<host>/api/partido/{partido_id}/ingesta  el worker de vision publica
"""

from fastapi import APIRouter, Query, status

from app.core.deps import Actual, Db
from app.core.pendiente import RESPUESTA_501, pendiente
from app.partido.schemas import (
    AsignarTrack,
    Descuento,
    EstadoEnVivo,
    EventoManual,
    EventoManualCrear,
    IniciarPartido,
    RangoPosiciones,
    TrackDetectado,
)

router = APIRouter(responses=RESPUESTA_501)


# ---------------- CU-30, CU-31 · Control del partido ----------------

@router.post("/{partido_id}/iniciar", response_model=EstadoEnVivo,
             summary="CU-30, CU-31 · Iniciar el partido y fijar la direccion de ataque")
async def iniciar(partido_id: int, datos: IniciarPartido, usuario: Actual, db: Db) -> EstadoEnVivo:
    # Regla: un partido sin calibracion valida (error medio > 2 m) no puede iniciarse.
    pendiente("CU-30", "Sprint 3", "Jhon")


@router.post("/{partido_id}/entretiempo", response_model=EstadoEnVivo,
             summary="CU-30 · Cerrar el primer tiempo e iniciar el segundo")
async def entretiempo(partido_id: int, usuario: Actual, db: Db) -> EstadoEnVivo:
    pendiente("CU-30", "Sprint 3", "Jhon")


@router.post("/{partido_id}/descuento", response_model=EstadoEnVivo,
             summary="CU-30 · Agregar tiempo de descuento")
async def descuento(partido_id: int, datos: Descuento, usuario: Actual, db: Db) -> EstadoEnVivo:
    pendiente("CU-30", "Sprint 3", "Jhon")


@router.post("/{partido_id}/finalizar", response_model=EstadoEnVivo,
             summary="CU-30 · Finalizar el partido")
async def finalizar(partido_id: int, usuario: Actual, db: Db) -> EstadoEnVivo:
    pendiente("CU-30", "Sprint 3", "Jhon")


@router.get("/{partido_id}/estado", response_model=EstadoEnVivo,
            summary="CU-30, CU-39 · Estado actual del partido y calidad del procesamiento")
async def estado(partido_id: int, usuario: Actual, db: Db) -> EstadoEnVivo:
    pendiente("CU-30", "Sprint 3", "Jhon")


# ---------------- CU-36, CU-37, CU-38 · Eventos manuales ----------------

@router.get("/{partido_id}/eventos", response_model=list[EventoManual],
            summary="CU-36 a CU-38 · Listar eventos cargados a mano")
async def listar_eventos(partido_id: int, usuario: Actual, db: Db) -> list[EventoManual]:
    pendiente("CU-36", "Sprint 3", "Susana")


@router.post("/{partido_id}/eventos", response_model=EventoManual,
             status_code=status.HTTP_201_CREATED,
             summary="CU-36 a CU-38 · Registrar gol, tarjeta o sustitucion")
async def registrar_evento(partido_id: int, datos: EventoManualCrear,
                           usuario: Actual, db: Db) -> EventoManual:
    # Regla: una segunda amarilla al mismo jugador se convierte en roja automaticamente.
    pendiente("CU-36", "Sprint 3", "Susana")


@router.delete("/eventos/{evento_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="CU-38 · Deshacer el ultimo evento cargado")
async def deshacer_evento(evento_id: int, usuario: Actual, db: Db) -> None:
    pendiente("CU-38", "Sprint 3", "Susana")


@router.post("/{partido_id}/eventos/sincronizar", response_model=list[EventoManual],
             summary="CU-33 · Sincronizar la cola de eventos capturados sin conexion")
async def sincronizar_cola(partido_id: int, eventos: list[EventoManualCrear],
                           usuario: Actual, db: Db) -> list[EventoManual]:
    # Regla: llegan en orden y no se duplican, aunque el envio se repita.
    pendiente("CU-33", "Sprint 3", "Susana")


# ---------------- CU-34, CU-35 · Identificadores ----------------

@router.get("/{partido_id}/tracks", response_model=list[TrackDetectado],
            summary="CU-34 · Identificadores detectados y su asignacion")
async def listar_tracks(partido_id: int, usuario: Actual, db: Db,
                        solo_activos: bool = True) -> list[TrackDetectado]:
    pendiente("CU-34", "Sprint 3", "Jhon")


@router.put("/{partido_id}/tracks/{track_id}", response_model=TrackDetectado,
            summary="CU-34, CU-35 · Asignar o reasignar un identificador a un jugador")
async def asignar_track(partido_id: int, track_id: int, datos: AsignarTrack,
                        usuario: Actual, db: Db) -> TrackDetectado:
    # Regla: reasignar tras una oclusion continua las metricas, no las reinicia.
    pendiente("CU-34", "Sprint 3", "Jhon")


# ---------------- Posiciones ----------------

@router.get("/{partido_id}/posiciones", response_model=RangoPosiciones,
            summary="Consultar posiciones en un rango de tiempo (para replay y mapas)")
async def posiciones(partido_id: int, usuario: Actual, db: Db,
                     desde_t: float = Query(0, ge=0),
                     hasta_t: float = Query(300, gt=0)) -> RangoPosiciones:
    pendiente("CU-41", "Sprint 3", "Daniel")
