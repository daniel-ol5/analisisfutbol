"""Modelos de Gestión Deportiva  —  CU-09 … CU-17.

Tablas: Equipo, Jugador, Competicion, Partido, Alineacion, AlineacionJugador

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga.
"""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Equipo(Base):
    __tablename__ = "equipo"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)

    nombre: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str] = mapped_column(String(40), default="")
    temporada: Mapped[str] = mapped_column(String(20), default="")
    color_local: Mapped[str] = mapped_column(String(7), default="#1E5AA8")
    color_visitante: Mapped[str] = mapped_column(String(7), default="#FFFFFF")
    color_arquero: Mapped[str] = mapped_column(String(7), default="#F2C200")
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    jugadores: Mapped[list["Jugador"]] = relationship(back_populates="equipo")
    partidos: Mapped[list["Partido"]] = relationship(back_populates="equipo")


class Jugador(Base):
    __tablename__ = "jugador"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipo.id"), index=True)

    nombre: Mapped[str] = mapped_column(String(80))
    apellido: Mapped[str] = mapped_column(String(80))
    dorsal: Mapped[int] = mapped_column(Integer)
    posicion: Mapped[str] = mapped_column(String(10), default="MED")
    pie_habil: Mapped[str] = mapped_column(String(10), default="DER")
    altura_cm: Mapped[int] = mapped_column(Integer)
    peso_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    equipo: Mapped["Equipo"] = relationship(back_populates="jugadores")


class Competicion(Base):
    __tablename__ = "competicion"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)

    nombre: Mapped[str] = mapped_column(String(120))
    temporada: Mapped[str] = mapped_column(String(20), default="")
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    partidos: Mapped[list["Partido"]] = relationship(back_populates="competicion")


class Partido(Base):
    __tablename__ = "partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipo.id"), index=True)
    competicion_id: Mapped[int | None] = mapped_column(
        ForeignKey("competicion.id"), nullable=True, index=True
    )

    rival: Mapped[str] = mapped_column(String(120))
    es_local: Mapped[bool] = mapped_column(default=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sede: Mapped[str] = mapped_column(String(160), default="")
    estado: Mapped[str] = mapped_column(String(20), default="PROGRAMADO")
    ataca_hacia: Mapped[str | None] = mapped_column(String(10), nullable=True)
    goles_favor: Mapped[int] = mapped_column(default=0)
    goles_contra: Mapped[int] = mapped_column(default=0)
    parte: Mapped[int] = mapped_column(default=0)
    minuto_actual: Mapped[int] = mapped_column(default=0)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    equipo: Mapped["Equipo"] = relationship(back_populates="partidos")
    competicion: Mapped["Competicion | None"] = relationship(back_populates="partidos")
    alineaciones: Mapped[list["Alineacion"]] = relationship(back_populates="partido")


class Alineacion(Base):
    __tablename__ = "alineacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("club.id"), index=True)
    # CU-17: una sola alineación por partido; guardar de nuevo la reemplaza.
    partido_id: Mapped[int] = mapped_column(
        ForeignKey("partido.id"), index=True, unique=True
    )

    formacion: Mapped[str] = mapped_column(String(20), default="4-3-3")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    partido: Mapped["Partido"] = relationship(back_populates="alineaciones")
    jugadores_alineados: Mapped[list["AlineacionJugador"]] = relationship(
        back_populates="alineacion", cascade="all, delete-orphan"
    )


class AlineacionJugador(Base):
    __tablename__ = "alineacion_jugador"

    id: Mapped[int] = mapped_column(primary_key=True)
    alineacion_id: Mapped[int] = mapped_column(
        ForeignKey("alineacion.id"), index=True
    )
    jugador_id: Mapped[int] = mapped_column(ForeignKey("jugador.id"), index=True)

    es_titular: Mapped[bool] = mapped_column(default=True)
    es_capitan: Mapped[bool] = mapped_column(default=False)
    pos_x: Mapped[float] = mapped_column(Float, default=50.0)
    pos_y: Mapped[float] = mapped_column(Float, default=50.0)
    minuto_entra: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minuto_sale: Mapped[int | None] = mapped_column(Integer, nullable=True)

    alineacion: Mapped["Alineacion"] = relationship(back_populates="jugadores_alineados")
    jugador: Mapped["Jugador"] = relationship()
