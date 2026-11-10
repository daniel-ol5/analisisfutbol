"""Estimación y seguimiento de homografía dinámica en partidos de fútbol.

Soporta cámaras móviles (paneo horizontal/vertical por operador humano)
combinando dos fuentes complementarias:
1. Puntos clave de la cancha (YOLOv8-pose de 32 marcas reglamentarias):
   Provee una referencia métrica absoluta (terreno de 105m x 68m) sin deriva.
2. Compensación de movimiento global de cámara (GMC - Flujo Óptico disperso):
   Provee continuidad suave cuadro a cuadro entre intervalos de detección.

Fórmula de proyección dinámica:
    p_cancha = H_t @ [u, v, 1]^T
donde H_t se actualiza y suaviza temporalmente con cada movimiento de la cámara.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from calibracion.homografia import HomografiaInvalida, cargar_homografia
from seguimiento.gmc import CompensadorMovimientoCamara, TransformacionCamara

log = logging.getLogger("calibracion.dinamica")

_PESOS_KEYPOINTS_DEFECTO = Path(__file__).resolve().parent.parent / "pesos" / "yolo_cancha_keypoints.pt"


def generar_keypoints_campo(
    largo: float = 105.0, ancho: float = 68.0
) -> dict[int, tuple[float, float]]:
    """Devuelve las coordenadas métricas (x, y) de los 32 puntos clave del modelo.

    Coordenadas en metros según el estándar FIFA reglamentario.
    Origen (0, 0) en el córner superior izquierdo.
    Eje X: línea de banda longitudinal (0 a largo, típicamente 105m).
    Eje Y: línea de meta transversal (0 a ancho, típicamente 68m).
    """
    mid_x = largo / 2.0
    mid_y = ancho / 2.0
    r_circ = 9.15
    # Distancia vertical del semicírculo del área grande a la intersección con la frontal (16.5m)
    arc_dy = float(np.sqrt(max(0.0, 9.15**2 - 5.5**2)))

    return {
        0: (0.0, 0.0),                      # Córner superior izquierdo
        1: (0.0, mid_y - 20.16),            # Área grande superior en línea de fondo izq
        2: (0.0, mid_y - 9.16),             # Área chica superior en línea de fondo izq
        3: (0.0, mid_y + 9.16),             # Área chica inferior en línea de fondo izq
        4: (0.0, mid_y + 20.16),            # Área grande inferior en línea de fondo izq
        5: (0.0, ancho),                    # Córner inferior izquierdo
        6: (5.5, mid_y - 9.16),             # Esquina superior interna área chica izq
        7: (5.5, mid_y + 9.16),             # Esquina inferior interna área chica izq
        8: (11.0, mid_y),                   # Punto penal izquierdo
        9: (16.5, mid_y - 20.16),           # Esquina superior interna área grande izq
        10: (16.5, mid_y - arc_dy),         # Intersección superior semicírculo penal izq
        11: (16.5, mid_y + arc_dy),         # Intersección inferior semicírculo penal izq
        12: (16.5, mid_y + 20.16),          # Esquina inferior interna área grande izq
        13: (mid_x, 0.0),                   # Intersección línea media y banda superior
        14: (mid_x, mid_y - r_circ),        # Intersección superior círculo central y línea media
        15: (mid_x, mid_y + r_circ),        # Intersección inferior círculo central y línea media
        16: (mid_x, ancho),                 # Intersección línea media y banda inferior
        17: (largo - 16.5, mid_y - 20.16),  # Esquina superior interna área grande der
        18: (largo - 16.5, mid_y - arc_dy), # Intersección superior semicírculo penal der
        19: (largo - 16.5, mid_y + arc_dy), # Intersección inferior semicírculo penal der
        20: (largo - 16.5, mid_y + 20.16),  # Esquina inferior interna área grande der
        21: (largo - 11.0, mid_y),          # Punto penal derecho
        22: (largo - 5.5, mid_y - 9.16),    # Esquina superior interna área chica der
        23: (largo - 5.5, mid_y + 9.16),    # Esquina inferior interna área chica der
        24: (largo, 0.0),                   # Córner superior derecho
        25: (largo, mid_y - 20.16),         # Área grande superior en línea de fondo der
        26: (largo, mid_y - 9.16),          # Área chica superior en línea de fondo der
        27: (largo, mid_y + 9.16),          # Área chica inferior en línea de fondo der
        28: (largo, mid_y + 20.16),         # Área grande inferior en línea de fondo der
        29: (largo, ancho),                 # Córner inferior derecho
        30: (mid_x - r_circ, mid_y),        # Extremo izquierdo círculo central
        31: (mid_x + r_circ, mid_y),        # Extremo derecho círculo central
    }


@dataclass
class ResultadoEstimacion:
    """Resultado del cálculo de homografía a partir de puntos clave."""

    homografia: np.ndarray | None
    puntos_detectados: int
    puntos_inliers: int
    error_medio_m: float
    es_valida: bool
    puntos_imagen: list[tuple[float, float]] = field(default_factory=list)
    puntos_cancha: list[tuple[float, float]] = field(default_factory=list)


class EstimadorHomografiaPitch:
    """Detecta los 32 puntos clave reglamentarios de la cancha y calcula H."""

    def __init__(
        self,
        ruta_pesos: str | Path | None = None,
        dispositivo: str = "cpu",
        largo_m: float = 105.0,
        ancho_m: float = 68.0,
    ) -> None:
        self.ruta_pesos = Path(ruta_pesos) if ruta_pesos else _PESOS_KEYPOINTS_DEFECTO
        self.dispositivo = dispositivo
        self.largo_m = largo_m
        self.ancho_m = ancho_m
        self.keypoints_metricos = generar_keypoints_campo(largo_m, ancho_m)
        self._modelo = None

    @property
    def modelo_cargado(self) -> bool:
        return self._modelo is not None

    def _cargar_modelo_si_hace_falta(self) -> bool:
        if self._modelo is not None:
            return True
        if not self.ruta_pesos.exists():
            log.warning("No se encontraron los pesos de puntos de cancha en %s", self.ruta_pesos)
            return False
        try:
            from ultralytics import YOLO

            self._modelo = YOLO(str(self.ruta_pesos))
            return True
        except Exception:
            log.exception("Error al inicializar YOLO para puntos de cancha")
            return False

    def estimar(
        self,
        cuadro: np.ndarray,
        conf_minima: float = 0.40,
        min_puntos: int = 4,
        umbral_ransac_px: float = 8.0,
        max_error_admisible_m: float = 3.0,
    ) -> ResultadoEstimacion:
        """Calcula la homografía absoluta (píxeles -> metros) si detecta la cancha."""
        if not isinstance(cuadro, np.ndarray) or cuadro.size == 0:
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        if not self._cargar_modelo_si_hace_falta():
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        try:
            res = self._modelo(cuadro, verbose=False, device=self.dispositivo)[0]
        except Exception:
            log.exception("Error en inferencia de puntos de cancha")
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        if res.keypoints is None or len(res.keypoints) == 0:
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        kpts = res.keypoints.xy[0].cpu().numpy()
        confs = (
            res.keypoints.conf[0].cpu().numpy()
            if res.keypoints.conf is not None
            else np.ones(len(kpts), dtype=np.float32)
        )

        src_pts: list[list[float]] = []
        dst_pts: list[tuple[float, float]] = []

        for i, ((u, v), conf) in enumerate(zip(kpts, confs, strict=False)):
            if conf >= conf_minima and (u > 0.0 or v > 0.0) and i in self.keypoints_metricos:
                src_pts.append([float(u), float(v)])
                dst_pts.append(self.keypoints_metricos[i])

        n_detectados = len(src_pts)
        if n_detectados < min_puntos:
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        src_arr = np.array(src_pts, dtype=np.float32)
        dst_arr = np.array(dst_pts, dtype=np.float32)

        try:
            H, mascara = cv2.findHomography(src_arr, dst_arr, cv2.RANSAC, umbral_ransac_px)
        except cv2.error:
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        if H is None or H.shape != (3, 3) or not np.isfinite(H).all():
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        if abs(np.linalg.det(H)) < 1e-12:
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        inliers = mascara.ravel() == 1
        n_inliers = int(np.sum(inliers))
        if n_inliers < min_puntos:
            return ResultadoEstimacion(None, n_detectados, n_inliers, float("inf"), False)

        # Evaluar error de reproyección sobre inliers
        pts_inliers_px = src_arr[inliers].reshape(-1, 1, 2)
        pts_inliers_dst = dst_arr[inliers]
        proy_m = cv2.perspectiveTransform(pts_inliers_px, H).reshape(-1, 2)
        errores = np.linalg.norm(proy_m - pts_inliers_dst, axis=1)
        error_medio = float(np.mean(errores))

        # Normalizar matriz tal que H[2, 2] = 1.0 si es posible
        if abs(H[2, 2]) > 1e-9:
            H = H / H[2, 2]

        valida = error_medio <= max_error_admisible_m
        pts_img = [tuple(p) for p in src_arr[inliers].tolist()]
        pts_cnc = [tuple(p) for p in dst_arr[inliers].tolist()]
        return ResultadoEstimacion(
            homografia=H if valida else None,
            puntos_detectados=n_detectados,
            puntos_inliers=n_inliers,
            error_medio_m=error_medio,
            es_valida=valida,
            puntos_imagen=pts_img,
            puntos_cancha=pts_cnc,
        )


@dataclass
class RastreadorHomografiaDinamica:
    """Mantiene la homografía efectiva sincronizada con el paneo de cámara.

    Combina la alta velocidad del flujo óptico (GMC) con la precisión absoluta
    de los puntos clave de la cancha cuando están disponibles.
    """

    estimador_pitch: EstimadorHomografiaPitch | None = None
    gmc: CompensadorMovimientoCamara = field(default_factory=CompensadorMovimientoCamara)
    alpha_suavizado: float = 0.35
    recalibrar_cada_n_cuadros: int = 15
    _homografia_anclada: np.ndarray | None = None
    _homografia_actual: np.ndarray | None = None
    _contador_cuadros: int = 0

    def reiniciar(self, homografia_inicial: np.ndarray | None = None) -> None:
        self._homografia_anclada = homografia_inicial.copy() if homografia_inicial is not None else None
        self._homografia_actual = homografia_inicial.copy() if homografia_inicial is not None else None
        self._contador_cuadros = 0
        self.gmc.reiniciar()

    def actualizar(
        self,
        cuadro: np.ndarray,
        homografia_referencia: np.ndarray | None = None,
        cajas_excluidas: Sequence[Sequence[float]] | None = None,
        forzar_recalibracion: bool = False,
    ) -> np.ndarray:
        """Actualiza la homografía para el cuadro actual y la devuelve normalizada."""
        self._contador_cuadros += 1

        # 1. Base inicial si no había homografía previa
        if self._homografia_anclada is None and homografia_referencia is not None:
            self._homografia_anclada = homografia_referencia.copy()
            self._homografia_actual = homografia_referencia.copy()

        # 2. Movimiento relativo de cámara por GMC
        _ = self.gmc.estimar(cuadro, cajas_excluidas=cajas_excluidas or ())
        H_pred = (
            self.gmc.homografia_compensada(self._homografia_anclada)
            if self._homografia_anclada is not None
            else None
        )

        # 3. Recalibración periódica o forzada con puntos clave del campo
        toca_recalibrar = forzar_recalibracion or (
            self.estimador_pitch is not None
            and (
                self._homografia_anclada is None
                or (self.recalibrar_cada_n_cuadros > 0 and self._contador_cuadros % self.recalibrar_cada_n_cuadros == 0)
            )
        )

        if toca_recalibrar and self.estimador_pitch is not None:
            res = self.estimador_pitch.estimar(cuadro)
            if res.es_valida and res.homografia is not None:
                H_kpt = res.homografia
                if H_pred is not None:
                    # Suavizado exponencial para evitar sacudidas bruscas entre cuadros
                    H_suave = (1.0 - self.alpha_suavizado) * H_pred + self.alpha_suavizado * H_kpt
                    if abs(H_suave[2, 2]) > 1e-9:
                        H_suave = H_suave / H_suave[2, 2]
                    self._homografia_anclada = H_suave
                else:
                    self._homografia_anclada = H_kpt

                # Reanclar GMC para acumular traslación a partir de esta nueva referencia
                self.gmc.reanclar()
                self._homografia_actual = self._homografia_anclada.copy()
                return self._homografia_actual.copy()

        if H_pred is not None:
            self._homografia_actual = H_pred.copy()
            return self._homografia_actual.copy()

        # 4. Fallback de seguridad
        if homografia_referencia is not None:
            return homografia_referencia.copy()
        return np.eye(3, dtype=np.float64)
