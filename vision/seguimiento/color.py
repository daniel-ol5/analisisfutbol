"""Clasificación de equipo por color de indumentaria  —  CU-25.

Convierte recortes de torso a espacio perceptual CIELAB (L*, a*, b*), permitiendo
separar eficazmente camisetas blancas (L* alto, croma bajo), árbitros/indumentaria
negra (L* bajo) y equipaciones de colores (a*, b*).

Tres pasos:
1. `recortar_torso`: del torso (pecho), no de la caja completa.
2. `descartar_cesped`: máscara para excluir verde del campo de juego.
3. `color_dominante`: vector normalizado en CIELAB [L, a, b] robusto a variaciones de luz.

`clasificar_equipos` compara contra los colores registrados (CU-10) y permite
asignar LOCAL, VISITANTE, ARBITRO o DESCONOCIDO.
`ClasificadorTemporalEquipos` agrega persistencia temporal por Track ID.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from seguimiento.tipos import EquipoDetectado

# Rango de verde de cancha en HSV de OpenCV (H: 0-179, S y V: 0-255).
_VERDE_HSV_BAJO = np.array([35, 40, 40])
_VERDE_HSV_ALTO = np.array([85, 255, 255])

# Umbral en espacio CIELAB normalizado [L/255, (a-128)/128, (b-128)/128]
# para discriminar árbitro (lejos de los colores de ambos equipos).
_UMBRAL_ARBITRO_DEFECTO = 0.50


class RecorteVacio(ValueError):
    """El recorte no tiene píxeles (caja degenerada o fuera del cuadro)."""


def recortar_torso(
    cuadro: np.ndarray,
    caja: tuple[float, float, float, float],
    margen_horizontal: float = 0.2,
    inicio_vertical: float = 0.15,
    fin_vertical: float = 0.55,
) -> np.ndarray:
    """Recorte del torso dentro de la caja del jugador, en píxeles del cuadro.

    Por defecto toma del 15% al 55% del alto de la caja (el pecho, debajo de
    la cabeza y arriba de la pantaloneta) y descarta un 20% del ancho en cada
    borde (donde suele colarse el césped de fondo).
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


def es_color_cesped(color: np.ndarray) -> bool:
    """Verifica si un vector CIELAB normalizado [L, a, b] corresponde al césped del campo."""
    return bool(color[1] < -0.12 and color[2] > 0.16)


def descartar_cesped(recorte_bgr: np.ndarray) -> np.ndarray:
    """Máscara booleana del mismo alto x ancho: `True` donde NO es césped."""
    hsv = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2HSV)
    es_cesped = cv2.inRange(hsv, _VERDE_HSV_BAJO, _VERDE_HSV_ALTO) > 0
    return ~es_cesped


def color_dominante(recorte_bgr: np.ndarray) -> np.ndarray:
    """Vector `[L, a, b]` normalizado en espacio CIELAB del color dominante.

    L en [0, 1] mide luminosidad (blanco vs negro).
    a en [-1, 1] mide verde-rojo.
    b en [-1, 1] mide azul-amarillo.
    Si todo el recorte es césped se usa el recorte completo sin máscara.
    """
    if recorte_bgr.size == 0:
        raise RecorteVacio("No se puede calcular el color de un recorte vacio")

    lab = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)
    mascara = descartar_cesped(recorte_bgr).reshape(-1)
    pixeles = lab[mascara] if mascara.any() else lab

    l_norm = pixeles[:, 0] / 255.0
    a_norm = (pixeles[:, 1] - 128.0) / 128.0
    b_norm = (pixeles[:, 2] - 128.0) / 128.0
    return np.array([float(l_norm.mean()), float(a_norm.mean()), float(b_norm.mean())])


def agrupar_equipos(colores: Sequence[np.ndarray], k: int = 2) -> np.ndarray:
    """Etiqueta (0 o 1, sin orden definido) de cada color por K-means."""
    datos = np.asarray(colores, dtype=np.float32)
    criterios = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
    _, etiquetas, _ = cv2.kmeans(datos, k, None, criterios, 10, cv2.KMEANS_PP_CENTERS)
    return etiquetas.ravel()


# ---------------- Comparación contra los colores registrados (CU-10) ----------------


@dataclass(frozen=True, slots=True)
class ColoresEquipo:
    """Colores de indumentaria del partido, en hex `#RRGGBB` (CU-10)."""

    color_local: str
    color_visitante: str
    color_arbitro: str | None = None


