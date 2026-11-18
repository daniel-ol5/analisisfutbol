"""Endpoints de Analisis Tactico  —  CU-40 … CU-48.

Responsables segun el Sprint Planning:
    CU-42, CU-43, CU-46  metricas       · S3 · Alejandra
    CU-40, CU-41, CU-44  visualizacion  · S3 · Daniel
    CU-45, CU-47, CU-48  avanzadas      · S4 · Alex
"""

from fastapi import APIRouter, Depends, Path, Query

from app.analisis import avanzadas as svc_avanzadas
from app.analisis import metricas as svc_metricas
from app.analisis.schemas import (
    Comparativa,
    EventoDerivado,
    Intervalo,
    LineaTiempo,
    MapaCalor,
    MetricaJugador,
    MetricasJugadorPorIntervalo,
    MetricasPartido,
    MetricasTacticas,
    RedPases,
)
from app.analisis.service import calcular_mapa_calor
from app.core.deps import Actual, Db, requiere_rol
from app.core.pendiente import RESPUESTA_501, pendiente

router = APIRouter(responses=RESPUESTA_501)

_RESPUESTA_404 = {404: {"description": "Partido inexistente o de otro club"}}
_EQUIPO = Query(None, description="LOCAL o VISITANTE; sin filtro, los dos. Otro valor: 422")


# ---------------- CU-42 · Posesion y circulacion ----------------

@router.get("/partidos/{partido_id}/metricas", response_model=MetricasPartido,
            responses=_RESPUESTA_404,
            summary="CU-42 · Metricas de equipo acumuladas y de los ultimos 5 minutos",
            description=(
                "T-074. Posesion: en cada muestra con balon visible, el jugador de campo mas "
                "cercano; a 2 m o menos posee su equipo, si no es disputa. Sin balon visible "
                "no se asigna. local + visitante + disputa = 100. Con el partido en juego "
                "incluye el intervalo en curso y `ultimos_5_min_*` es una ventana movil."
            ))
async def metricas(partido_id: int, usuario: Actual, db: Db) -> MetricasPartido:
    return await svc_metricas.metricas_partido(db, usuario, partido_id)


@router.get("/partidos/{partido_id}/metricas/intervalos", response_model=list[Intervalo],
            responses=_RESPUESTA_404,
            summary="CU-46 · Evolucion por intervalos de 5 minutos",
            description=(
                "T-076. Solo intervalos CERRADOS: se cierran durante el partido, al llegar la "
                "primera muestra del siguiente. Al finalizar, el ultimo se cierra como parcial "
                "(`minuto_hasta` es el de su ultima muestra)."
            ))
async def intervalos(partido_id: int, usuario: Actual, db: Db) -> list[Intervalo]:
    return await svc_metricas.listar_intervalos(db, usuario, partido_id)


@router.post("/partidos/{partido_id}/metricas/recalcular", response_model=MetricasPartido,
             dependencies=[Depends(requiere_rol("ADMIN", "ANALISTA"))],
             responses={**_RESPUESTA_404,
                        403: {"description": "Requiere rol ADMIN o ANALISTA"},
                        409: {"description": "El partido esta EN_CURSO"}},
             summary="CU-46 · Recalcular las metricas desde las posiciones guardadas",
             description=(
                 "T-076. Pasa las filas de `posicion`, ordenadas por t, por el mismo motor que "
                 "en vivo y reemplaza los intervalos guardados. Util tras procesar un video "
                 "grabado o tras asignar el arquero. No disponible con el partido EN_CURSO."
             ))
async def recalcular_metricas(partido_id: int, usuario: Actual, db: Db) -> MetricasPartido:
    return await svc_metricas.recalcular(db, usuario, partido_id)


# ---------------- CU-45 · Metricas tacticas colectivas ----------------

@router.get("/partidos/{partido_id}/metricas/tacticas", response_model=MetricasTacticas,
            responses=_RESPUESTA_404,
            summary="CU-45 · Altura de linea, amplitud y compacidad con y sin balon",
            description=(
                "T-102. Una muestra por segundo, con coordenadas normalizadas por direccion "
                "de ataque. Altura de linea: distancia al arco propio, en metros, de la x "
                "media de los 4 jugadores de campo mas retrasados; el arquero (asignado como "
                "ARQ o, si no hay, el mas retrasado dentro de su area) queda fuera del "
                "calculo. Amplitud: distancia entre los dos jugadores mas abiertos. "
                "Compacidad: area en m2 del poligono envolvente de los jugadores de campo. "
                "Suavizado: un jugador que la camara pierde sigue contando en su ultima "
                "posicion hasta 3 s, asi la linea no salta. Fase CON_BALON: posee el "
                "equipo; SIN_BALON: posee el rival; en disputa o con el balon no visible la "
                "muestra solo entra en `total`. `muestras` dice cuantos segundos respaldan "
                "cada promedio."
            ))
async def metricas_tacticas(partido_id: int, usuario: Actual, db: Db) -> MetricasTacticas:
    return await svc_metricas.metricas_tacticas(db, usuario, partido_id)


@router.get("/partidos/{partido_id}/metricas/minuto/{minuto}", response_model=Intervalo,
            responses=_RESPUESTA_404,
            summary="CU-47 · Metricas de un minuto exacto del partido",
            description=(
                "T-103. Calculadas con las posiciones de ese minuto (`minuto` .. `minuto` + 1, "
                "en minutos de partido) con el mismo motor que CU-42 y CU-45: posesion, pases, "
                "distancia, altura de linea, amplitud y compacidad. La linea de tiempo lo usa "
                "al elegir un evento para filtrar las metricas al minuto de la jugada. Un "
                "minuto sin posiciones devuelve ceros y valores nulos."
            ))
