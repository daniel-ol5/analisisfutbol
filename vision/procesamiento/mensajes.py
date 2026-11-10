"""De un cuadro con detecciones a un `MensajeWorker`  —  CU-27 (T-061).

Une las piezas del pipeline que ya existen, en el orden del README:

    detecciones (YOLO + ByteTrack) ──► color de equipo (CU-25) ──► homografía (CU-26)

y arma el mismo diccionario que el worker manda en vivo
(`backend/app/partido/schemas.py::MensajeWorker`). Que sea el mismo contrato es
lo que hace que un video procesado genere las mismas entidades que un partido
en vivo.

Sin torch ni ultralytics: se prueba con cuadros y detecciones sintéticos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from calibracion.homografia import proyectar_detecciones
from seguimiento.color import (
    ColoresEquipo,
    RecorteVacio,
    agrupar_equipos,
    clasificar_equipos,
    color_dominante,
    recortar_torso,
)
from seguimiento.tipos import Clase, Deteccion, EquipoDetectado

# Mismo umbral que el backend para marcar la calidad como degradada (CU-39).
MIN_JUGADORES_SANO = 16


@dataclass(frozen=True, slots=True)
class Contexto:
    """Lo que no cambia en todo el video (sale del `Trabajo` del backend)."""

    partido_id: int
    homografia: np.ndarray
    es_local: bool
    color_propio: str
    color_rival: str | None
    fps_muestreo: float


def _vector_de_hex(color_hex: str) -> np.ndarray:
    """Mismo espacio [cos(h), sin(h), s] que `color_dominante`, usando su API pública."""
    hex_limpio = color_hex.strip().lstrip("#")
    r, g, b = (int(hex_limpio[i : i + 2], 16) for i in (0, 2, 4))
    return color_dominante(np.array([[[b, g, r]]], dtype=np.uint8))


def _equipo_propio(ctx: Contexto) -> EquipoDetectado:
    return EquipoDetectado.LOCAL if ctx.es_local else EquipoDetectado.VISITANTE


def _equipo_rival(ctx: Contexto) -> EquipoDetectado:
    return EquipoDetectado.VISITANTE if ctx.es_local else EquipoDetectado.LOCAL


def _por_cercania_al_propio(colores: Sequence[np.ndarray], ctx: Contexto) -> list[EquipoDetectado]:
    """Sin el color del rival: dos grupos por K-means; el más parecido a la
    camiseta propia es el equipo propio. Sin árbitro: no hay con qué separarlo."""
    propio = _vector_de_hex(ctx.color_propio)
    datos = np.asarray(colores, dtype=np.float64)
    if len(datos) < 2:
        # Con un solo jugador no hay grupos: decide la distancia a la camiseta propia.
        cerca = len(datos) == 1 and np.linalg.norm(datos[0] - propio) < 0.6
        return [_equipo_propio(ctx) if cerca else _equipo_rival(ctx)] * len(datos)

    etiquetas = agrupar_equipos(datos, k=2)
    distancias = []
    for grupo in (0, 1):
        miembros = datos[etiquetas == grupo]
        distancias.append(np.linalg.norm(miembros.mean(axis=0) - propio) if len(miembros) else np.inf)
    grupo_propio = int(np.argmin(distancias))
    return [_equipo_propio(ctx) if e == grupo_propio else _equipo_rival(ctx) for e in etiquetas]


def equipos_de(cuadro: np.ndarray, personas: Sequence[Deteccion], ctx: Contexto) -> list[EquipoDetectado]:
    """Equipo de cada persona detectada, en el mismo orden (CU-25)."""
    equipos: list[EquipoDetectado | None] = [None] * len(personas)
    colores: list[np.ndarray] = []
    indices: list[int] = []
    for i, d in enumerate(personas):
        if d.clase == Clase.ARBITRO:  # el modelo propio (CU-29) ya lo distingue
            equipos[i] = EquipoDetectado.ARBITRO
            continue
        try:
            colores.append(color_dominante(recortar_torso(cuadro, d.caja)))
            indices.append(i)
        except RecorteVacio:
            equipos[i] = EquipoDetectado.DESCONOCIDO

    if colores:
        if ctx.color_rival:
            local, visitante = (
                (ctx.color_propio, ctx.color_rival) if ctx.es_local
                else (ctx.color_rival, ctx.color_propio)
            )
            clasificados = [
                c.equipo for c in clasificar_equipos(colores, ColoresEquipo(local, visitante))
            ]
        else:
            clasificados = _por_cercania_al_propio(colores, ctx)
        for i, equipo in zip(indices, clasificados, strict=True):
            equipos[i] = equipo
    return [e or EquipoDetectado.DESCONOCIDO for e in equipos]


def _punto(
    d: Deteccion,
    equipo: EquipoDetectado,
    xy: tuple[float, float],
    ancho_px: int | None = None,
    alto_px: int | None = None,
) -> dict[str, Any]:
    punto: dict[str, Any] = {
        "tid": d.tid,
        "equipo": equipo.value,
        "x": round(float(xy[0]), 2),
        "y": round(float(xy[1]), 2),
        "conf": round(min(max(float(d.conf), 0.0), 1.0), 3),
    }
    if ancho_px and alto_px and ancho_px > 0 and alto_px > 0:
        x1_pct = round(100.0 * max(0.0, float(d.caja[0])) / ancho_px, 2)
        y1_pct = round(100.0 * max(0.0, float(d.caja[1])) / alto_px, 2)
        x2_pct = round(100.0 * min(float(ancho_px), float(d.caja[2])) / ancho_px, 2)
        y2_pct = round(100.0 * min(float(alto_px), float(d.caja[3])) / alto_px, 2)
        punto["bbox"] = [x1_pct, y1_pct, x2_pct, y2_pct]
    return punto


def armar_mensaje(
    ctx: Contexto, t: float, cuadro: np.ndarray, detecciones: Sequence[Deteccion]
) -> dict[str, Any]:
    """Un `MensajeWorker` (como diccionario JSON) para el cuadro del segundo `t`."""
    alto, ancho = cuadro.shape[:2] if isinstance(cuadro, np.ndarray) and cuadro.ndim >= 2 else (None, None)
    personas = [d for d in detecciones if d.clase in (Clase.JUGADOR, Clase.ARBITRO)]
    balones = [d for d in detecciones if d.clase == Clase.BALON]

    equipos = equipos_de(cuadro, personas, ctx)
    jugadores = [
        _punto(d, equipo, xy, ancho, alto)
        for (d, xy), equipo in zip(proyectar_detecciones(personas, ctx.homografia), equipos, strict=True)
    ]

    balon = None
    if balones:
        # Solo hay una pelota: la detección más segura.
        mejor = max(balones, key=lambda d: d.conf)
        (_, xy), = proyectar_detecciones([mejor], ctx.homografia)
        balon = _punto(mejor, EquipoDetectado.DESCONOCIDO, xy, ancho, alto)

    degradado = len(personas) < MIN_JUGADORES_SANO
    return {
        "partido": ctx.partido_id,
        "t": round(t, 3),
        "jugadores": jugadores,
        "balon": balon,
        "calidad": {
            "worker_conectado": True,
            "fps": ctx.fps_muestreo,
            "jugadores_detectados": len(personas),
            "balon_visible": balon is not None,
            "retraso_s": 0.0,  # video grabado: no hay retraso respecto del vivo
            "degradado": degradado,
            "motivo": f"Solo {len(personas)} jugadores detectados" if degradado else None,
        },
    }
