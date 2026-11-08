"""Modelos de Operación del Partido  —  CU-30 … CU-39.

Tablas previstas: Posicion, AsignacionTrack, EventoManual

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga.
"""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventoManual(Base):
    """Gol, tarjeta o sustitución registrada por una persona durante el partido.

    `uuid` prepara la idempotencia que necesita la cola offline de T-070. El
    borrado es lógico para poder deshacer sin perder la trazabilidad del evento.
    """

    __tablename__ = "evento_manual"
    __table_args__ = (
        UniqueConstraint("club_id", "uuid", name="uq_evento_manual_club_uuid"),
        CheckConstraint(
            "tipo IN ('GOL', 'AMARILLA', 'ROJA', 'SUSTITUCION')",
            name="ck_evento_manual_tipo",
        ),
        CheckConstraint(
            "equipo IN ('LOCAL', 'VISITANTE')",
            name="ck_evento_manual_equipo",
        ),
        CheckConstraint("origen = 'MANUAL'", name="ck_evento_manual_origen"),
        Index("ix_evento_manual_partido_creado", "partido_id", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id"), index=True)
    uuid: Mapped[str] = mapped_column(String(36))

    tipo: Mapped[str] = mapped_column(String(20))
    equipo: Mapped[str] = mapped_column(String(15))
    jugador_id: Mapped[int | None] = mapped_column(
        ForeignKey("jugador.id"), nullable=True, index=True
    )
    jugador_entra_id: Mapped[int | None] = mapped_column(
        ForeignKey("jugador.id"), nullable=True, index=True
    )
    minuto: Mapped[int]
    origen: Mapped[str] = mapped_column(String(15), default="MANUAL")
    convertida_en_roja: Mapped[bool] = mapped_column(default=False)

    capturado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    creado_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    anulado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
