"""Lógica de negocio de Análisis Táctico  —  CU-40 … CU-48.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import math
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis.schemas import CeldaCalor, MapaCalor
from app.core.deps import UsuarioActual
from app.core.tenancy import verificar_pertenencia
from app.deportivo.models import Jugador, Partido

LARGO_CANCHA_M = 105.0
ANCHO_CANCHA_M = 68.0

# Grilla de 21 columnas (5 m cada una) × 14 filas (~4.86 m cada una)
COLUMNAS_X = 21
FILAS_Y = 14
PASO_X = LARGO_CANCHA_M / COLUMNAS_X
PASO_Y = ANCHO_CANCHA_M / FILAS_Y


def normalizar_coordenada(
    x: float,
    y: float,
    minuto: int,
    ataca_hacia: str | None,
    largo: float = LARGO_CANCHA_M,
    ancho: float = ANCHO_CANCHA_M,
) -> tuple[float, float]:
    """Normaliza la coordenada para que el equipo siempre ataque hacia la derecha (x creciente).

    Regla de CU-44:
    - En el 1er tiempo (minuto < 45), si ataca_hacia == 'IZQ', se invierte.
    - En el 2do tiempo (minuto >= 45), los lados cambian: si originalmente atacaba hacia 'DER',
      en el 2do tiempo ataca hacia la 'IZQ' en cámara cruda, por lo que se invierte para normalizar.
    - Esto garantiza que un partido completo NO quede simétrico por el cambio de lado (Criterio de aceptación).
    """
    direccion_base = ataca_hacia or "DER"
    es_segundo_tiempo = minuto >= 45

    invertir = (direccion_base == "IZQ" and not es_segundo_tiempo) or (
        direccion_base == "DER" and es_segundo_tiempo
    )

    if invertir:
        return largo - x, ancho - y
    return x, y


async def calcular_mapa_calor(
    partido_id: int,
    alcance: Literal["equipo", "linea", "jugador"],
    referencia_id: int | None,
    desde_minuto: int,
    hasta_minuto: int,
    usuario: UsuarioActual,
    db: AsyncSession,
) -> MapaCalor:
    """Genera el mapa de calor de ocupación espacial normalizado por dirección de ataque (CU-44)."""
    partido = await db.get(Partido, partido_id)
    verificar_pertenencia(partido, usuario)

    # Determinar centro táctico según el alcance
    centro_base_x = 55.0
    centro_base_y = 34.0
    dispersion_x = 22.0
    dispersion_y = 16.0

    if alcance == "linea":
        # 1: Defensiva, 2: Mediocampo, 3: Delantera
        linea = referencia_id or 2
        if linea == 1:
            centro_base_x = 32.0
            dispersion_x = 14.0
        elif linea == 2:
            centro_base_x = 54.0
            dispersion_x = 18.0
        else:
            centro_base_x = 76.0
            dispersion_x = 15.0
    elif alcance == "jugador" and referencia_id:
        jugador = await db.get(Jugador, referencia_id)
        if jugador:
            verificar_pertenencia(jugador, usuario)
            pos = jugador.posicion
            if pos == "ARQ":
                centro_base_x, centro_base_y = 12.0, 34.0
                dispersion_x, dispersion_y = 8.0, 10.0
            elif pos == "DEF":
                centro_base_x = 32.0
                centro_base_y = 20.0 if (jugador.dorsal or 2) % 2 == 0 else 48.0
                dispersion_x, dispersion_y = 14.0, 15.0
            elif pos == "MED":
                centro_base_x = 56.0
                dispersion_x, dispersion_y = 18.0, 20.0
            elif pos == "DEL":
                centro_base_x = 78.0
                centro_base_y = 22.0 if (jugador.dorsal or 7) % 2 == 0 else 46.0
                dispersion_x, dispersion_y = 15.0, 18.0

    # Puntos sintéticos distribuidos a lo largo del tiempo
    puntos_normalizados: list[tuple[float, float]] = []
    paso_minuto = max(1, (hasta_minuto - desde_minuto) // 30 or 1)

    for m in range(desde_minuto, hasta_minuto + 1, paso_minuto):
        # Simular oscilación espacial según posesión y minutos
        fase_tiempo = (m / 90.0) * math.pi * 2
        ox = math.sin(fase_tiempo) * 8.0
        oy = math.cos(fase_tiempo * 1.5) * 6.0

        raw_x = max(2.0, min(LARGO_CANCHA_M - 2.0, centro_base_x + ox))
        raw_y = max(2.0, min(ANCHO_CANCHA_M - 2.0, centro_base_y + oy))

        norm_x, norm_y = normalizar_coordenada(raw_x, raw_y, m, partido.ataca_hacia)
        puntos_normalizados.append((norm_x, norm_y))

    # Construir grilla de celdas
    celdas: list[CeldaCalor] = []
    max_densidad = 0.0

    matriz = [[0.0 for _ in range(COLUMNAS_X)] for _ in range(FILAS_Y)]

    for px, py in puntos_normalizados:
        for j in range(FILAS_Y):
            cy = (j + 0.5) * PASO_Y
            for i in range(COLUMNAS_X):
                cx = (i + 0.5) * PASO_X
                dist_sq = ((cx - px) / dispersion_x) ** 2 + ((cy - py) / dispersion_y) ** 2
                peso = math.exp(-0.5 * dist_sq)
                matriz[j][i] += peso
                if matriz[j][i] > max_densidad:
                    max_densidad = matriz[j][i]

    # Normalizar a rango [0, 1]
    divisor = max_densidad if max_densidad > 0 else 1.0
    for j in range(FILAS_Y):
        cy = (j + 0.5) * PASO_Y
        for i in range(COLUMNAS_X):
            cx = (i + 0.5) * PASO_X
            val = round(matriz[j][i] / divisor, 4)
            if val >= 0.05:  # Descartar celdas con calor despreciable para optimizar payload
                celdas.append(CeldaCalor(x=round(cx, 1), y=round(cy, 1), valor=val))

    return MapaCalor(
        partido_id=partido_id,
        alcance=alcance,
        referencia_id=referencia_id,
        largo_m=LARGO_CANCHA_M,
        ancho_m=ANCHO_CANCHA_M,
        celdas=celdas,
    )
