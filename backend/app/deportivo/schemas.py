"""Esquemas de Gestion Deportiva  —  CU-09 … CU-17.

Contrato congelado en el Sprint 1. Web y Movil generan sus mocks de aca.
Cualquier cambio posterior se acuerda con las dos parejas antes de mergear.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Posicion(StrEnum):
    ARQUERO = "ARQ"
    DEFENSOR = "DEF"
    MEDIOCAMPISTA = "MED"
    DELANTERO = "DEL"


class Pie(StrEnum):
    IZQUIERDO = "IZQ"
    DERECHO = "DER"
    AMBOS = "AMBOS"


class EstadoPartido(StrEnum):
    PROGRAMADO = "PROGRAMADO"
    EN_CURSO = "EN_CURSO"
    FINALIZADO = "FINALIZADO"
    PROCESANDO = "PROCESANDO"
    ANALIZADO = "ANALIZADO"
    CANCELADO = "CANCELADO"


class Formacion(StrEnum):
    F_433 = "4-3-3"
    F_442 = "4-4-2"
    F_4231 = "4-2-3-1"
    F_352 = "3-5-2"


class Direccion(StrEnum):
    IZQUIERDA = "IZQ"
    DERECHA = "DER"


# ---------- CU-09, CU-10 Equipos e indumentaria ----------

class EquipoBase(BaseModel):
    nombre: str = Field(max_length=120, examples=["Primera Division"])
    categoria: str = Field(default="", max_length=40, examples=["Sub-17"])
    temporada: str = Field(default="", max_length=20, examples=["2026"])
    color_local: str = Field(default="#1E5AA8", pattern=r"^#[0-9A-Fa-f]{6}$")
    color_visitante: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    color_arquero: str = Field(default="#F2C200", pattern=r"^#[0-9A-Fa-f]{6}$")


class EquipoCrear(EquipoBase):
    pass


class EquipoEditar(BaseModel):
    nombre: str | None = None
    categoria: str | None = None
    temporada: str | None = None
    color_local: str | None = None
    color_visitante: str | None = None
    color_arquero: str | None = None


class Equipo(EquipoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    club_id: int
    activo: bool = True
    jugadores: int = Field(default=0, description="Cantidad de jugadores activos")


class AvisoColores(BaseModel):
    """CU-10: los colores de ambos equipos quedaron demasiado cerca en HSV."""
    hay_riesgo: bool
    distancia_hsv: float = Field(description="Distancia en el espacio HSV; menor a 40 es riesgoso")
    mensaje: str


# ---------- CU-11, CU-12 Jugadores ----------

class JugadorBase(BaseModel):
    nombre: str = Field(max_length=80, examples=["Marcelo"])
    apellido: str = Field(max_length=80, examples=["Moreno"])
    dorsal: int = Field(ge=1, le=99, examples=[9])
    posicion: Posicion = Posicion.MEDIOCAMPISTA
    pie_habil: Pie = Pie.DERECHO
    altura_cm: int = Field(ge=140, le=220, examples=[181],
                           description="Obligatoria: se usa para estimar el punto de apoyo en la proyeccion")
    peso_kg: int | None = Field(default=None, ge=40, le=130)
    fecha_nacimiento: date | None = None


class JugadorCrear(JugadorBase):
    equipo_id: int


class JugadorEditar(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    dorsal: int | None = Field(default=None, ge=1, le=99)
    posicion: Posicion | None = None
    pie_habil: Pie | None = None
    altura_cm: int | None = None
    peso_kg: int | None = None
    fecha_nacimiento: date | None = None


class Jugador(JugadorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipo_id: int
    activo: bool = True


class FilaImportacion(BaseModel):
    fila: int
    datos: dict
    error: str | None = None


class ResultadoImportacion(BaseModel):
    """CU-12: las filas validas se importan aunque otras fallen."""
    total: int
    importadas: int
    con_error: int
    detalle: list[FilaImportacion]


# ---------- CU-13 Competiciones ----------

class CompeticionCrear(BaseModel):
    nombre: str = Field(max_length=120, examples=["Torneo Apertura"])
    temporada: str = Field(max_length=20, examples=["2026"])
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class Competicion(CompeticionCrear):
    model_config = ConfigDict(from_attributes=True)
    id: int
    club_id: int


# ---------- CU-14, CU-15, CU-16 Partidos ----------

class PartidoCrear(BaseModel):
    equipo_id: int
    rival: str = Field(max_length=120, examples=["Club Atletico Rival"])
    es_local: bool = True
    fecha_hora: datetime
    sede: str = Field(default="", max_length=160, examples=["Cancha municipal"])
    competicion_id: int | None = None


class PartidoEditar(BaseModel):
    rival: str | None = None
    es_local: bool | None = None
    fecha_hora: datetime | None = None
    sede: str | None = None
    competicion_id: int | None = None


class Partido(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipo_id: int
    competicion_id: int | None = None
    rival: str
    es_local: bool
    fecha_hora: datetime
    sede: str
    estado: EstadoPartido
    ataca_hacia: Direccion | None = Field(
        default=None,
        description="Direccion de ataque en el PRIMER tiempo. Sin esto las metricas espaciales salen espejadas.")
    goles_favor: int = 0
    goles_contra: int = 0
    parte: int = Field(default=0, ge=0, le=2)
    minuto_actual: int = 0


class Cancelacion(BaseModel):
    motivo: str = Field(max_length=200, examples=["Suspendido por lluvia"])


# ---------- CU-17 Alineacion ----------

class JugadorAlineado(BaseModel):
    jugador_id: int
    es_titular: bool = True
    es_capitan: bool = False
    pos_x: float = Field(ge=0, le=100, description="Coordenada relativa en el plano, 0 a 100")
    pos_y: float = Field(ge=0, le=100)
    minuto_entra: int | None = None
    minuto_sale: int | None = None


class AlineacionGuardar(BaseModel):
    formacion: Formacion = Formacion.F_433
    jugadores: list[JugadorAlineado] = Field(
        description="Maximo 11 con es_titular=true")


class Alineacion(AlineacionGuardar):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