@dataclass(frozen=True, slots=True)
class ClasificacionJugador:
    """Salida de `clasificar_equipos` para un jugador: equipo + confianza en [0, 1]."""

    equipo: EquipoDetectado
    confianza: float


def _hex_a_vector(color_hex: str) -> np.ndarray:
    """Convierte un color `#RRGGBB` al espacio CIELAB normalizado `[L, a, b]`."""
    hex_limpio = color_hex.strip().lstrip("#")
    r, g, b = (int(hex_limpio[i : i + 2], 16) for i in (0, 2, 4))
    bgr = np.array([[[b, g, r]]], dtype=np.uint8)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float64)
    return np.array([lab[0] / 255.0, (lab[1] - 128.0) / 128.0, (lab[2] - 128.0) / 128.0])


def _confianza(distancia: float, escala: float) -> float:
    """Mapea una distancia a confianza en [0, 1]: 0 de distancia -> 1.0 de confianza."""
    return float(np.clip(1.0 - distancia / escala, 0.0, 1.0))


def _distancia_color_robusta(datos: np.ndarray, proto: np.ndarray) -> np.ndarray:
    """Calcula la distancia perceptual invariante a desaturación por distancia y luz.

    Para colores neutros (blanco/gris/negro): penaliza si la muestra tiene color (croma).
    Para colores cromáticos (rojo, celeste, verde): prioriza la coincidencia angular de tono
    en el plano (a*, b*) independientemente de si la cámara desaturó la camiseta.
    """
    chroma_c = np.sqrt(datos[:, 1] ** 2 + datos[:, 2] ** 2)
    chroma_p = float(np.sqrt(proto[1] ** 2 + proto[2] ** 2))

    if chroma_p < 0.08:
        # Prototipo neutro (blanco o negro)
        dL = np.abs(datos[:, 0] - proto[0])
        return dL * 0.45 + chroma_c * 1.6
    else:
        # Prototipo cromático (color definido)
        dL = np.abs(datos[:, 0] - proto[0]) * 0.25
        denom = np.maximum(1e-4, chroma_c * chroma_p)
        dot = (datos[:, 1] * proto[1] + datos[:, 2] * proto[2]) / denom
        cos_dist = 1.0 - np.clip(dot, -1.0, 1.0)
        deficit = np.maximum(0.0, 0.08 - chroma_c) * 1.8
        return dL + cos_dist * 0.55 + deficit


def clasificar_equipos(
    colores: Sequence[np.ndarray],
    colores_equipo: ColoresEquipo,
    k: int = 2,
    umbral_arbitro: float = _UMBRAL_ARBITRO_DEFECTO,
) -> list[ClasificacionJugador]:
    """Asigna `LOCAL`, `VISITANTE`, `ARBITRO` o `DESCONOCIDO` a cada color dominante.

    1. Compara contra árbitro (si está configurado o si la distancia mínima a ambos
       equipos supera `umbral_arbitro`).
    2. Aplica K-means al resto de jugadores y asocia cada clúster al equipo más cercano.
    """
    datos = np.asarray(colores, dtype=np.float64)
    if datos.size == 0:
        return []

    vec_local = _hex_a_vector(colores_equipo.color_local)
    vec_visitante = _hex_a_vector(colores_equipo.color_visitante)
    vec_arbitro = (
        _hex_a_vector(colores_equipo.color_arbitro) if colores_equipo.color_arbitro else None
    )

    cL = float(np.sqrt(vec_local[1] ** 2 + vec_local[2] ** 2))
    cV = float(np.sqrt(vec_visitante[1] ** 2 + vec_visitante[2] ** 2))

    dist_local = _distancia_color_robusta(datos, vec_local)
    dist_visitante = _distancia_color_robusta(datos, vec_visitante)
    dist_equipo_min = np.minimum(dist_local, dist_visitante)

    if vec_arbitro is not None:
        dist_arbitro = _distancia_color_robusta(datos, vec_arbitro)
        # Solo se etiqueta como árbitro si es significativamente más cercano que a los equipos
        # y la distancia perceptual absoluta es menor al umbral (evita falsos árbitros en jugadores de campo)
        es_arbitro = (dist_arbitro < dist_equipo_min) & (dist_arbitro < 0.38)
    else:
        # Árbitro por defecto: indumentaria oscura / negra estándar (L < 0.28)
        dist_arbitro = None
        es_arbitro = (datos[:, 0] < 0.28) & (dist_equipo_min > 0.30)

    resultado: list[ClasificacionJugador] = []
    for i in range(len(datos)):
        if es_arbitro[i]:
            conf = _confianza(dist_arbitro[i] if dist_arbitro is not None else 0.15, umbral_arbitro)
            resultado.append(ClasificacionJugador(EquipoDetectado.ARBITRO, conf))
            continue

        if dist_equipo_min[i] > 0.65:
            resultado.append(ClasificacionJugador(EquipoDetectado.DESCONOCIDO, 0.20))
            continue

        ab = datos[i, 1:3]
        if cL >= 0.08 and cV < 0.08:
            dir_L = vec_local[1:3] / cL
            proj = float(np.dot(ab, dir_L))
            es_local = proj > 0.005
            conf = float(np.clip(0.55 + abs(proj) * 5.0, 0.50, 0.95))
        elif cV >= 0.08 and cL < 0.08:
            dir_V = vec_visitante[1:3] / cV
            proj = float(np.dot(ab, dir_V))
            es_local = proj <= 0.005
            conf = float(np.clip(0.55 + abs(proj) * 5.0, 0.50, 0.95))
        elif cL >= 0.08 and cV >= 0.08:
            dir_L = vec_local[1:3] / cL
            dir_V = vec_visitante[1:3] / cV
            sim_L = float(np.dot(ab, dir_L))
            sim_V = float(np.dot(ab, dir_V))
            es_local = sim_L >= sim_V
            conf = float(np.clip(0.55 + abs(sim_L - sim_V) * 3.0, 0.50, 0.95))
        else:
            es_local = dist_local[i] <= dist_visitante[i]
            distancia = dist_local[i] if es_local else dist_visitante[i]
            conf = _confianza(distancia, umbral_arbitro)

        equipo = EquipoDetectado.LOCAL if es_local else EquipoDetectado.VISITANTE
        resultado.append(ClasificacionJugador(equipo, conf))

    return resultado


