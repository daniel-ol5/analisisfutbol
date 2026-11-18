"""Reglas configurables y recomendaciones persistidas de un partido (CU-49)."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.asistencia.schemas import EstadoRecomendacion, Prioridad
from app.core.database import Base


class ReglaTactica(Base):
    __tablename__ = "regla_tactica"
    __table_args__ = (
        CheckConstraint("cooldown_s BETWEEN 30 AND 3600", name="ck_regla_tactica_cooldown"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int | None] = mapped_column(ForeignKey("club.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    condicion: Mapped[dict] = mapped_column(JSON)
    plantilla_mensaje: Mapped[str] = mapped_column(Text)
    plantilla_justificacion: Mapped[str] = mapped_column(Text, default="")
    prioridad: Mapped[str] = mapped_column(String(10), default=Prioridad.MEDIA.value)
    cooldown_s: Mapped[int] = mapped_column(default=300)
    activa: Mapped[bool] = mapped_column(default=True)


class Recomendacion(Base):
    __tablename__ = "recomendacion"
    __table_args__ = (
        UniqueConstraint("partido_id", "regla_id", "t", name="ux_recomendacion_regla_instante"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id", ondelete="CASCADE"))
    regla_id: Mapped[int] = mapped_column(ForeignKey("regla_tactica.id"))
    t: Mapped[float] = mapped_column(Float)
    minuto: Mapped[int]
    mensaje: Mapped[str] = mapped_column(Text)
    justificacion: Mapped[str] = mapped_column(Text)
    prioridad: Mapped[str] = mapped_column(String(10))
    datos_soporte: Mapped[list[dict]] = mapped_column(JSON)
    estado: Mapped[str] = mapped_column(String(12), default=EstadoRecomendacion.PENDIENTE.value)
    util: Mapped[bool | None]
    comentario: Mapped[str | None] = mapped_column(String(400))
    vista_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
