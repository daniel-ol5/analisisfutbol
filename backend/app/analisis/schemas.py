"""Esquemas de Analisis Tactico  —  CU-40 … CU-48.

Todos los casos de uso son de consulta: ninguno modifica el estado del sistema.
Las coordenadas llegan ya normalizadas por direccion de ataque (CU-31), asi que
el 1er y el 2do tiempo son comparables entre si.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.partido.schemas import Lado


class TipoEventoDerivado(StrEnum):
    PASE = "PASE"
    PERDIDA = "PERDIDA"
    RECUPERACION = "RECUPERACION"
    TIRO = "TIRO"
    FUERA = "FUERA"


class Fase(StrEnum):
    CON_BALON = "CON_BALON"
    SIN_BALON = "SIN_BALON"


# ---------- CU-42, CU-46 Metricas de equipo ----------

class MetricaEquipo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipo: Lado
    posesion_pct: float = Field(ge=0, le=100)
    pases_intentados: int = 0
    pases_completados: int = 0
    distancia_m: float = 0
    tiros: int = 0
    entradas_ultimo_tercio: int = 0
    altura_linea_m: float | None = Field(default=None,
        description="CU-45. Posicion media de los 4 defensores mas retrasados, sin el arquero")
    amplitud_m: float | None = None
    compacidad_m: float | None = None
    degradada: bool = Field(default=False,
        description="True si se calculo sobre datos con calidad degradada")


class Intervalo(BaseModel):
    minuto_desde: int
    minuto_hasta: int
    local: MetricaEquipo
    visitante: MetricaEquipo


class MetricasPartido(BaseModel):
    partido_id: int
    acumulado_local: MetricaEquipo
    acumulado_visitante: MetricaEquipo
    ultimos_5_min_local: MetricaEquipo | None = None
    ultimos_5_min_visitante: MetricaEquipo | None = None


# ---------- CU-43 Metricas por jugador ----------

class MetricaJugador(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    jugador_id: int | None = Field(default=None,
        description="null cuando el identificador no fue asignado a un jugador")
    track_id: int
    nombre: str | None = None
    dorsal: int | None = None
    distancia_m: float
    velocidad_max_kmh: float
    sprints: int
    minutos_jugados: int


class MetricasJugadorPorIntervalo(BaseModel):
    jugador_id: int
    intervalos: list[dict] = Field(
        description="Uno por bloque de 5 minutos, con distancia, velocidad max y sprints")


# ---------- CU-44 Mapas de calor ----------

class CeldaCalor(BaseModel):
    x: float = Field(description="Centro de la celda, en metros")
    y: float
    valor: float = Field(ge=0, le=1, description="Normalizado de 0 a 1")


class MapaCalor(BaseModel):
    partido_id: int
    alcance: str = Field(description="equipo | linea | jugador")
    referencia_id: int | None = None
    largo_m: float
    ancho_m: float
    celdas: list[CeldaCalor]


# ---------- CU-47 Linea de tiempo ----------

class ItemLineaTiempo(BaseModel):
    t: float
    minuto: int
    tipo: str
    equipo: Lado | None = None
    jugador_id: int | None = None
    descripcion: str
    origen: str = Field(description="CAMARA o MANUAL: distingue lo inferido de lo cargado a mano")


class LineaTiempo(BaseModel):
    partido_id: int
    items: list[ItemLineaTiempo]


# ---------- CU-48 Red de pases ----------

class NodoPase(BaseModel):
    jugador_id: int
    nombre: str
    x_medio: float
    y_medio: float
    pases: int


class AristaPase(BaseModel):
    origen_id: int
    destino_id: int
    pases: int


class RedPases(BaseModel):
    partido_id: int
    desde_minuto: int
    hasta_minuto: int
    nodos: list[NodoPase]
    aristas: list[AristaPase]


# ---------- Eventos derivados ----------

class EventoDerivado(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: TipoEventoDerivado
    t: float
    minuto: int
    equipo: Lado
    jugador_origen_id: int | None = None
    jugador_destino_id: int | None = None
    x_o: float
    y_o: float
    x_d: float | None = None
    y_d: float | None = None
    resultado: str | None = None
    confianza: float = Field(ge=0, le=1)
    origen: str = "CAMARA"


# ---------- CU-57 Comparativa ----------

class Comparativa(BaseModel):
    metrica: str
    valor_partido: float
    promedio_temporada: float
    diferencia: float
    base_suficiente: bool = Field(
        description="False con menos de 3 partidos analizados")