class ClasificadorTemporalEquipos:
    """Mantiene estabilidad temporal de la asignación de equipo por Track ID (tid).

    Evita que un jugador cambie de equipo o pase a desconocido por un solo
    fotograma con sombra, reflejo o cruce parcial.
    """

    def __init__(self, ventana: int = 15, olvido_cuadros: int = 90) -> None:
        self.ventana = ventana
        self.olvido_cuadros = olvido_cuadros
        self._historial: dict[int, list[EquipoDetectado]] = {}
        self._ultimo_visto: dict[int, int] = {}
        self._cuadro_actual: int = 0

    def registrar_y_suavizar(
        self, tid: int, equipo: EquipoDetectado, confianza: float
    ) -> tuple[EquipoDetectado, float]:
        self._ultimo_visto[tid] = self._cuadro_actual
        if equipo != EquipoDetectado.DESCONOCIDO:
            hist = self._historial.setdefault(tid, [])
            hist.append(equipo)
            if len(hist) > self.ventana:
                hist.pop(0)

        hist = self._historial.get(tid)
        if not hist:
            return equipo, confianza

        conteo: dict[EquipoDetectado, int] = {}
        for eq in hist:
            conteo[eq] = conteo.get(eq, 0) + 1
        mejor_equipo = max(conteo.items(), key=lambda item: item[1])[0]
        conf_suavizada = conteo[mejor_equipo] / len(hist)
        return mejor_equipo, float(conf_suavizada)

    def avanzar_cuadro(self) -> None:
        self._cuadro_actual += 1
        if self._cuadro_actual % 30 == 0:
            eliminar = [
                tid for tid, ult in self._ultimo_visto.items()
                if self._cuadro_actual - ult > self.olvido_cuadros
            ]
            for tid in eliminar:
                self._historial.pop(tid, None)
                self._ultimo_visto.pop(tid, None)