async def metricas_minuto(partido_id: int, usuario: Actual, db: Db,
                          minuto: int = Path(ge=0, le=200)) -> Intervalo:
    return await svc_metricas.metricas_minuto(db, usuario, partido_id, minuto)


# ---------------- CU-43 · Metricas fisicas ----------------

@router.get("/partidos/{partido_id}/metricas/jugadores", response_model=list[MetricaJugador],
            responses=_RESPUESTA_404,
            summary="CU-43 · Distancia, velocidad maxima y sprints por jugador",
            description=(
                "T-075. Ordenado por distancia. Distancia sobre la trayectoria suavizada; "
                "velocidad en ventana de 1 s; sprint = mas de 21 km/h sostenido 1 s. Se "
                "calcula por track y se convierte a jugador con las asignaciones (CU-34, "
                "CU-35): un track sin asignar suma a su equipo pero no aparece aqui."
            ))
async def metricas_jugadores(partido_id: int, usuario: Actual, db: Db,
                             equipo: str | None = _EQUIPO) -> list[MetricaJugador]:
    # Regla: un identificador sin jugador asignado no produce metricas individuales.
    return await svc_metricas.metricas_jugadores(db, usuario, partido_id, equipo)


@router.get("/partidos/{partido_id}/metricas/jugadores/intervalos",
            response_model=list[MetricasJugadorPorIntervalo],
            responses=_RESPUESTA_404,
            summary="CU-43 · Metricas fisicas por jugador en cada intervalo de 5 minutos",
            description=(
                "T-075. Una entrada por intervalo cerrado con `minuto_desde`, `minuto_hasta`, "
                "`distancia_m`, `velocidad_max_kmh`, `sprints` y `minutos_jugados`. Un sprint "
                "cuenta en el intervalo donde empieza."
            ))
async def metricas_jugadores_intervalos(
    partido_id: int, usuario: Actual, db: Db, equipo: str | None = _EQUIPO,
) -> list[MetricasJugadorPorIntervalo]:
    return await svc_metricas.metricas_jugadores_intervalos(db, usuario, partido_id, equipo)


# ---------------- CU-44 · Mapas de calor ----------------

@router.get("/partidos/{partido_id}/mapa-calor", response_model=MapaCalor,
            summary="CU-44 · Mapa de calor por equipo, linea o jugador")
async def mapa_calor(partido_id: int, usuario: Actual, db: Db,
                     alcance: str = Query("equipo", pattern="^(equipo|linea|jugador)$"),
                     referencia_id: int | None = None,
                     desde_minuto: int = 0,
                     hasta_minuto: int = 90) -> MapaCalor:
    # Regla: las coordenadas se normalizan por direccion de ataque antes de agregarse.
    return await calcular_mapa_calor(
        partido_id=partido_id,
        alcance=alcance,  # type: ignore[arg-type]
        referencia_id=referencia_id,
        desde_minuto=desde_minuto,
        hasta_minuto=hasta_minuto,
        usuario=usuario,
        db=db,
    )


# ---------------- CU-47, CU-48 · Linea de tiempo y red de pases ----------------

@router.get("/partidos/{partido_id}/linea-tiempo", response_model=LineaTiempo,
            responses=_RESPUESTA_404,
            summary="CU-47 · Cronologia de eventos de camara y manuales",
            description=(
                "T-103. Ordenada por `t` (segundos de partido). `origen` distingue lo inferido "
                "por la camara (PASE, PERDIDA, RECUPERACION) de lo cargado a mano (GOL, "
                "AMARILLA, ROJA, SUSTITUCION; sin los anulados, ubicados en `minuto * 60`). "
                "Filtros `tipo` y `equipo` (LOCAL o VISITANTE); un valor invalido da 422. "
                "Con el filtro, `t` permite que el plano 2D salte a ese instante."
            ))
async def linea_tiempo(partido_id: int, usuario: Actual, db: Db,
                       tipo: str | None = Query(None, description="PASE, PERDIDA, GOL, ..."),
                       equipo: str | None = _EQUIPO) -> LineaTiempo:
    return await svc_avanzadas.linea_tiempo(db, usuario, partido_id, tipo, equipo)


@router.get("/partidos/{partido_id}/red-pases", response_model=RedPases,
            responses=_RESPUESTA_404,
            summary="CU-48 · Grafo de circulacion del balon",
            description=(
                "T-103. Solo pases COMPLETADOS entre jugadores con track asignado. Nodo: "
                "jugador con su posicion media en el rango (normalizada por direccion de "
                "ataque), pases enviados y recibidos. `mayor_recepcion` marca a los 3 que mas "
                "pases reciben de su equipo; `aislado`, a quienes jugaron pero casi no entran "
                "al circuito (incluye a los que no tienen ningun pase). Arista: pases de "
                "`origen_id` a `destino_id`. Minutos inclusive; `desde_minuto` > "
                "`hasta_minuto` da 422."
            ))
async def red_pases(partido_id: int, usuario: Actual, db: Db,
                    desde_minuto: int = Query(0, ge=0), hasta_minuto: int = Query(90, ge=0),
                    equipo: str | None = _EQUIPO) -> RedPases:
    return await svc_avanzadas.red_pases(db, usuario, partido_id, desde_minuto, hasta_minuto,
                                         equipo)


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
