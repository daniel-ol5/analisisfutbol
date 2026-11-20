"""Uso diario del asistente, para el límite de preguntas por usuario."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConsultaAsistente(Base):
    """Cuántas preguntas hizo un usuario en un día (UTC). Una fila por usuario y día."""

    __tablename__ = "consulta_asistente"
    __table_args__ = (
        UniqueConstraint("usuario_id", "fecha", name="uq_consulta_asistente_usuario_fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    fecha: Mapped[date] = mapped_column(Date)
    cantidad: Mapped[int] = mapped_column(Integer, default=0)
