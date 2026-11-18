"""Modelos de Análisis Táctico  —  CU-40 … CU-48.

Tablas: MetricaIntervalo, MetricaTrackIntervalo (T-076), EventoDerivado (T-103).

Todas las tablas de este paquete llevan `club_id` para el aislamiento entre
clubes (Pb-03), salvo las que cuelgan de otra que ya lo tenga. Las de métricas
cuelgan de `partido`: se accede a ellas solo después de
`verificar_pertenencia(partido)`.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
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
    # T-102 (CU-45): lo mismo separado por fase (cb = con balón, sb = sin balón).
    suma_altura_cb_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_altura_cb: Mapped[int] = mapped_column(Integer, default=0)
    suma_amplitud_cb_m: Mapped[float] = mapped_column(Float, default=0.0)
    suma_compacidad_cb_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_forma_cb: Mapped[int] = mapped_column(Integer, default=0)
    suma_altura_sb_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_altura_sb: Mapped[int] = mapped_column(Integer, default=0)
    suma_amplitud_sb_m: Mapped[float] = mapped_column(Float, default=0.0)
    suma_compacidad_sb_m: Mapped[float] = mapped_column(Float, default=0.0)
    n_forma_sb: Mapped[int] = mapped_column(Integer, default=0)


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


class EventoDerivado(Base):
    """Evento inferido por la cámara a partir de las posiciones  —  T-103 (CU-47).

    Tipos de docs/diagramas/modelo-datos.puml (`evento_derivado`). Lo escribe el motor
    de análisis (`app/analisis/eventos.py`): al cerrarse cada intervalo en vivo, al
    finalizar el partido y al recalcular (CU-46). Cada escritura reemplaza TODOS los
    eventos de cámara del partido, así que es idempotente y no deja duplicados.

    - `origen` es CAMARA para lo que sale de aquí. Los eventos cargados a mano viven en
      `evento_manual`; la línea de tiempo (CU-47) junta las dos tablas y distingue el
      origen con esta columna y con la procedencia de cada fila.
    - Coordenadas en metros de cancha, crudas (sin normalizar por dirección de ataque).
    - `track_origen_id` / `track_destino_id` NO están en el diagrama: se agregan porque
      el jugador de un track puede reasignarse después (CU-34/35). Con ellos la lectura
      resuelve el jugador vigente; `jugador_*_id` queda como la foto al escribir.
    - `confianza` es NULL: los eventos salen de reglas deterministas sobre posesión y
      balón, no de un modelo que devuelva una confianza.
    - Sin `club_id`: cuelga de `partido` (verificar pertenencia antes de acceder).
    """

    __tablename__ = "evento_derivado"
    __table_args__ = (
        # La línea de tiempo y el borrado por partido consultan un partido ordenado por t.
        Index("ix_evento_derivado_partido_t", "partido_id", "t"),
    )

    # Un partido genera miles de eventos: BigInteger.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partido.id", ondelete="CASCADE"))
    jugador_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("jugador.id", ondelete="SET NULL"), nullable=True)
    jugador_destino_id: Mapped[int | None] = mapped_column(
        ForeignKey("jugador.id", ondelete="SET NULL"), nullable=True)
    track_origen_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    track_destino_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(String(15))            # PASE|PERDIDA|RECUPERACION|TIRO|FUERA
    t: Mapped[float] = mapped_column(Numeric(8, 2, asdecimal=False))
    minuto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    equipo: Mapped[str | None] = mapped_column(String(15), nullable=True)   # LOCAL|VISITANTE
    x_o: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    y_o: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    x_d: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    y_d: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=True)
    resultado: Mapped[str | None] = mapped_column(String(10), nullable=True)   # EXITOSO|FALLIDO
    confianza: Mapped[float | None] = mapped_column(Numeric(4, 3, asdecimal=False), nullable=True)
    origen: Mapped[str] = mapped_column(
        String(10), default="CAMARA", server_default="CAMARA")                  # CAMARA|MANUAL
