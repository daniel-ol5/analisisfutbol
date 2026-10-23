"""Esquemas de Vision por Computadora  —  CU-18 … CU-29.

Este paquete NO ejecuta YOLO: el worker vive en `vision/` en la raiz del
repositorio y corre junto a la camara. Aca se administra su configuracion y
se reciben sus resultados.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TipoModelo(StrEnum):
    DETECCION = "DETECCION"
    POSE = "POSE"


class EstadoVideo(StrEnum):
    SUBIDO = "SUBIDO"
    PROCESANDO = "PROCESANDO"
    PROCESADO = "PROCESADO"
    ERROR = "ERROR"


# ---------- CU-19, CU-20, CU-21 Calibracion ----------

class Punto(BaseModel):
    # NaN e infinito no son JSON valido y PostgreSQL los rechaza al guardar.
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class CalibracionGuardar(BaseModel):
    """Se exigen al menos 8 puntos repartidos por toda la cancha.

    Con 4 la homografia ajusta exacta y el residual da cero, que no informa nada.
    Solo puntos sobre el plano del suelo: nunca el travesano, que esta a 2,44 m.
    """
    puntos_imagen: list[Punto] = Field(min_length=8,
        description="Puntos marcados sobre el cuadro, en pixeles")
    puntos_cancha: list[Punto] = Field(min_length=8,
        description="Los mismos puntos en metros sobre el plano de la cancha")
    largo_m: float = Field(default=105.0, gt=40, lt=130,
        description="Medida real: las canchas formativas casi nunca miden 105 x 68")
    ancho_m: float = Field(default=68.0, gt=25, lt=90)
    coef_distorsion: list[Annotated[float, Field(allow_inf_nan=False)]] | None = Field(
        default=None,
        description="CU-23, opcional. Obligatorio con gran angular o action cam")

    @model_validator(mode="after")
    def _misma_cantidad_de_puntos(self) -> Self:
        # Cada punto de la imagen se aparea con el punto de la cancha de igual indice.
        # No se valida que los puntos de cancha caigan dentro de largo_m x ancho_m:
        # el sistema de coordenadas de la cancha todavia no esta definido.
        if len(self.puntos_imagen) != len(self.puntos_cancha):
            raise ValueError(
                "puntos_imagen y puntos_cancha deben tener la misma cantidad de puntos "
                f"(recibidos {len(self.puntos_imagen)} y {len(self.puntos_cancha)})"
            )
        return self


class ErrorCalibracion(BaseModel):
    """CU-21: un error medio mayor a 2 m bloquea el inicio del partido."""
    error_medio_m: float
    error_max_m: float
    punto_peor: int = Field(description="Indice del punto con mayor residual")
    valida: bool
    mensaje: str


class Calibracion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    largo_m: float
    ancho_m: float
    puntos_imagen: list[Punto]
    puntos_cancha: list[Punto]
    # T-029 calcula la homografia y los errores. Hasta entonces son None y valida es False.
    matriz_h: list[list[float]] | None = Field(default=None,
        description="Matriz de homografia 3x3. None hasta que T-029 la calcule")
    error_medio_m: float | None = Field(default=None,
        description="None hasta que T-029 calcule el error de reproyeccion")
    error_max_m: float | None = Field(default=None,
        description="None hasta que T-029 calcule el error de reproyeccion")
    valida: bool
    coef_distorsion: list[float] | None = None
    creada_en: datetime


# ---------- CU-29 Modelos ----------

class ModeloCrear(BaseModel):
    nombre: str = Field(max_length=80, examples=["futbol-propio"])
    version: str = Field(max_length=20, examples=["v3"])
    tipo: TipoModelo = TipoModelo.DETECCION
    archivo_url: str = Field(max_length=400)
    map50_jugador: float | None = Field(default=None, ge=0, le=1, examples=[0.87])
    map50_balon: float | None = Field(default=None, ge=0, le=1, examples=[0.64])
    idf1: float | None = Field(default=None, ge=0, le=1, examples=[0.72])
    notas: str = ""


class Modelo(ModeloCrear):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activo: bool
    entrenado_en: datetime


# ---------- CU-27, CU-28 Video ----------

class Video(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    modelo_id: int | None = None
    archivo_url: str
    duracion_s: int | None = None
    fps: int | None = None
    resolucion: str | None = Field(default=None, examples=["3840x2160"])
    estado: EstadoVideo
    progreso_pct: int = Field(default=0, ge=0, le=100)
    mensaje_error: str | None = None
    procesado_en: datetime | None = None


class LanzarProceso(BaseModel):
    modelo_id: int | None = Field(default=None,
        description="Si se omite, usa el modelo marcado como activo")
