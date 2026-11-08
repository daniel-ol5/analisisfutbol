"""Modelos de Visión por Computadora  —  CU-18 … CU-29.

Tablas previstas: Calibracion, ModeloML, Video

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Calibracion(Base):
    """Calibración de la cámara de un partido (CU-19, CU-20).

    Una calibración por partido y club. T-028 guarda los puntos marcados y
    las medidas reales de la cancha; T-029 calcula `matriz_h`, los errores y
    `valida` al guardar (ver `app/vision/homografia.py`). Son nulos solo en filas
    anteriores a T-029.
    """

    __tablename__ = "calibracion"
    __table_args__ = (
        UniqueConstraint("club_id", "partido_id", name="uq_calibracion_club_partido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    # TODO: agregar ForeignKey("partido.id") cuando la tabla Partido llegue a main.
    # Mientras tanto no se valida que el partido exista: solo que sea del club.
    partido_id: Mapped[int] = mapped_column(Integer, index=True)

    largo_m: Mapped[float] = mapped_column(Float)
    ancho_m: Mapped[float] = mapped_column(Float)
    # JSON genérico: funciona igual en SQLite y PostgreSQL.
    puntos_imagen: Mapped[list[dict[str, float]]] = mapped_column(JSON)
    puntos_cancha: Mapped[list[dict[str, float]]] = mapped_column(JSON)

    # none_as_null: sin esto, None se guardaría como el JSON `null` y no como NULL de SQL.
    matriz_h: Mapped[list[list[float]] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    error_medio_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_max_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    valida: Mapped[bool] = mapped_column(default=False)
    coef_distorsion: Mapped[list[float] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ModeloML(Base):
    """Versión entrenada de un modelo YOLO (CU-29).

    Cada `POST /modelos` registra una versión ya entrenada (con sus métricas),
    nunca entrena nada aquí. `activo` marca cuál usa el worker en el próximo
    procesamiento (T-059); `activar_modelo` en `service.py` garantiza que haya
    como máximo una activa por club, lo que permite "volver atrás" a una
    versión anterior sin reentrenar: activarla de nuevo alcanza.
    """

    __tablename__ = "modelo_ml"
    __table_args__ = (
        UniqueConstraint("club_id", "nombre", "version", name="uq_modelo_club_nombre_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)

    nombre: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(20))
    archivo_url: Mapped[str] = mapped_column(String(400))

    map50_jugador: Mapped[float | None] = mapped_column(Float, nullable=True)
    map50_balon: Mapped[float | None] = mapped_column(Float, nullable=True)
    idf1: Mapped[float | None] = mapped_column(Float, nullable=True)
    notas: Mapped[str] = mapped_column(default="")

    activo: Mapped[bool] = mapped_column(default=False, index=True)
    entrenado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # T-064: quién activó esta versión, cuándo y, si tenía métricas peores que
    # la vigente, por qué se forzó (volver atrás).
    activado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    motivo_activacion: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Video(Base):
    """Video grabado de un partido (CU-27, CU-28).

    T-060: se carga por partes. Mientras `bytes_recibidos < tamano_bytes` está
    en CARGANDO; al llegar el último trozo se lee con OpenCV y pasa a SUBIDO
    (o a ERROR si el archivo no es un video legible). `archivo_url` es la clave
    en el almacén (ver `app/vision/almacen.py`), no una URL pública.
    """

    __tablename__ = "video"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id"), index=True)
    modelo_id: Mapped[int | None] = mapped_column(ForeignKey("modelo_ml.id"), nullable=True)

    archivo_url: Mapped[str] = mapped_column(String(400))
    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(80))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    bytes_recibidos: Mapped[int] = mapped_column(BigInteger, default=0)

    duracion_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolucion: Mapped[str | None] = mapped_column(String(20), nullable=True)

    estado: Mapped[str] = mapped_column(String(20), default="CARGANDO", index=True)
    progreso_pct: Mapped[int] = mapped_column(Integer, default=0)
    mensaje_error: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # T-061: procesamiento diferido. `color_rival` lo indica quien lanza el
    # proceso; `tomado_en` es cuándo un worker tomó el trabajo, y se renueva con
    # cada lote: si deja de llegar (worker caído), otro worker puede retomarlo.
    color_rival: Mapped[str | None] = mapped_column(String(7), nullable=True)
    tomado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # HU-25 · Criterio 2: cuándo el worker empezó; base del tiempo restante.
    iniciado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    procesado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def tiempo_restante_s(self) -> int | None:
        """HU-25 · Criterio 2: segundos que faltan, al ritmo que lleva.

        Si en `t` segundos hizo el `p` %, el resto (100 - p) % lleva
        t·(100 - p)/p. Sin avance todavía (o en cola) no hay base para estimar:
        null. Terminado: 0.
        """
        if self.estado == "PROCESADO":
            return 0
        if self.estado != "PROCESANDO" or self.iniciado_en is None or self.progreso_pct <= 0:
            return None
        inicio = self.iniciado_en
        if inicio.tzinfo is None:  # SQLite devuelve la fecha sin zona; se guardó en UTC
            inicio = inicio.replace(tzinfo=UTC)
        transcurrido = max((datetime.now(UTC) - inicio).total_seconds(), 0.0)
        return round(transcurrido * (100 - self.progreso_pct) / self.progreso_pct)
