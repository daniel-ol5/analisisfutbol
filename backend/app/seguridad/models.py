"""Modelos de Seguridad y Administración  —  CU-01 … CU-08."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Rol(StrEnum):
    ADMIN = "ADMIN"
    DT = "DT"
    ANALISTA = "ANALISTA"
    ASISTENTE = "ASISTENTE"


class Club(Base):
    """Raíz del aislamiento multi-club: todo lo demás cuelga de acá."""

    __tablename__ = "club"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    ciudad: Mapped[str] = mapped_column(String(80), default="")
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="club")


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("email", name="uq_usuario_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)

    email: Mapped[str] = mapped_column(String(180))
    password_hash: Mapped[str] = mapped_column(String(120))
    nombre: Mapped[str] = mapped_column(String(80), default="")
    apellido: Mapped[str] = mapped_column(String(80), default="")
    rol: Mapped[Rol] = mapped_column(String(20), default=Rol.ADMIN)
    activo: Mapped[bool] = mapped_column(default=True)
    # CU-05: viaja en cada token como "ver". Cambiar la contraseña la sube y
    # deja sin efecto todos los tokens emitidos antes, en cualquier dispositivo.
    version_sesion: Mapped[int] = mapped_column(default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    club: Mapped[Club] = relationship(back_populates="usuarios")


class TokenRevocado(Base):
    """Lista negra persistida de tokens revocados (Pb-01).

    Guarda identificadores únicos de tokens (jti) para invalidar tokens de acceso
    o refresco tras logout o rotación.
    """

    __tablename__ = "token_revocado"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    revocado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    usuario: Mapped[Usuario] = relationship()
