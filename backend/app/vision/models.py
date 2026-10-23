"""Modelos de Visión por Computadora  —  CU-18 … CU-29.

Tablas previstas: Calibracion, ModeloML, Video

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Calibracion(Base):
    """Calibración de la cámara de un partido (CU-19, CU-20).

    Una calibración por partido y club. T-028 solo guarda los puntos marcados y
    las medidas reales de la cancha; `matriz_h`, los errores y `valida` los
    calcula T-029 y quedan sin valor (None / False) hasta entonces.
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