class CalibradorEquiposPartido:
    """Acumulador y calibrador empírico de indumentaria a nivel de partido (Fase F4).

    Resuelve el problema de variaciones de luz, sombras y desaturación broadcast:
    1. Acumula vectores CIELAB [L, a, b] de torsos de jugadores de campo durante los primeros fotogramas.
    2. Ejecuta K-means (k=2) con filtrado de atípicos sobre las muestras acumuladas para
       descubrir los centroides empíricos reales observados bajo la iluminación del partido.
    3. Asocia óptimamente los 2 centroides a `color_local` y `color_visitante` de forma robusta.
    4. Clasifica a los jugadores en cada fotograma contra los centroides empíricos con un
       margen de confianza superior y resistente a sombras.
    5. Aísla a los porteros (por clase YOLO o por posición) para no sesgar los clústeres
       de campo, y los asigna al equipo correspondiente según la mitad de cancha defendida.
    """

    def __init__(
        self,
        colores_equipo: ColoresEquipo,
        min_muestras_calibracion: int = 25,
        max_buffer_muestras: int = 400,
        intervalo_recalibracion: int = 150,
    ) -> None:
        self.colores_equipo = colores_equipo
        self.min_muestras_calibracion = min_muestras_calibracion
        self.max_buffer_muestras = max_buffer_muestras
        self.intervalo_recalibracion = intervalo_recalibracion

        self._muestras: list[np.ndarray] = []
        self._muestras_tid_count: dict[int, int] = {}
        self.centroide_local: np.ndarray | None = None
        self.centroide_visitante: np.ndarray | None = None
        self.calibrado: bool = False
        self._cuadro_actual: int = 0

        self._vec_local = _hex_a_vector(colores_equipo.color_local)
        self._vec_visitante = _hex_a_vector(colores_equipo.color_visitante)
        self._vec_arbitro = (
            _hex_a_vector(colores_equipo.color_arbitro)
            if colores_equipo.color_arbitro
            else None
        )
        self._algun_equipo_es_oscuro = min(self._vec_local[0], self._vec_visitante[0]) < 0.35

    @property
    def total_muestras(self) -> int:
        return len(self._muestras)

    def es_muestra_invalida_o_arbitro(self, color: np.ndarray) -> bool:
        """Determina si una muestra es césped espurio o indumentaria de árbitro."""
        if es_color_cesped(color):
            return True
        if not self._algun_equipo_es_oscuro and color[0] < 0.38:
            return True
        if self._vec_arbitro is not None:
            d_arb = float(_distancia_color_robusta(color[None, :], self._vec_arbitro)[0])
            d_loc = float(_distancia_color_robusta(color[None, :], self._vec_local)[0])
            d_vis = float(_distancia_color_robusta(color[None, :], self._vec_visitante)[0])
            if d_arb < min(d_loc, d_vis) and d_arb < 0.30:
                return True
        return False

    def acumular_muestra(
        self,
        color: np.ndarray,
        tid: int = -1,
        es_portero: bool = False,
        es_arbitro: bool = False,
    ) -> None:
        """Acumula una observación de torso de jugador de campo en el buffer."""
        if es_portero or es_arbitro or self.es_muestra_invalida_o_arbitro(color):
            return

        if tid > 0:
            count = self._muestras_tid_count.get(tid, 0)
            if count >= 15:
                return
            self._muestras_tid_count[tid] = count + 1

        self._muestras.append(color)
        if len(self._muestras) > self.max_buffer_muestras:
            self._muestras.pop(0)

        if not self.calibrado and len(self._muestras) >= self.min_muestras_calibracion:
            self.calibrar()

    def calibrar(self, forzar: bool = False) -> bool:
        """Ajusta los centroides empíricos para LOCAL y VISITANTE mediante K-means."""
        if len(self._muestras) < self.min_muestras_calibracion and not forzar:
            return False

        datos = np.asarray(self._muestras, dtype=np.float32)
        if len(datos) < 2:
            return False

        criterios = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-4)
        _, etiquetas, centros = cv2.kmeans(datos, 2, None, criterios, 15, cv2.KMEANS_PP_CENTERS)

        c0, c1 = centros[0], centros[1]

        # Refinamiento robusto: descartar atípicos de cada clúster
        for g, centro in enumerate([c0, c1]):
            pts = datos[etiquetas.ravel() == g]
            if len(pts) > 5:
                dists = np.linalg.norm(pts - centro, axis=1)
                med = float(np.median(dists))
                inliers = pts[dists <= max(2.0 * med, 0.12)]
                if len(inliers) > 3:
                    if g == 0:
                        c0 = inliers.mean(axis=0)
                    else:
                        c1 = inliers.mean(axis=0)

        costo_0_loc = float(_distancia_color_robusta(c0[None, :], self._vec_local)[0]) + float(
            _distancia_color_robusta(c1[None, :], self._vec_visitante)[0]
        )
        costo_1_loc = float(_distancia_color_robusta(c1[None, :], self._vec_local)[0]) + float(
            _distancia_color_robusta(c0[None, :], self._vec_visitante)[0]
        )

        if costo_0_loc <= costo_1_loc:
            c_loc, c_vis = c0, c1
        else:
            c_loc, c_vis = c1, c0

        if self.centroide_local is not None and self.centroide_visitante is not None:
            self.centroide_local = 0.85 * self.centroide_local + 0.15 * c_loc
            self.centroide_visitante = 0.85 * self.centroide_visitante + 0.15 * c_vis
        else:
            self.centroide_local = c_loc
            self.centroide_visitante = c_vis

        self.calibrado = True
        return True

    def clasificar_jugador(
        self,
        color: np.ndarray,
        posicion_m: tuple[float, float] | None = None,
        es_portero: bool = False,
        centroides_equipo_x: tuple[float, float] | None = None,
    ) -> ClasificacionJugador:
        """Clasifica un jugador individual con lógica empírica, posicional y de árbitro."""
        # 1. Portero asignado por mitad de cancha defendida
        if es_portero and posicion_m is not None:
            x_m = posicion_m[0]
            if centroides_equipo_x is not None:
                mean_loc_x, mean_vis_x = centroides_equipo_x
                loc_defiende_izq = mean_loc_x < mean_vis_x
                eq = (
                    EquipoDetectado.LOCAL
                    if (x_m < 52.5 if loc_defiende_izq else x_m >= 52.5)
                    else EquipoDetectado.VISITANTE
                )
            else:
                eq = EquipoDetectado.LOCAL if x_m < 52.5 else EquipoDetectado.VISITANTE
            return ClasificacionJugador(eq, 0.95)

        # 2. Árbitro por indumentaria oscura o cercanía a color árbitro registrado
        if not es_color_cesped(color):
            if not self._algun_equipo_es_oscuro and color[0] < 0.30:
                return ClasificacionJugador(EquipoDetectado.ARBITRO, 0.90)
            if self._vec_arbitro is not None:
                d_arb = float(_distancia_color_robusta(color[None, :], self._vec_arbitro)[0])
                d_loc = float(_distancia_color_robusta(color[None, :], self._vec_local)[0])
                d_vis = float(_distancia_color_robusta(color[None, :], self._vec_visitante)[0])
                if d_arb < min(d_loc, d_vis) and d_arb < 0.35:
                    return ClasificacionJugador(EquipoDetectado.ARBITRO, 0.90)

        # 3. Fallback estático si aún no ha completado el número mínimo de muestras
        if not self.calibrado or self.centroide_local is None or self.centroide_visitante is None:
            res = clasificar_equipos([color], self.colores_equipo)
            return res[0] if res else ClasificacionJugador(EquipoDetectado.DESCONOCIDO, 0.0)

        # 4. Clasificación contra centroides empíricos
        dL = float(_distancia_color_robusta(color[None, :], self.centroide_local)[0])
        dV = float(_distancia_color_robusta(color[None, :], self.centroide_visitante)[0])

        if min(dL, dV) > 0.70 and not self.es_muestra_invalida_o_arbitro(color):
            return ClasificacionJugador(EquipoDetectado.DESCONOCIDO, 0.20)

        margin = abs(dV - dL) / (dL + dV + 1e-5)
        conf = float(np.clip(0.60 + margin * 0.38, 0.50, 0.98))

        if dL <= dV:
            return ClasificacionJugador(EquipoDetectado.LOCAL, conf)
        else:
            return ClasificacionJugador(EquipoDetectado.VISITANTE, conf)

    def clasificar_lote(
        self,
        colores: Sequence[np.ndarray],
        posiciones_m: Sequence[tuple[float, float] | None] | None = None,
        son_porteros: Sequence[bool] | None = None,
        centroides_equipo_x: tuple[float, float] | None = None,
    ) -> list[ClasificacionJugador]:
        """Clasifica un lote completo de observaciones de un fotograma."""
        pos = posiciones_m or [None] * len(colores)
        porters = son_porteros or [False] * len(colores)
        return [
            self.clasificar_jugador(c, p, port, centroides_equipo_x)
            for c, p, port in zip(colores, pos, porters, strict=True)
        ]

    def avanzar_cuadro(self) -> None:
        """Avanza el reloj interno del calibrador y programa recalibraciones suaves."""
        self._cuadro_actual += 1
        if (
            self._cuadro_actual % self.intervalo_recalibracion == 0
            and len(self._muestras) >= self.min_muestras_calibracion
        ):
            self.calibrar()
