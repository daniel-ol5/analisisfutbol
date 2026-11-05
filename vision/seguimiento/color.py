"""Clasificacion de equipo por color de camiseta  —  CU-25.

Tres pasos puros, sin torch ni modelo: reciben el cuadro (BGR, como lo da
OpenCV) y la caja de un jugador ya trackeado (CU-24).

1. `recortar_torso`: del torso, no de la caja completa. La cabeza (piel/pelo)
   y la pantaloneta (a veces de otro color) contaminan el promedio, y los
   bordes de la caja casi siempre tienen cesped de fondo.
2. `descartar_cesped`: mascara HSV para excluir lo que sobrevive del verde de
   la cancha dentro del recorte.
3. `color_dominante`: un vector robusto a la intensidad de la luz (se
   descarta el canal V) y al quiebre circular del tono (h=0 y h=179 son el
   mismo color, por eso se proyecta a (cos, sin) en vez de usarlo crudo).

`agrupar_equipos` junta esos vectores de varios jugadores con K-means (k=2).

`clasificar_equipos` va un paso mas alla (HU-21, criterios 2 y 3): no se
queda en un agrupamiento ciego con etiquetas 0/1 sin significado, sino que
compara contra los colores de indumentaria ya registrados en CU-10
(`Equipo.color_local` / `color_visitante`, hex #RRGGBB) para asignar
`EquipoDetectado.LOCAL`/`VISITANTE`/`ARBITRO` con un indice de confianza.
Esos colores le llegan como parametro de configuracion al iniciar el worker
(igual que `fuente` en `seguimiento.tracker.seguir`): el worker corre fuera
de este backend y nunca consulta la base de datos directamente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from seguimiento.tipos import EquipoDetectado

# Rango de verde de cancha en HSV de OpenCV (H: 0-179, S y V: 0-255).
# Ancho a proposito: cesped seco, sombra y reflejo de luz cambian el tono.
_VERDE_HSV_BAJO = np.array([35, 40, 40])
_VERDE_HSV_ALTO = np.array([85, 255, 255])

# Distancia (en el espacio [cos(h), sin(h), s]) a partir de la cual un color
# ya no se considera "del mismo equipo": por encima de esto en ambos
# registrados (local y visitante) se interpreta como arbitro.
_UMBRAL_ARBITRO_DEFECTO = 0.6


class RecorteVacio(ValueError):
    """El recorte no tiene pixeles (caja degenerada o fuera del cuadro)."""


def recortar_torso(
    cuadro: np.ndarray,
    caja: tuple[float, float, float, float],
    margen_horizontal: float = 0.2,
    inicio_vertical: float = 0.15,
    fin_vertical: float = 0.55,
) -> np.ndarray:
    """Recorte del torso dentro de la caja del jugador, en pixeles del cuadro.

    Por defecto toma del 15% al 55% del alto de la caja (el pecho, debajo de
    la cabeza y arriba de la pantaloneta) y descarta un 20% del ancho en cada
    borde (ahi es donde mas se cuela el cesped de fondo).
    """
    alto_img, ancho_img = cuadro.shape[:2]
    x1, y1, x2, y2 = caja
    alto, ancho = y2 - y1, x2 - x1

    rx1 = np.clip(x1 + margen_horizontal * ancho, 0, ancho_img)
    rx2 = np.clip(x2 - margen_horizontal * ancho, 0, ancho_img)
    ry1 = np.clip(y1 + inicio_vertical * alto, 0, alto_img)
    ry2 = np.clip(y1 + fin_vertical * alto, 0, alto_img)

    recorte = cuadro[int(ry1) : int(ry2), int(rx1) : int(rx2)]
    if recorte.size == 0:
        raise RecorteVacio(f"La caja {caja} no deja un recorte de torso valido")
    return recorte


def descartar_cesped(recorte_bgr: np.ndarray) -> np.ndarray:
    """Mascara booleana del mismo alto x ancho: `True` donde NO es cesped."""
    hsv = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2HSV)
    es_cesped = cv2.inRange(hsv, _VERDE_HSV_BAJO, _VERDE_HSV_ALTO) > 0
    return ~es_cesped


def color_dominante(recorte_bgr: np.ndarray) -> np.ndarray:
    """Vector `[cos(tono), sin(tono), saturacion]` del color dominante.

    Se descarta el canal V (brillo): dos camisetas del mismo color bajo luz
    distinta no deberian separarse. Si todo el recorte es cesped (caso raro,
    jugador casi oculto) se usa el recorte completo sin mascara en vez de
    fallar.
    """
    if recorte_bgr.size == 0:
        raise RecorteVacio("No se puede calcular el color de un recorte vacio")

    hsv = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float64)
    mascara = descartar_cesped(recorte_bgr).reshape(-1)
    pixeles = hsv[mascara] if mascara.any() else hsv

    angulo = pixeles[:, 0] * (2 * np.pi / 180.0)  # H de OpenCV: angulo real / 2
    saturacion = pixeles[:, 1] / 255.0
    return np.array([np.cos(angulo).mean(), np.sin(angulo).mean(), saturacion.mean()])


def agrupar_equipos(colores: Sequence[np.ndarray], k: int = 2) -> np.ndarray:
    """Etiqueta (0 o 1, sin orden definido) de cada color por K-means.

    `k=2`: el criterio de aceptacion de CU-25 es agrupar en dos equipos.
    """
    datos = np.asarray(colores, dtype=np.float32)
    criterios = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
    _, etiquetas, _ = cv2.kmeans(datos, k, None, criterios, 10, cv2.KMEANS_PP_CENTERS)
    return etiquetas.ravel()


# ---------------- Comparacion contra los colores registrados (CU-10) ----------------


@dataclass(frozen=True, slots=True)
class ColoresEquipo:
    """Colores de indumentaria del partido, en hex `#RRGGBB` (CU-10).

    Llegan como parametro de configuracion al iniciar el worker (CLI/env),
    nunca consultando la base de datos del backend. `color_arbitro` es
    opcional: hoy `Equipo` (backend) no registra un color de arbitro, asi
    que sin este dato se usa el criterio de "lejos de ambos equipos" en vez
    de un match directo.
    """

    color_local: str
    color_visitante: str
    color_arbitro: str | None = None


@dataclass(frozen=True, slots=True)
class ClasificacionJugador:
    """Salida de `clasificar_equipos` para un jugador: equipo + confianza en [0, 1]."""

    equipo: EquipoDetectado
    confianza: float


def _hex_a_vector(color_hex: str) -> np.ndarray:
    """Convierte un color `#RRGGBB` al mismo espacio `[cos(h), sin(h), s]` de `color_dominante`."""
    hex_limpio = color_hex.strip().lstrip("#")
    r, g, b = (int(hex_limpio[i : i + 2], 16) for i in (0, 2, 4))
    bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    h, s, _v = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
    angulo = float(h) * (2 * np.pi / 180.0)
    return np.array([np.cos(angulo), np.sin(angulo), s / 255.0])


def _confianza(distancia: float, escala: float) -> float:
    """Mapea una distancia a confianza en [0, 1]: 0 de distancia -> 1.0 de confianza."""
    return float(np.clip(1.0 - distancia / escala, 0.0, 1.0))


def clasificar_equipos(
    colores: Sequence[np.ndarray],
    colores_equipo: ColoresEquipo,
    k: int = 2,
    umbral_arbitro: float = _UMBRAL_ARBITRO_DEFECTO,
) -> list[ClasificacionJugador]:
    """Asigna `LOCAL`, `VISITANTE` o `ARBITRO` a cada color dominante (HU-21, criterios 2-3).

    No es un K-means ciego: primero aparta a quien no se parece a ninguno de
    los dos equipos registrados (candidato a arbitro); al resto se le aplica
    K-means (k=2, robusto al ruido por jugador) y cada cluster se asigna al
    equipo cuyo color registrado tenga el centroide mas cercano.
    """
    datos = np.asarray(colores, dtype=np.float64)
    if datos.size == 0:
        return []

    vec_local = _hex_a_vector(colores_equipo.color_local)
    vec_visitante = _hex_a_vector(colores_equipo.color_visitante)
    vec_arbitro = (
        _hex_a_vector(colores_equipo.color_arbitro) if colores_equipo.color_arbitro else None
    )

    dist_local = np.linalg.norm(datos - vec_local, axis=1)
    dist_visitante = np.linalg.norm(datos - vec_visitante, axis=1)
    dist_equipo_min = np.minimum(dist_local, dist_visitante)

    if vec_arbitro is not None:
        dist_arbitro = np.linalg.norm(datos - vec_arbitro, axis=1)
        es_arbitro = dist_arbitro < dist_equipo_min
    else:
        dist_arbitro = None
        es_arbitro = dist_equipo_min > umbral_arbitro

    indices_jugadores = np.flatnonzero(~es_arbitro)
    etiquetas_cluster = np.full(len(datos), -1, dtype=int)
    cluster_0_es_local = True
    if indices_jugadores.size >= k:
        etiquetas_cluster[indices_jugadores] = agrupar_equipos(datos[indices_jugadores], k=k)
        etiquetas_jug = etiquetas_cluster[indices_jugadores]
        mascara_0, mascara_1 = etiquetas_jug == 0, etiquetas_jug == 1
        # Si un cluster quedo vacio (puede pasar con pocos puntos), se usa la
        # referencia contraria como su centroide: asi la comparacion sigue
        # siendo valida en vez de propagar NaN.
        centroide_0 = datos[indices_jugadores][mascara_0].mean(axis=0) if mascara_0.any() else vec_visitante
        centroide_1 = datos[indices_jugadores][mascara_1].mean(axis=0) if mascara_1.any() else vec_local
        cluster_0_es_local = bool(
            np.linalg.norm(centroide_0 - vec_local) <= np.linalg.norm(centroide_1 - vec_local)
        )

    resultado: list[ClasificacionJugador] = []
    for i in range(len(datos)):
        if es_arbitro[i]:
            if vec_arbitro is not None:
                resultado.append(
                    ClasificacionJugador(EquipoDetectado.ARBITRO, _confianza(dist_arbitro[i], umbral_arbitro))
                )
            else:
                # Mas lejos de ambos equipos que el umbral: confianza crece con esa distancia extra.
                confianza = _confianza(2 * umbral_arbitro - dist_equipo_min[i], umbral_arbitro)
                resultado.append(ClasificacionJugador(EquipoDetectado.ARBITRO, confianza))
            continue

        if etiquetas_cluster[i] != -1:
            es_local = (etiquetas_cluster[i] == 0) == cluster_0_es_local
        else:
            es_local = dist_local[i] <= dist_visitante[i]

        equipo = EquipoDetectado.LOCAL if es_local else EquipoDetectado.VISITANTE
        distancia = dist_local[i] if es_local else dist_visitante[i]
        resultado.append(ClasificacionJugador(equipo, _confianza(distancia, umbral_arbitro)))

    return resultado
