"""Análisis en vivo: un motor por partido, alimentado por el almacén de posiciones.

T-074, T-075, T-076. El almacén de posiciones (`PosicionesEnLote`) es el
único punto por el que pasan TODAS las posiciones (/ingesta, /resultados y el
respaldo local), así que es el único lugar desde donde se alimenta el motor.

Ciclo de vida de un partido en este proceso:

1. Primera posición de un partido: si está EN_CURSO, se crea su motor. Si la
   tabla `posicion` ya tiene filas (la API se reinició en pleno partido), el
   motor se reconstruye con ellas ANTES de seguir. Si no está EN_CURSO, se
   ignora y se vuelve a consultar como mucho cada `REVISION_ESTADO_S`.
2. Cada muestra: el motor (puro) devuelve qué pasó; aquí se guardan los
   intervalos cerrados y se difunde por /vivo:
     - `posesion` cada segundo de partido,
     - `metricas_jugadores` cada 60 s de partido,
     - `intervalo` al cerrarse cada intervalo de 5 minutos.
3. `finalizar_partido` (CU-30) llama a `cerrar_partido`: el último intervalo
   se cierra como parcial y el motor se descarta.

Ningún error de aquí corta la ingesta: se registra y la difusión de posiciones
sigue igual.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.analisis import persistencia
from app.analisis.metricas import intervalo_de, jugadores_de_partido, motor_desde_tabla
from app.analisis.motor.motor import MotorPartido, Salida, minutos_de, porcentajes
from app.analisis.motor.muestras import muestra_de_mensaje
from app.analisis.parametros import PARAMETROS
from app.core.config import settings
from app.core.realtime import Hub, canal_partido, obtener_hub
from app.deportivo.models import Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.schemas import MensajeWorker

log = logging.getLogger(__name__)

# Sesiones sin pool, como las de la ingesta de tracks: el motor escribe desde el
# bucle del WebSocket y no debe compartir conexiones entre event loops.
_motor_bd = create_async_engine(settings.database_url, poolclass=NullPool)
SesionesAnalisis: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _motor_bd, expire_on_commit=False)

Vaciar = Callable[[], Awaitable[None]]


@dataclass
class _Vivo:
    motor: MotorPartido
    club_id: int


class AnalisisEnVivo:
    REVISION_ESTADO_S = 5.0

    def __init__(self, sesiones: async_sessionmaker[AsyncSession] | None = None,
                 hub: Hub | None = None,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.sesiones = sesiones or SesionesAnalisis
        self._hub = hub
        self.reloj = reloj
        self._vivos: dict[int, _Vivo] = {}
        self._descartados: dict[int, float] = {}
        self._candados: dict[int, asyncio.Lock] = {}

    @property
    def hub(self) -> Hub:
        return self._hub or obtener_hub()

    def motor(self, partido_id: int) -> MotorPartido | None:
        vivo = self._vivos.get(partido_id)
        return vivo.motor if vivo is not None else None

    def _candado(self, partido_id: int) -> asyncio.Lock:
        return self._candados.setdefault(partido_id, asyncio.Lock())

    # ---------------- entrada ----------------

    async def procesar(self, mensaje: MensajeWorker, vaciar: Vaciar | None = None) -> None:
        """Lo llama el almacén de posiciones con cada mensaje, ANTES de ponerlo en su buffer.

        `vaciar` guarda lo pendiente del partido: hace falta antes de reconstruir
        desde la tabla, para no perder lo que todavía estaba en memoria.
        """
        try:
            vivo = self._vivos.get(mensaje.partido)
            if vivo is None:
                vivo = await self._hidratar(mensaje.partido, vaciar)
                if vivo is None:
                    return
            salida = vivo.motor.procesar(muestra_de_mensaje(mensaje))
            await self._despachar(mensaje.partido, vivo, salida)
        except Exception:
            log.exception("Falló el análisis en vivo del partido %s", mensaje.partido)

    async def _hidratar(self, partido_id: int, vaciar: Vaciar | None) -> _Vivo | None:
        if self.reloj() < self._descartados.get(partido_id, float("-inf")):
            return None
        async with self._candado(partido_id):
            if partido_id in self._vivos:
                return self._vivos[partido_id]
            async with self.sesiones() as db:
                partido = await db.get(Partido, partido_id)
                en_curso = partido is not None and partido.estado == EstadoPartido.EN_CURSO.value
            if not en_curso:
                self._descartados[partido_id] = self.reloj() + self.REVISION_ESTADO_S
                return None

            if vaciar is not None:
                await vaciar()
            async with self.sesiones() as db:
                partido = await db.get(Partido, partido_id)
                assert partido is not None
                motor = await motor_desde_tabla(db, partido)
                # Tras un reinicio, por si algún cierre no llegó a guardarse.
                cerrados = [i for i in motor.intervalos.values() if i.cerrado]
                if cerrados:
                    await persistencia.guardar_intervalos(db, partido_id, cerrados)
                    await db.commit()
                vivo = _Vivo(motor, partido.club_id)
            if motor.t is not None:
                log.info("Motor del partido %s reconstruido hasta t=%.2f", partido_id, motor.t)
            self._vivos[partido_id] = vivo
            self._descartados.pop(partido_id, None)
            return vivo

    # ---------------- salida ----------------

    async def _despachar(self, partido_id: int, vivo: _Vivo, salida: Salida) -> None:
        motor = vivo.motor
        canal = canal_partido(vivo.club_id, partido_id)

        indices = list(dict.fromkeys([*salida.cerrados, *salida.corregidos]))
        if indices:
            intervalos = [motor.intervalos[k] for k in indices]
            async with self.sesiones() as db:
                await persistencia.guardar_intervalos(db, partido_id, intervalos)
                await db.commit()
            for intervalo in intervalos:
                await self.hub.difundir(canal, {
                    "tipo": "intervalo",
                    "datos": intervalo_de(intervalo).model_dump(mode="json"),
                })

        if salida.nuevo_segundo:
            await self.hub.difundir(canal, {"tipo": "posesion",
                                            "datos": datos_posesion(partido_id, motor)})

        if salida.nuevo_minuto:
            async with self.sesiones() as db:
                partido = await db.get(Partido, partido_id)
                assert partido is not None
                # El analista puede asignar el arquero durante el partido.
                motor.actualizar_arqueros(await persistencia.arqueros_de(db, partido))
                if await self.hub.conectados(canal) == 0:
                    return
                filas = await jugadores_de_partido(db, partido, motor)
            await self.hub.difundir(canal, {
                "tipo": "metricas_jugadores",
                "datos": {
                    "partido_id": partido_id,
                    "t": motor.t,
                    "local": [m.model_dump(mode="json") for e, m in filas if e == "LOCAL"],
                    "visitante": [m.model_dump(mode="json") for e, m in filas
                                  if e == "VISITANTE"],
                },
            })

    # ---------------- fin del partido ----------------

    async def cerrar_partido(self, partido_id: int) -> None:
        """T-076: cierra el último intervalo como parcial, lo guarda, lo difunde y suelta el motor.

        Si este proceso no tenía el motor (reinicio sin posiciones nuevas), lo
        reconstruye desde la tabla para poder cerrar igual.
        """
        try:
            async with self._candado(partido_id):
                vivo = self._vivos.pop(partido_id, None)
                self._descartados[partido_id] = self.reloj() + self.REVISION_ESTADO_S
                async with self.sesiones() as db:
                    partido = await db.get(Partido, partido_id)
                    if partido is None:
                        return
                    if vivo is None:
                        vivo = _Vivo(await motor_desde_tabla(db, partido), partido.club_id)
                        reconstruido = True
                    else:
                        reconstruido = False
                    indice = vivo.motor.cerrar()
                    if indice is None:
                        return
                    guardar = ([i for i in vivo.motor.intervalos.values() if i.cerrado]
                               if reconstruido else [vivo.motor.intervalos[indice]])
                    await persistencia.guardar_intervalos(db, partido_id, guardar)
                    await db.commit()
            await self.hub.difundir(canal_partido(vivo.club_id, partido_id), {
                "tipo": "intervalo",
                "datos": intervalo_de(vivo.motor.intervalos[indice]).model_dump(mode="json"),
            })
        except Exception:
            log.exception("No se pudo cerrar el último intervalo del partido %s", partido_id)


def datos_posesion(partido_id: int, motor: MotorPartido) -> dict[str, Any]:
    """Contenido del mensaje `posesion` (T-074)."""
    local, visitante, disputa = porcentajes(motor.total)
    abierto = motor.abierto
    intervalo = None
    if abierto is not None:
        il, iv, idisp = porcentajes(abierto)
        desde, hasta = minutos_de(abierto, PARAMETROS)
        intervalo = {"minuto_desde": desde, "minuto_hasta": hasta,
                     "local_pct": il, "visitante_pct": iv, "disputa_pct": idisp}
    poseedor = motor.poseedor
    return {
        "partido_id": partido_id,
        "t": motor.t,
        "acumulado": {"local_pct": local, "visitante_pct": visitante, "disputa_pct": disputa},
        "intervalo": intervalo,
        "estado": poseedor.estado.value if poseedor is not None else None,
        "poseedor": ({"equipo": poseedor.estado.value, "track_id": poseedor.track_id}
                     if poseedor is not None and poseedor.track_id is not None else None),
    }


# ---------------- Una instancia por proceso ----------------

_analisis: dict[str, AnalisisEnVivo] = {}


def obtener_analisis_en_vivo() -> AnalisisEnVivo:
    if "unico" not in _analisis:
        _analisis["unico"] = AnalisisEnVivo()
    return _analisis["unico"]


def reiniciar_analisis_en_vivo(analisis: AnalisisEnVivo | None = None) -> None:
    """Para pruebas: descarta los motores (simula un reinicio) o instala otra instancia."""
    _analisis.clear()
    if analisis is not None:
        _analisis["unico"] = analisis
