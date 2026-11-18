"""Eventos derivados de la cámara  —  T-103 (CU-47).

El motor detecta pases (`MotorPartido.pases`); de cada uno salen eventos que se guardan
en `evento_derivado` con `origen = CAMARA`:

- pase completado           → PASE (EXITOSO) del que pasa.
- pase que cae en un rival  → PERDIDA (FALLIDO) del que pasó y RECUPERACION (EXITOSO) del
  rival que se quedó con el balón.

TIRO y FUERA están en el diagrama pero ningún detector los produce todavía.

Escritura: cada vez que se escribe se REEMPLAZAN todos los eventos de cámara del partido
(borrar + insertar), así es idempotente y sirve igual en vivo, al cerrar y al recalcular.
Los llamadores hacen el `commit`.

Lectura (CU-47): la línea de tiempo lee esta tabla. Con el partido en juego usa los pases
del motor en memoria (todavía no están todos guardados); si un partido terminó antes de que
existiera la tabla y no tiene eventos, quien llama los deriva de las posiciones.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis import persistencia
from app.analisis.models import EventoDerivado
from app.analisis.motor.posesion import Pase
from app.deportivo.models import Partido
from app.partido.models import AsignacionTrack

CAMARA = "CAMARA"


@dataclass(frozen=True, slots=True)
class EventoCamara:
    """Un evento de cámara, todavía sin jugadores: solo tracks (se resuelven al leer)."""
    tipo: str
    t: float
    equipo: str
    track_origen: int | None
    track_destino: int | None
    x_o: float
    y_o: float
    x_d: float | None
    y_d: float | None
    resultado: str

    @property
    def minuto(self) -> int:
        return int(self.t // 60)


def _rival(equipo: str) -> str:
    return "VISITANTE" if equipo == "LOCAL" else "LOCAL"


def de_pases(pases: Iterable[Pase]) -> list[EventoCamara]:
    """Los eventos de cámara que salen de los pases del motor, en orden de `t`."""
    eventos: list[EventoCamara] = []
    for p in pases:
        (x_o, y_o), (x_d, y_d) = p.origen_xy, p.destino_xy
        if p.completado:
            eventos.append(EventoCamara("PASE", p.t, p.equipo, p.origen_track, p.destino_track,
                                        x_o, y_o, x_d, y_d, "EXITOSO"))
        else:
            eventos.append(EventoCamara("PERDIDA", p.t, p.equipo, p.origen_track,
                                        p.destino_track, x_o, y_o, x_d, y_d, "FALLIDO"))
            # Quien recupera es el dueño del destino; el evento ocurre donde recibió el balón.
            eventos.append(EventoCamara("RECUPERACION", p.t, _rival(p.equipo), p.destino_track,
                                        None, x_d, y_d, None, None, "EXITOSO"))
    return eventos


# ---------------- Jugador de un track ----------------


def tramos_por_track(tramos: Iterable[AsignacionTrack]) -> dict[int, list[AsignacionTrack]]:
    por_track: dict[int, list[AsignacionTrack]] = defaultdict(list)
    for tramo in tramos:
        por_track[tramo.track_id].append(tramo)
    return por_track


def jugador_en(tramos: dict[int, list[AsignacionTrack]], track_id: int | None,
               t: float) -> int | None:
    """El jugador asignado al track en el instante `t` (None: sin asignar en ese momento)."""
    if track_id is None:
        return None
    for tramo in tramos.get(track_id, []):
        fin = tramo.hasta_t if tramo.hasta_t is not None else float("inf")
        if tramo.desde_t <= t <= fin:
            return tramo.jugador_id
    return None


# ---------------- Tabla ----------------


async def reemplazar(db: AsyncSession, partido: Partido, pases: Iterable[Pase]) -> int:
    """Reemplaza los eventos de cámara del partido por los de `pases`. Devuelve cuántos guardó.

    No hace `commit`. Los jugadores se anotan con las asignaciones vigentes AHORA; la lectura
    vuelve a resolverlos por track, así una reasignación posterior no deja datos viejos.
    """
    tramos = tramos_por_track(await persistencia.tramos_de(db, partido))
    filas = [
        {"partido_id": partido.id, "tipo": e.tipo, "t": round(e.t, 2), "minuto": e.minuto,
         "equipo": e.equipo, "track_origen_id": e.track_origen, "track_destino_id": e.track_destino,
         "jugador_origen_id": jugador_en(tramos, e.track_origen, e.t),
         "jugador_destino_id": jugador_en(tramos, e.track_destino, e.t),
         "x_o": round(e.x_o, 2), "y_o": round(e.y_o, 2),
         "x_d": round(e.x_d, 2) if e.x_d is not None else None,
         "y_d": round(e.y_d, 2) if e.y_d is not None else None,
         "resultado": e.resultado, "confianza": None, "origen": CAMARA}
        for e in de_pases(pases)
    ]
    await db.execute(delete(EventoDerivado).where(EventoDerivado.partido_id == partido.id,
                                                  EventoDerivado.origen == CAMARA))
    if filas:
        await db.execute(insert(EventoDerivado), filas)
    return len(filas)


async def leer(db: AsyncSession, partido_id: int) -> list[EventoCamara]:
    """Los eventos de cámara guardados del partido, ordenados por `t`."""
    filas = (await db.execute(
        select(EventoDerivado)
        .where(EventoDerivado.partido_id == partido_id, EventoDerivado.origen == CAMARA)
        .order_by(EventoDerivado.t, EventoDerivado.id)
    )).scalars().all()
    return [EventoCamara(f.tipo, float(f.t), f.equipo or "", f.track_origen_id,
                         f.track_destino_id, float(f.x_o or 0.0), float(f.y_o or 0.0),
                         f.x_d, f.y_d, f.resultado or "")
            for f in filas]
