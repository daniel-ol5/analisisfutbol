"""Esquemas de Vision por Computadora  —  CU-18 … CU-29.

Este paquete NO ejecuta YOLO: el worker vive en `vision/` en la raiz del
repositorio y corre junto a la camara. Aca se administra su configuracion y
se reciben sus resultados.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.partido.schemas import MensajeWorker


class TipoModelo(StrEnum):
    DETECCION = "DETECCION"
    POSE = "POSE"


class EstadoVideo(StrEnum):
    CARGANDO = "CARGANDO"   # T-060: la carga por partes todavía no terminó
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
    # CU-23 (T-036). Opcionales y aditivos: con los TRES (matriz_camara,
    # coef_distorsion y tamano_imagen) los puntos de imagen se corrigen antes de
    # la homografía. Mismos nombres y formas que devuelve POST /calibracion-intrinseca.
    matriz_camara: list[list[Annotated[float, Field(allow_inf_nan=False)]]] | None = Field(
        default=None,
        description=(
            "CU-23, opcional. Matriz de la camara K (3x3, en pixeles), de POST "
            "/calibracion-intrinseca. Va junto con coef_distorsion y tamano_imagen: con los "
            "tres, los puntos_imagen se corrigen antes de calcular la homografia"))
    tamano_imagen: list[Annotated[int, Field(gt=0)]] | None = Field(
        default=None, min_length=2, max_length=2,
        description=(
            "CU-23, opcional. [ancho, alto] en pixeles de las fotos con que se calibro la "
            "camara. Los puntos_imagen deben marcarse sobre un cuadro de ese mismo tamano"))

    @property
    def tiene_intrinseca(self) -> bool:
        """True si llegaron los tres datos que hacen falta para corregir el lente."""
        return None not in (self.matriz_camara, self.coef_distorsion, self.tamano_imagen)

    @model_validator(mode="after")
    def _intrinseca_completa(self) -> Self:
        # coef_distorsion solo sigue aceptándose como hasta ahora (no corrige nada).
        # matriz_camara o tamano_imagen, en cambio, sin los otros dos no sirven.
        if self.matriz_camara is None and self.tamano_imagen is None:
            return self
        if not self.tiene_intrinseca:
            raise ValueError(
                "matriz_camara, coef_distorsion y tamano_imagen van juntos (CU-23): envia los "
                "tres, tal como los devuelve POST /calibracion-intrinseca, o ninguno")
        k = self.matriz_camara
        if len(k) != 3 or any(len(fila) != 3 for fila in k):
            raise ValueError("matriz_camara debe ser de 3x3")
        if k[0][0] <= 0 or k[1][1] <= 0 or k[2] != [0.0, 0.0, 1.0]:
            raise ValueError(
                "matriz_camara no es una matriz de camara: fx y fy deben ser positivos y la "
                "ultima fila [0, 0, 1]")
        if len(self.coef_distorsion) not in (4, 5, 8, 12, 14):
            raise ValueError(
                "coef_distorsion debe tener 4, 5, 8, 12 o 14 coeficientes (modelo de OpenCV)")
        return self

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
    punto_peor: int = Field(
        description="Indice (base 0) sobre la lista de puntos enviada del punto con mayor residual")
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
    # T-029 las calcula al guardar. Siguen siendo opcionales por si hay filas anteriores a T-029.
    matriz_h: list[list[float]] | None = Field(default=None,
        description="Matriz de homografia 3x3 (pixeles a metros), calculada al guardar")
    error_medio_m: float | None = Field(default=None,
        description="Error medio de reproyeccion en metros, calculado al guardar")
    error_max_m: float | None = Field(default=None,
        description="Error maximo de reproyeccion en metros, calculado al guardar")
    valida: bool
    coef_distorsion: list[float] | None = None
    creada_en: datetime
    matriz_camara: list[list[float]] | None = Field(default=None, description=(
        "CU-23: matriz de la camara K, si se envio. Con ella, matriz_h va de pixeles "
        "CORREGIDOS a metros: el worker debe corregir cada punto antes de aplicarla"))
    tamano_imagen: list[int] | None = Field(default=None, description=(
        "CU-23: [ancho, alto] de la calibracion de la camara, si se envio"))
    advertencia: str | None = Field(default=None, description=(
        "CU-22: solo en GET /sedes/{sede}/calibracion-previa. Recuerda verificar "
        "que la camara no se haya movido antes de reutilizar la calibracion"))


class CalibracionIntrinseca(BaseModel):
    """CU-23: parametros propios de la camara y el lente, de POST /calibracion-intrinseca.

    No se guardan solos: se envian (los tres primeros campos) en
    POST /partidos/{id}/calibracion junto con los puntos de la cancha.
    """
    matriz_camara: list[list[float]] = Field(description="K, 3x3, en pixeles")
    coef_distorsion: list[float] = Field(description="(k1, k2, p1, p2, k3) de OpenCV")
    tamano_imagen: list[int] = Field(description="[ancho, alto] en pixeles de las fotos")
    error_reproyeccion_px: float = Field(
        description="Error RMS de la calibracion: por debajo de 0,5 px es buena")
    imagenes_usadas: int = Field(description="Fotos en las que se detecto el tablero")


# ---------- CU-29 Modelos ----------

class ModeloCrear(BaseModel):
    nombre: str = Field(max_length=80, examples=["futbol-propio"])
    version: str = Field(max_length=20, examples=["v3"])
    tipo: TipoModelo = TipoModelo.DETECCION
    archivo_url: str = Field(max_length=400, examples=["https://cdn.club.com/modelos/futbol-v3.pt"])
    map50_jugador: float | None = Field(default=None, ge=0, le=1, examples=[0.87])
    map50_balon: float | None = Field(default=None, ge=0, le=1, examples=[0.64])
    idf1: float | None = Field(default=None, ge=0, le=1, examples=[0.72])
    notas: str = ""

    @field_validator("archivo_url")
    @classmethod
    def _solo_https(cls, v: str) -> str:
        # Criterio 3 de HU-26: el worker descarga el archivo del modelo sin
        # autenticacion propia, asi que http (sin cifrar) o un esquema que no
        # sea web (file://, s3://, ftp://...) no sirven en produccion.
        if not v.lower().startswith("https://"):
            raise ValueError("archivo_url debe ser una URL https")
        return v


class Modelo(ModeloCrear):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activo: bool
    entrenado_en: datetime
    activado_en: datetime | None = Field(default=None,
        description="Ultima vez que se activo esta version")
    motivo_activacion: str | None = Field(default=None,
        description="T-064: por que se activo aunque tuviera metricas peores (volver atras)")


class ActivarModelo(BaseModel):
    """T-064: una version con metricas peores que la activa no se activa, salvo
    que se fuerce a proposito (volver atras, criterio de T-059) y se diga por que."""

    forzar: bool = False
    motivo: str | None = Field(default=None, max_length=300,
        examples=["v4 confunde a los arbitros con jugadores; se vuelve a v3"])

    @model_validator(mode="after")
    def _forzar_con_motivo(self) -> Self:
        if self.forzar and not (self.motivo or "").strip():
            raise ValueError("Para activar una version peor hay que indicar el motivo")
        return self


# ---------- CU-27, CU-28 Video ----------

# T-060. Contenedores que el pipeline sabe leer (OpenCV + FFmpeg). Se validan
# ANTES de empezar la carga: un partido son varios GB y descubrir al final que
# el formato no sirve es perder una hora de subida.
FORMATOS_VIDEO: dict[str, tuple[str, ...]] = {
    ".mp4": ("video/mp4",),
    ".mov": ("video/quicktime",),
    ".mkv": ("video/x-matroska", "video/matroska"),
}


class VideoIniciar(BaseModel):
    """Primer paso de la carga por partes: se declara el archivo sin subirlo."""

    nombre: str = Field(min_length=1, max_length=200, examples=["fecha-12-vs-rival.mp4"],
        description="Nombre del archivo; su extension tiene que ser .mp4, .mov o .mkv")
    tipo: str = Field(max_length=80, examples=["video/mp4"],
        description="Tipo MIME que informa el navegador (File.type)")
    tamano_bytes: int = Field(gt=0, examples=[4_500_000_000],
        description="Tamano total; el maximo lo fija la configuracion del servidor")


class Video(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    partido_id: int
    modelo_id: int | None = None
    archivo_url: str
    nombre: str = Field(description="Nombre original del archivo")
    tipo: str
    tamano_bytes: int
    bytes_recibidos: int = Field(
        description="Para retomar una carga cortada: el siguiente trozo empieza en este byte")
    duracion_s: int | None = None
    fps: int | None = None
    resolucion: str | None = Field(default=None, examples=["3840x2160"])
    estado: EstadoVideo
    progreso_pct: int = Field(default=0, ge=0, le=100,
        description="Progreso del PROCESAMIENTO (CU-27), no de la carga")
    iniciado_en: datetime | None = Field(default=None,
        description="Cuando un worker empezo a procesarlo; null mientras espera en cola")
    tiempo_restante_s: int | None = Field(default=None, ge=0,
        description="HU-25. Estimado al ritmo actual; null en cola o sin avance, 0 al terminar")
    mensaje_error: str | None = None
    creado_en: datetime
    procesado_en: datetime | None = None


_HEX = r"^#[0-9A-Fa-f]{6}$"


class LanzarProceso(BaseModel):
    modelo_id: int | None = Field(default=None,
        description="Si se omite, usa el modelo marcado como activo; sin modelo activo, "
                    "el worker usa el YOLO preentrenado")
    color_rival: str | None = Field(default=None, pattern=_HEX, examples=["#C8102E"],
        description="Color de camiseta del rival en este partido. El backend solo conoce los "
                    "del equipo propio; sin este dato el worker separa los equipos por K-means "
                    "y toma como propio el grupo mas parecido a la camiseta registrada")


# ---------- T-061 Procesamiento diferido: contrato del worker ----------
#
# El worker corre en la maquina con GPU (vision/procesamiento/worker.py), se
# autentica como un usuario ADMIN o ANALISTA del club y:
#   1. POST /trabajos/tomar          toma el video PROCESANDO mas antiguo
#   2. GET  /videos/{id}/archivo     lo descarga (admite Range)
#   3. POST /videos/{id}/resultados  manda lotes de MensajeWorker + progreso
#   4. POST /videos/{id}/terminar    cierra con exito o con el motivo del error
# Un 409 en (3) significa que el procesamiento se cancelo: el worker se detiene.


class ModeloTrabajo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    version: str
    tipo: TipoModelo
    archivo_url: str


class Trabajo(BaseModel):
    """Todo lo que el worker necesita para procesar un video sin consultar nada mas."""

    video_id: int
    partido_id: int
    archivo: str = Field(description="Ruta de descarga del video, relativa a la API")
    nombre: str
    tamano_bytes: int
    fps: int | None
    duracion_s: int | None
    modelo: ModeloTrabajo | None = Field(
        description="null: usar el YOLO preentrenado (no hay modelo activo en el club)")
    matriz_h: list[list[float]] = Field(description="Homografia pixeles a metros (CU-26)")
    largo_m: float
    ancho_m: float
    es_local: bool = Field(description="Si el equipo propio es el LOCAL del mensaje")
    color_propio: str = Field(description="Camiseta del equipo propio en este partido")
    color_rival: str | None


class ResultadosLote(BaseModel):
    """Un lote de muestras del video: las mismas que manda el worker en vivo."""

    progreso_pct: int = Field(ge=0, le=99,
        description="Hasta 99: el 100 lo pone el backend al terminar")
    muestras: list[MensajeWorker] = Field(max_length=500,
        description="Cada una con el mismo contrato que /partido/{id}/ingesta")


class FinTrabajo(BaseModel):
    ok: bool
    mensaje_error: str | None = Field(default=None, max_length=400,
        description="Obligatorio si ok=false: es lo que ve el analista en la web")

    @model_validator(mode="after")
    def _error_con_motivo(self) -> Self:
        if not self.ok and not (self.mensaje_error or "").strip():
            raise ValueError("Un procesamiento fallido necesita mensaje_error")
        return self
