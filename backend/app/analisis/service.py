"""Mapa de calor a partir de las posiciones observadas en cancha."""

import asyncio
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis import persistencia
from app.analisis.eventos import jugador_en, tramos_por_track
from app.analisis.motor.muestras import Muestra, muestra_de_mensaje
from app.analisis.schemas import CeldaCalor, MapaCalor
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Jugador, Partido
from app.partido.service import normalizar_coordenadas
from app.vision.models import Video
from app.vision.procesamiento import cargar_muestras_video
from app.vision.schemas import EstadoVideo

COLUMNAS = 21
FILAS = 14
POSICION_POR_LINEA = {1: "DEF", 2: "MED", 3: "DEL"}


async def calcular_mapa_calor(
    partido_id: int,
    alcance: Literal["equipo", "linea", "jugador"],
    referencia_id: int | None,
    desde_minuto: int,
    hasta_minuto: int,
    usuario: UsuarioActual,
    db: AsyncSession,
) -> MapaCalor:
    """Agrega ocupación real del equipo propio orientada en su dirección de ataque."""
    partido = verificar_pertenencia(await db.get(Partido, partido_id), usuario)
    jugadores: set[int] | None = None
    if alcance == "jugador":
        jugadores = set()
        if referencia_id is not None:
            jugador = verificar_pertenencia(
                await db.scalar(del_club(Jugador, usuario).where(Jugador.id == referencia_id)),
                usuario,
            )
            if jugador.equipo_id == partido.equipo_id:
                jugadores.add(jugador.id)
    elif alcance == "linea":
        posicion = POSICION_POR_LINEA.get(referencia_id or 2)
        jugadores = set(await db.scalars(
            del_club(Jugador, usuario).with_only_columns(Jugador.id)
            .where(Jugador.equipo_id == partido.equipo_id, Jugador.posicion == posicion)
        )) if posicion is not None else set()

    contexto = await persistencia.contexto_de(db, partido)
    largo, ancho = contexto.largo_m, contexto.ancho_m
    direccion = contexto.ataca_hacia or "DER"
    tramos = await persistencia.tramos_de(db, partido)
    por_track = tramos_por_track(tramos) if jugadores is not None else {}
    video_id = await db.scalar(del_club(Video, usuario).with_only_columns(Video.id).where(
        Video.partido_id == partido_id,
        Video.estado == EstadoVideo.PROCESADO.value,
    ).order_by(Video.procesado_en.desc().nulls_last(), Video.id.desc()).limit(1))
    muestras_video = await asyncio.to_thread(cargar_muestras_video, video_id) if video_id is not None else []
    if muestras_video:
        largo, ancho = muestras_video[0].calidad.largo_m, muestras_video[0].calidad.ancho_m

    paso_x, paso_y = largo / COLUMNAS, ancho / FILAS
    matriz = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]

    def acumular(muestra: Muestra) -> None:
        parte = 1 if muestra.t < 45 * 60 else 2
        puntos = {p.track_id: p for p in muestra.jugadores if p.equipo == contexto.lado_propio}
        for tid, punto in puntos.items():
            if jugadores is not None and jugador_en(por_track, tid, muestra.t) not in jugadores:
                continue
            if not (0 <= punto.x <= largo and 0 <= punto.y <= ancho):
                continue
            x, y = normalizar_coordenadas(punto.x, punto.y, largo, ancho, direccion, parte)
            columna, fila = min(COLUMNAS - 1, int(x / paso_x)), min(FILAS - 1, int(y / paso_y))
            matriz[fila][columna] += 1

    desde, hasta = desde_minuto * 60, (hasta_minuto + 1) * 60
    if video_id is not None:
        for muestra in muestras_video:
            if desde <= muestra.t < hasta and muestra.calidad.calibracion_valida is not False:
                acumular(muestra_de_mensaje(muestra))
    else:
        async for muestra in persistencia.muestras_de(
            db, partido_id, persistencia.equipos_de(tramos), t_desde=desde, t_hasta=hasta,
        ):
            acumular(muestra)

    maximo = max(map(max, matriz)) or 1
    return MapaCalor(
        partido_id=partido_id, alcance=alcance, referencia_id=referencia_id,
        largo_m=largo, ancho_m=ancho,
        celdas=[CeldaCalor(x=round((i + .5) * paso_x, 2), y=round((j + .5) * paso_y, 2),
                          valor=round(n / maximo, 4))
                for j, fila in enumerate(matriz) for i, n in enumerate(fila) if n],
    )
