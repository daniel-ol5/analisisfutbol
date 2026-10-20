"""Endpoints de Operacion del Partido  —  CU-30 … CU-39.

Responsables segun el Sprint Planning:
    CU-30, CU-31, CU-34, CU-35  control y asignacion · S3 · Jhon
    CU-33, CU-36 a CU-39        eventos y calidad    · S3 · Susana

El canal WebSocket no figura en el esquema OpenAPI porque el estandar no lo
cubre. Su contrato esta en docs/api/websockets.md:

    ws://<host>/api/partido/{partido_id}/vivo     el DT y el analista escuchan
    ws://<host>/api/partido/{partido_id}/ingesta  el worker de vision publica
"""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.core import ws as ws_auth
from app.core.deps import Actual, Db, UsuarioActual, requiere_rol, worker_desde_token
from app.core.pendiente import RESPUESTA_501, pendiente
from app.core.realtime import Hub, canal_partido, obtener_hub
from app.core.security import decodificar, token_ingesta
from app.core.ws import Cierre, cerrar
from app.partido.schemas import (
    AsignarTrack,
    Descuento,
    EstadoEnVivo,
    EventoManual,
    EventoManualCrear,
    IniciarPartido,
    MensajeWorker,
    RangoPosiciones,
    TokenIngesta,
    TrackDetectado,
)
from app.partido.service import (
    AlmacenPosiciones,
    RepositorioPartidos,
    obtener_almacen_posiciones,
    obtener_repositorio_partidos,
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


# ---------------- T-032 · Canal en vivo (WebSocket) ----------------

def _es_ping(texto: str | None) -> bool:
    try:
        datos = json.loads(texto or "")
    except ValueError:
        return False
    return isinstance(datos, dict) and datos.get("tipo") == "ping"


HubDep = Annotated[Hub, Depends(obtener_hub)]
PartidosDep = Annotated[RepositorioPartidos, Depends(obtener_repositorio_partidos)]


async def _partido_accesible(ws: WebSocket, partidos: RepositorioPartidos,
                             partido_id: int, identidad: UsuarioActual) -> bool:
    """Verifica el partido con `tenancy`; si no es accesible, cierra con 4404."""
    try:
        await partidos.verificar(partido_id, identidad)
    except HTTPException as e:
        if e.status_code != status.HTTP_404_NOT_FOUND:
            raise
        await cerrar(ws, Cierre.NO_ENCONTRADO, "Partido no encontrado")
        return False
    return True


@router.websocket("/{partido_id}/vivo")
async def vivo(ws: WebSocket, partido_id: int, hub: HubDep, partidos: PartidosDep) -> None:
    """El panel del DT, el analista y el asistente escuchan el partido.

    Primer mensaje: {"tipo": "auth", "token": "..."}. Después el servidor
    responde {"tipo": "listo"} y difunde lo que llegue al canal del partido.
    """
    usuario = await ws_auth.autenticar(ws)
    if usuario is None or not await _partido_accesible(ws, partidos, partido_id, usuario):
        return

    canal = canal_partido(usuario.club_id, partido_id)
    await hub.suscribir(canal, ws)
    try:
        await ws.send_json({"tipo": "listo", "partido": partido_id})
        while True:
            # El cliente solo escucha; lo único que se atiende es el ping, útil
            # para que el móvil detecte una red caída. Leer también es lo que
            # permite enterarse de la desconexión. Lo demás se ignora.
            mensaje = await ws.receive()
            if mensaje["type"] == "websocket.disconnect":
                break
            if _es_ping(mensaje.get("text")):
                await ws.send_json({"tipo": "pong"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await hub.desuscribir(canal, ws)


# ---------------- T-033 · Ingesta del worker (WebSocket) ----------------

# Un fotograma corrupto no debe tumbar al worker en pleno partido, pero un
# worker que solo manda basura (versión vieja del contrato, bug) se corta.
MAX_INVALIDOS_SEGUIDOS = 50

AlmacenDep = Annotated[AlmacenPosiciones, Depends(obtener_almacen_posiciones)]


@router.post("/{partido_id}/token-ingesta", response_model=TokenIngesta,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={
                 401: {"description": "Falta el token de acceso, o es inválido o expirado"},
                 403: {"description": "Requiere rol ADMIN o ANALISTA"},
                 404: {"description": "Partido inexistente o de otro club"},
             },
             summary="T-033 · Emitir el token del worker de visión para un partido")
async def emitir_token_ingesta(partido_id: int, usuario: Actual,
                               partidos: PartidosDep) -> TokenIngesta:
    await partidos.verificar(partido_id, usuario)
    token = token_ingesta(usuario.club_id, partido_id)
    expira = datetime.fromtimestamp(decodificar(token)["exp"], UTC)
    return TokenIngesta(token=token, partido_id=partido_id, expira_en=expira)


def _validar_mensaje(texto: str | None, partido_id: int) -> tuple[MensajeWorker | None, list]:
    """Valida contra el contrato `MensajeWorker`. Devuelve el mensaje o los errores."""
    if texto is None:
        return None, [{"type": "binario", "loc": [],
                       "msg": "Solo se aceptan mensajes de texto con JSON"}]
    try:
        mensaje = MensajeWorker.model_validate_json(texto)
    except ValidationError as e:
        return None, json.loads(e.json(include_url=False, include_input=False))
    if mensaje.partido != partido_id:
        return None, [{"type": "partido_distinto", "loc": ["partido"],
                       "msg": f"El mensaje es del partido {mensaje.partido} y la "
                              f"conexión, del partido {partido_id}"}]
    return mensaje, []


@router.websocket("/{partido_id}/ingesta")
async def ingesta(ws: WebSocket, partido_id: int, hub: HubDep, partidos: PartidosDep,
                  almacen: AlmacenDep) -> None:
    """El worker de visión (o el emisor simulado) publica posiciones a 5 Hz.

    Primer mensaje: {"tipo": "auth", "token": "<token de ingesta>"}. Cada
    mensaje válido se difunde a /vivo y se guarda por lotes.
    """
    worker = await ws_auth.autenticar(ws, worker_desde_token)
    if worker is None:
        return
    if worker.partido_id != partido_id:
        # Token de otro partido: mismo cierre que un partido ajeno
        await cerrar(ws, Cierre.NO_ENCONTRADO, "Partido no encontrado")
        return
    if not await _partido_accesible(ws, partidos, partido_id, worker):
        return

    canal = canal_partido(worker.club_id, partido_id)
    invalidos = 0
    try:
        await ws.send_json({"tipo": "listo", "partido": partido_id})
        while True:
            entrada = await ws.receive()
            if entrada["type"] == "websocket.disconnect":
                break

            mensaje, errores = _validar_mensaje(entrada.get("text"), partido_id)
            if mensaje is None:
                invalidos += 1
                if invalidos >= MAX_INVALIDOS_SEGUIDOS:
                    await cerrar(ws, Cierre.MENSAJE_INVALIDO,
                                 f"{MAX_INVALIDOS_SEGUIDOS} mensajes inválidos seguidos")
                    break
                await ws.send_json({"tipo": "error", "detalle": errores,
                                    "invalidos_seguidos": invalidos})
                continue

            invalidos = 0
            await hub.difundir(canal, {"tipo": "posiciones",
                                       "datos": mensaje.model_dump(mode="json")})
            await almacen.agregar(mensaje)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await almacen.vaciar()
