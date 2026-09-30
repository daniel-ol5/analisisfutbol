"""Esquemas de Asistencia y Reportes  —  CU-49 … CU-58.

La capa que da valor al entrenador. La explicabilidad no es un adorno: ningun
DT obedece a un sistema que no muestra por que.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Prioridad(StrEnum):
    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class EstadoRecomendacion(StrEnum):
    PENDIENTE = "PENDIENTE"
    VISTA = "VISTA"
    APLICADA = "APLICADA"
    DESCARTADA = "DESCARTADA"


class EstadoInforme(StrEnum):
    GENERANDO = "GENERANDO"
    LISTO = "LISTO"
    ERROR = "ERROR"


# ---------- CU-49, CU-54 Reglas tacticas ----------

class ReglaBase(BaseModel):
    nombre: str = Field(max_length=120, examples=["Linea defensiva demasiado baja"])
    condicion: dict = Field(
        description="Expresion evaluable sobre el estado del partido",
        examples=[{"y": [{"<": ["altura_linea_m", 25]},
                         {">": ["posesion_rival_5min", 60]},
                         {">=": ["minuto", 20]}]}])
    plantilla_mensaje: str = Field(
        examples=["Adelantar la linea: estamos replegados a {altura} m"])
    plantilla_justificacion: str = Field(default="",
        examples=["La linea bajo de {altura_inicial} a {altura} m y el rival acumula {posesion}% de posesion."])
    prioridad: Prioridad = Prioridad.MEDIA
    cooldown_s: int = Field(default=300, ge=30, le=3600,
        description="El motor evalua 5 veces por segundo: sin esto una regla dispara cientos de veces")
    activa: bool = True


class ReglaCrear(ReglaBase):
    pass


class ReglaEditar(BaseModel):
    nombre: str | None = None
    condicion: dict | None = None
    plantilla_mensaje: str | None = None
    plantilla_justificacion: str | None = None
    prioridad: Prioridad | None = None
    cooldown_s: int | None = None
    activa: bool | None = None


class Regla(ReglaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    club_id: int | None = Field(default=None,
        description="null significa regla global del sistema, visible para todos los clubes")


class PruebaRegla(BaseModel):
    """CU-54: probar una regla contra un partido ya registrado."""
    partido_id: int


class ResultadoPrueba(BaseModel):
    disparos: int
    minutos: list[int]


# ---------- CU-50, CU-51, CU-52 Recomendaciones ----------

class DatoSoporte(BaseModel):
    metrica: str
    valor: float
    umbral: float | None = None


class Recomendacion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    regla_id: int
    t: float
    minuto: int
    mensaje: str = Field(examples=["Atacar por banda derecha"])
    justificacion: str = Field(
        examples=["Su lateral izquierdo perdio 7 de 11 duelos y solo el 18% de nuestros ataques fue por ese sector."])
    prioridad: Prioridad
    datos_soporte: list[DatoSoporte]
    estado: EstadoRecomendacion
    util: bool | None = None
    comentario: str | None = None
    vista_en: datetime | None = None


class Valoracion(BaseModel):
    """CU-51. La meta de calidad del proyecto es al menos 70% marcadas como utiles."""
    util: bool | None = Field(default=None, description="null cuando solo se marca como aplicada")
    aplicada: bool = False
    comentario: str = Field(default="", max_length=400)


# ---------- CU-55, CU-56 Informes ----------

class Informe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    estado: EstadoInforme
    archivo_url: str | None = None
    error_calibracion_m: float | None = Field(default=None,
        description="Se incluye en el informe para que el lector sepa cuanto confiar en los numeros")
    recomendaciones_utiles_pct: float | None = None
    generado_en: datetime | None = None


class FormatoExportacion(StrEnum):
    METRICAS_EQUIPO = "metricas_equipo"
    METRICAS_JUGADOR = "metricas_jugador"
    EVENTOS = "eventos"
