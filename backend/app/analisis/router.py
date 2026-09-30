"""Endpoints de Analisis Tactico  —  CU-40 … CU-48.

Responsables segun el Sprint Planning:
    CU-42, CU-43, CU-46  metricas       · S3 · Alejandra
    CU-40, CU-41, CU-44  visualizacion  · S3 · Daniel
    CU-45, CU-47, CU-48  avanzadas      · S4 · Alex
"""

from fastapi import APIRouter, Query

from app.analisis.schemas import (
    Comparativa,
    EventoDerivado,
    Intervalo,
    LineaTiempo,
    MapaCalor,
    MetricaJugador,
    MetricasPartido,
    RedPases,
)
from app.core.deps import Actual, Db
from app.core.pendiente import RESPUESTA_501, pendiente

router = APIRouter(responses=RESPUESTA_501)


# ---------------- CU-42 · Posesion y circulacion ----------------

@router.get("/partidos/{partido_id}/metricas", response_model=MetricasPartido,
            summary="CU-42 · Metricas de equipo acumuladas y de los ultimos 5 minutos")
async def metricas(partido_id: int, usuario: Actual, db: Db) -> MetricasPartido:
    pendiente("CU-42", "Sprint 3", "Alejandra")


@router.get("/partidos/{partido_id}/metricas/intervalos", response_model=list[Intervalo],
            summary="CU-46 · Evolucion por intervalos de 5 minutos")
async def intervalos(partido_id: int, usuario: Actual, db: Db) -> list[Intervalo]:
    pendiente("CU-46", "Sprint 3", "Alejandra")


# ---------------- CU-43 · Metricas fisicas ----------------

@router.get("/partidos/{partido_id}/metricas/jugadores", response_model=list[MetricaJugador],
            summary="CU-43 · Distancia, velocidad maxima y sprints por jugador")
async def metricas_jugadores(partido_id: int, usuario: Actual, db: Db,
                             equipo: str | None = None) -> list[MetricaJugador]:
    # Regla: un identificador sin jugador asignado no produce metricas individuales.
    pendiente("CU-43", "Sprint 3", "Alejandra")


# ---------------- CU-44 · Mapas de calor ----------------

@router.get("/partidos/{partido_id}/mapa-calor", response_model=MapaCalor,
            summary="CU-44 · Mapa de calor por equipo, linea o jugador")
async def mapa_calor(partido_id: int, usuario: Actual, db: Db,
                     alcance: str = Query("equipo", pattern="^(equipo|linea|jugador)$"),
                     referencia_id: int | None = None,
                     desde_minuto: int = 0,
                     hasta_minuto: int = 90) -> MapaCalor:
    # Regla: las coordenadas se normalizan por direccion de ataque antes de agregarse.
    pendiente("CU-44", "Sprint 3", "Daniel")


# ---------------- CU-47, CU-48 · Linea de tiempo y red de pases ----------------

@router.get("/partidos/{partido_id}/linea-tiempo", response_model=LineaTiempo,
            summary="CU-47 · Cronologia de eventos de camara y manuales")
async def linea_tiempo(partido_id: int, usuario: Actual, db: Db,
                       tipo: str | None = None, equipo: str | None = None) -> LineaTiempo:
    pendiente("CU-47", "Sprint 4", "Alex")


@router.get("/partidos/{partido_id}/red-pases", response_model=RedPases,
            summary="CU-48 · Grafo de circulacion del balon")
async def red_pases(partido_id: int, usuario: Actual, db: Db,
                    desde_minuto: int = 0, hasta_minuto: int = 90) -> RedPases:
    pendiente("CU-48", "Sprint 4", "Alex")


# ---------------- Eventos derivados ----------------

@router.get("/partidos/{partido_id}/eventos-derivados", response_model=list[EventoDerivado],
            summary="Pases, perdidas, recuperaciones y tiros inferidos por la camara")
async def eventos_derivados(partido_id: int, usuario: Actual, db: Db,
                            tipo: str | None = None) -> list[EventoDerivado]:
    pendiente("CU-42", "Sprint 3", "Alejandra")


# ---------------- CU-57 · Comparativa ----------------

@router.get("/equipos/{equipo_id}/comparativa", response_model=list[Comparativa],
            summary="CU-57 · Comparar un partido con el promedio de la temporada")
async def comparativa(equipo_id: int, partido_id: int, usuario: Actual, db: Db,
                      competicion_id: int | None = None) -> list[Comparativa]:
    pendiente("CU-57", "Sprint 4", "Jhon")
