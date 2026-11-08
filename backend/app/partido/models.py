"""Modelos de Operación del Partido  —  CU-30 … CU-39.

Tablas previstas: RelojPartido, Posicion, AsignacionTrack, EventoManual

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RelojPartido(Base):
    """Estado persistido del cronómetro de un partido (CU-30, T-065).

    Permite calcular el segundo exacto con el reloj del servidor sin modificar
    la tabla `partido` de gestión deportiva: el tiempo transcurrido es
    `acumulado_s` más `(ahora - inicio_utc)` cuando `en_curso` es True.
    """

    __tablename__ = "reloj_partido"
    __table_args__ = (
        UniqueConstraint("partido_id", name="uq_reloj_partido_partido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id"), index=True)

    parte: Mapped[int] = mapped_column(Integer, default=0)
    en_curso: Mapped[bool] = mapped_column(Boolean, default=False)
    inicio_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acumulado_s: Mapped[float] = mapped_column(Float, default=0.0)
    descuento_1_min: Mapped[int] = mapped_column(Integer, default=0)
    descuento_2_min: Mapped[int] = mapped_column(Integer, default=0)


class AsignacionTrack(Base):
    """Intervalo de asignación de un `track_id` de ByteTrack a un jugador (CU-34, CU-35, T-067).

    `hasta_t IS NULL` indica que el tramo está vigente. La restricción parcial
    única `ux_asignacion_track_partido_track_activo` garantiza a nivel de base
    de datos que nunca existan dos tramos vigentes para el mismo `(partido_id, track_id)`.
    """

    __tablename__ = "asignacion_track"
    __table_args__ = (
        Index(
            "ux_asignacion_track_partido_track_activo",
            "partido_id",
            "track_id",
            unique=True,
            postgresql_where=text("hasta_t IS NULL"),
            sqlite_where=text("hasta_t IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id"), index=True)
    track_id: Mapped[int] = mapped_column(Integer, index=True)
    jugador_id: Mapped[int | None] = mapped_column(
        ForeignKey("jugador.id"), nullable=True, index=True
    )

    equipo_detectado: Mapped[str] = mapped_column(String(20), default="DESCONOCIDO")
    desde_t: Mapped[float] = mapped_column(Float, default=0.0)
    hasta_t: Mapped[float | None] = mapped_column(Float, nullable=True)
    confianza: Mapped[float] = mapped_column(Float, default=0.0)

