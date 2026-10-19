"""Esquemas de Operacion del Partido  —  CU-30 … CU-39.

Incluye el contrato del mensaje que el worker de vision envia por WebSocket,
que es la pieza que permite a Web y Movil construir en paralelo (Pb-26).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.deportivo.schemas import Direccion


class TipoEventoManual(StrEnum):
    GOL = "GOL"
    AMARILLA = "AMARILLA"
    ROJA = "ROJA"
    SUSTITUCION = "SUSTITUCION"


class Lado(StrEnum):
    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"


class EquipoDetectado(StrEnum):
    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"
    ARBITRO = "ARBITRO"
    DESCONOCIDO = "DESCONOCIDO"


# ---------- CU-30, CU-31 Control del partido ----------

class IniciarPartido(BaseModel):
    ataca_hacia: Direccion = Field(
        description="CU-31. Obligatorio: sin esto las metricas espaciales del 2do tiempo salen espejadas")


class Descuento(BaseModel):
    minutos: int = Field(ge=0, le=15)


class EstadoEnVivo(BaseModel):
    """Lo que ve el DT en el panel. Se difunde por WebSocket."""
    partido_id: int
    parte: int = Field(ge=0, le=2)
    minuto: int
    segundo: int
    en_curso: bool
    goles_favor: int
    goles_contra: int
    posesion_local_pct: float | None = None
    calidad: "IndicadorCalidad"


class IndicadorCalidad(BaseModel):
    """CU-39. Degradacion explicita: una metrica silenciosamente equivocada es
    peor que una metrica ausente."""
    worker_conectado: bool
    fps: float = 0
    jugadores_detectados: int = 0
    balon_visible: bool = False
    retraso_s: float = 0
    degradado: bool = Field(default=False,
        description="True con menos de 16 jugadores por mas de 10 s, o balon perdido por mas de 15 s")
    motivo: str | None = None


# ---------- CU-36, CU-37, CU-38 Eventos manuales ----------

class EventoManualCrear(BaseModel):
    tipo: TipoEventoManual
    minuto: int | None = Field(default=None,
        description="Si se omite, se toma del cronometro del partido")
    equipo: Lado = Lado.LOCAL
    jugador_id: int | None = None
    jugador_entra_id: int | None = Field(default=None,
        description="Solo para SUSTITUCION")


class EventoManual(EventoManualCrear):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    minuto: int
    origen: str = "MANUAL"
    convertida_en_roja: bool = Field(default=False,
        description="True cuando una segunda amarilla se convirtio automaticamente")


# ---------- CU-34, CU-35 Asignacion de identificadores ----------

class TrackDetectado(BaseModel):
    track_id: int
    equipo_detectado: EquipoDetectado
    jugador_id: int | None = None
    desde_t: float
    hasta_t: float | None = None
    confianza: float = Field(ge=0, le=1)


class AsignarTrack(BaseModel):
    jugador_id: int | None = Field(description="null desasigna el identificador")


# ---------- Contrato del worker de vision (Pb-26) ----------

class PosicionDetectada(BaseModel):
    tid: int = Field(description="Identificador de ByteTrack, no el dorsal")
    equipo: EquipoDetectado
    x: float = Field(description="Metros sobre el largo de la cancha")
    y: float = Field(description="Metros sobre el ancho de la cancha")
    conf: float = Field(ge=0, le=1)


class MensajeWorker(BaseModel):
    """Lo que el worker de vision envia al backend cinco veces por segundo.

    Unos 23 puntos por mensaje, entre 5 y 10 KB/s. El video nunca sale de la
    cancha: solo viajan estas coordenadas.
    """
    model_config = ConfigDict(json_schema_extra={"example": {
        "partido": 42, "t": 1873.4,
        "jugadores": [
            {"tid": 7, "equipo": "LOCAL", "x": 52.3, "y": 31.8, "conf": 0.91},
            {"tid": 12, "equipo": "VISITANTE", "x": 61.0, "y": 44.2, "conf": 0.88},
        ],
        "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 55.1, "y": 33.0, "conf": 0.62},
        "calidad": {"worker_conectado": True, "fps": 5.0, "jugadores_detectados": 21,
                    "balon_visible": True, "retraso_s": 0.4, "degradado": False},
    }})

    partido: int
    t: float = Field(description="Segundos desde el inicio del partido")
    jugadores: list[PosicionDetectada]
    balon: PosicionDetectada | None = None
    calidad: IndicadorCalidad


class TokenIngesta(BaseModel):
    """T-033. Credencial del worker para publicar en /ingesta de un solo partido."""
    token: str = Field(description="Enviarlo en el primer mensaje: {\"tipo\": \"auth\", \"token\": ...}")
    partido_id: int
    expira_en: datetime


class RangoPosiciones(BaseModel):
    partido_id: int
    desde_t: float
    hasta_t: float
    muestras: list[MensajeWorker]


EstadoEnVivo.model_rebuild()
