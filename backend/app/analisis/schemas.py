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


# ---------- CU-45 Metricas tacticas colectivas ----------

class BloqueFase(BaseModel):
    """Altura de linea, amplitud y compacidad promediadas sobre una fase (T-102)."""
    altura_linea_m: float | None = Field(default=None,
        description="Distancia al arco propio, en metros: x media de los 4 jugadores de campo "
                    "mas retrasados; el arquero queda excluido")
    amplitud_m: float | None = Field(default=None,
        description="Ancho del equipo, en metros: distancia entre los dos jugadores mas abiertos")
    compacidad_m2: float | None = Field(default=None,
        description="Area, en m2, del poligono envolvente de los jugadores de campo; "
                    "menos area = equipo mas junto")
    muestras: int = Field(default=0, ge=0,
        description="Segundos de partido sobre los que se promedio; 0 = sin datos en la fase")


class MetricaTactica(BaseModel):
    equipo: Lado
    total: BloqueFase = Field(description="Las dos fases juntas, incluida la disputa")
    con_balon: BloqueFase = Field(description="El equipo posee el balon")
    sin_balon: BloqueFase = Field(description="Posee el rival. Disputa o balon no visible: ninguna fase")


class IntervaloTactico(BaseModel):
    minuto_desde: int
    minuto_hasta: int
    local: MetricaTactica
    visitante: MetricaTactica


class MetricasTacticas(BaseModel):
    partido_id: int
    local: MetricaTactica
    visitante: MetricaTactica
    intervalos: list[IntervaloTactico] = Field(
        default_factory=list, description="Solo intervalos cerrados, como CU-46")


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
    compacidad_m2: float | None = Field(default=None,
        description="CU-45. Area del poligono envolvente de los jugadores de campo, en m2")
    con_balon: BloqueFase | None = Field(default=None, description="T-102. Bloque con balon")
    sin_balon: BloqueFase | None = Field(default=None, description="T-102. Bloque sin balon")
    degradada: bool = Field(default=False,
        description="True si se calculo sobre datos con calidad degradada")


class Intervalo(BaseModel):
    minuto_desde: int
    minuto_hasta: int
    local: MetricaEquipo
    visitante: MetricaEquipo
    posesion_disputa_pct: float = Field(default=0, ge=0, le=100,
        description="T-074. Tiempo con el balon lejos de todos (> 2 m); "
                    "local + visitante + disputa = 100")


class MetricasPartido(BaseModel):
    partido_id: int
    acumulado_local: MetricaEquipo
    acumulado_visitante: MetricaEquipo
    ultimos_5_min_local: MetricaEquipo | None = None
    ultimos_5_min_visitante: MetricaEquipo | None = None
    posesion_disputa_pct: float = Field(default=0, ge=0, le=100,
        description="T-074. Acumulado en disputa; local + visitante + disputa = 100")


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
    dorsal: int | None = None
    equipo: Lado | None = None
    x_medio: float = Field(description="Posicion media del jugador en el rango pedido, "
                                       "normalizada por direccion de ataque")
    y_medio: float
    pases: int = Field(description="Pases completados que envio")
    pases_recibidos: int = Field(default=0, description="Pases completados que recibio")
    mayor_recepcion: bool = Field(default=False,
        description="Esta entre los que mas pases reciben de su equipo (los 3 primeros, con al "
                    "menos un pase recibido)")
    aislado: bool = Field(default=False,
        description="Desconectado del circuito: sus pases enviados + recibidos son menos de "
                    "la cuarta parte del promedio de su equipo (o ninguno)")


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
    confianza: float | None = Field(default=None, ge=0, le=1,
        description="Null: los eventos salen de reglas deterministas, no de un modelo")
    origen: str = "CAMARA"


# ---------- CU-57 Comparativa ----------

class Comparativa(BaseModel):
    metrica: str
    valor_partido: float
    promedio_temporada: float
    diferencia: float
    base_suficiente: bool = Field(
        description="False con menos de 3 partidos analizados")
