"""Modelos de Análisis Táctico  —  CU-40 … CU-48.

Tablas: MetricaIntervalo, MetricaTrackIntervalo (T-076). EventoDerivado sigue previsto.

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga. Las de métricas
cuelgan de `partido`: se accede a ellas solo después de
`verificar_pertenencia(partido)`.
"""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetricaIntervalo(Base):
    """Métricas de un equipo en un intervalo de 5 minutos (CU-42, CU-46, T-076).

    Se escribe al CERRARSE el intervalo, durante el partido; el último se cierra
    como `parcial` al finalizar. Se guardan sumas y no promedios (posesión en
    segundos, bloque como suma + cantidad de muestras) para poder acumular
    varios intervalos sin perder precisión.
    """

    __tablename__ = "metrica_intervalo"
    __table_args__ = (
        UniqueConstraint("partido_id", "intervalo", "equipo",
                         name="ux_metrica_intervalo_partido_intervalo_equipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(
        ForeignKey("partido.id", ondelete="CASCADE"), index=True)
    intervalo: Mapped[int] = mapped_column(Integer)          # t // 300
    equipo: Mapped[str] = mapped_column(String(15))          # LOCAL | VISITANTE
    minuto_desde: Mapped[int] = mapped_column(Integer)
    minuto_hasta: Mapped[int] = mapped_column(Integer)
    t_desde: Mapped[float] = mapped_column(Float)
    t_hasta: Mapped[float] = mapped_column(Float)
    parcial: Mapped[bool] = mapped_column(Boolean, default=False)

    posesion_s: Mapped[float] = mapped_column(Float, default=0.0)
    disputa_s: Mapped[float] = mapped_column(Float, default=0.0)   # igual en las dos filas
    pases_intentados: Mapped[int] = mapped_column(Integer, default=0)
    pases_completados: Mapped[int] = mapped_column(Integer, default=0)
    distancia_m: Mapped[float] = mapped_column(Float, default=0.0)
    suma_altura_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_altura: Mapped[int] = mapped_column(Integer, default=0)
    suma_amplitud_m: Mapped[float] = mapped_column(Float, default=0.0)
    suma_compacidad_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_forma: Mapped[int] = mapped_column(Integer, default=0)


class MetricaTrackIntervalo(Base):
    """Métricas físicas de un TRACK en un intervalo (CU-43, T-075/T-076).

    Por track y no por jugador: el analista asigna los tracks después
    (CU-34, CU-35). La conversión a jugador se hace al consultar, con las
    vigencias de `asignacion_track`, así una reasignación tardía no obliga a
    recalcular.
    """

    __tablename__ = "metrica_track_intervalo"
    __table_args__ = (
        UniqueConstraint("partido_id", "intervalo", "track_id",
                         name="ux_metrica_track_intervalo_partido_intervalo_track"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(
        ForeignKey("partido.id", ondelete="CASCADE"), index=True)
    intervalo: Mapped[int] = mapped_column(Integer)
    track_id: Mapped[int] = mapped_column(Integer)
    equipo: Mapped[str] = mapped_column(String(20))   # el del primer mensaje del track
    t_desde: Mapped[float] = mapped_column(Float)      # primera y última muestra observada
    t_hasta: Mapped[float] = mapped_column(Float)
    tiempo_s: Mapped[float] = mapped_column(Float, default=0.0)
    distancia_m: Mapped[float] = mapped_column(Float, default=0.0)
    velocidad_max_ms: Mapped[float] = mapped_column(Float, default=0.0)
    sprints: Mapped[int] = mapped_column(Integer, default=0)
