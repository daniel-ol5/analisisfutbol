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

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from seguimiento.gmc import CompensadorMovimientoCamara

from calibracion.homografia import cargar_homografia
from calibracion.referencias import BancoReferencias
from calibracion.terreno import refinar_con_lineas

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

    puntos = {
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
    # El modelo numera desde la banda lejana; la aplicación usa Y=0 en la cercana.
    return {i: (x, ancho - y) for i, (x, y) in puntos.items()}


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
    error_lineas_px: float | None = None


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
        self.error_lineas_px: float | None = None

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

            from calibracion.instalar_modelo import SHA256

            if self.ruta_pesos == _PESOS_KEYPOINTS_DEFECTO:
                with self.ruta_pesos.open("rb") as archivo:
                    if hashlib.file_digest(archivo, "sha256").hexdigest() != SHA256:
                        raise ValueError("El checkpoint de cancha no coincide con el modelo evaluado")
            self._modelo = YOLO(str(self.ruta_pesos))
            if self._modelo.task != "pose" or list(self._modelo.names.values()) != ["pitch"]:
                self._modelo = None
                raise ValueError("Se requiere el modelo de cancha Roboflow de 32 marcas, no pose humana")
            return True
        except Exception:
            log.exception("Error al inicializar YOLO para puntos de cancha")
            return False

    def estimar(
        self,
        cuadro: np.ndarray,
        conf_minima: float = 0.50,
        min_puntos: int = 6,
        umbral_ransac_m: float = 1.0,
        max_error_admisible_m: float = 3.0,
    ) -> ResultadoEstimacion:
        """Calcula la homografía absoluta (píxeles -> metros) si detecta la cancha."""
        if not isinstance(cuadro, np.ndarray) or cuadro.size == 0:
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        if not self._cargar_modelo_si_hace_falta():
            return ResultadoEstimacion(None, 0, 0, float("inf"), False)

        try:
            res = self._modelo(cuadro, verbose=False, device=self.dispositivo, imgsz=640)[0]
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
        if kpts.shape != (len(self.keypoints_metricos), 2) or confs.shape != (len(kpts),):
            raise ValueError(
                "Checkpoint de cancha incompatible: se requieren 32 marcas con el orden documentado"
            )

        src_pts: list[list[float]] = []
        dst_pts: list[tuple[float, float]] = []

        for i, ((u, v), conf) in enumerate(zip(kpts, confs, strict=False)):
            # Los extremos de una elipse en imagen no son referencias métricas fijas.
            if i in (30, 31):
                continue
            if (np.isfinite([u, v, conf]).all() and conf >= conf_minima
                    and (u > 0.0 or v > 0.0) and i in self.keypoints_metricos):
                src_pts.append([float(u), float(v)])
                dst_pts.append(self.keypoints_metricos[i])

        n_detectados = len(src_pts)
        if n_detectados < min_puntos:
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        src_arr = np.array(src_pts, dtype=np.float32)
        dst_arr = np.array(dst_pts, dtype=np.float32)
        valores = np.linalg.svd(dst_arr - dst_arr.mean(axis=0), compute_uv=False)
        if valores[1] < .05 * valores[0]:
            return ResultadoEstimacion(None, n_detectados, 0, float("inf"), False)

        try:
            # El error se mide en el plano de destino: aquí son METROS, no píxeles.
            H, mascara = cv2.findHomography(src_arr, dst_arr, cv2.RANSAC, umbral_ransac_m)
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

        valida = error_medio <= max_error_admisible_m and n_inliers / n_detectados >= .6
        error_lineas = None
        if valida:
            H, error_lineas, valida = refinar_con_lineas(cuadro, H, self.largo_m, self.ancho_m)
            self.error_lineas_px = error_lineas
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
            error_lineas_px=error_lineas,
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
    valida: bool = False
    estado: str = "SIN_REFERENCIA"
    ultimo_anclaje_t: float | None = None
    error_lineas_px: float | None = None
    max_sin_anclaje_s: float = 5.0
    _anterior_t: float | None = None
    _ultimo_intento_t: float = -100.0
    banco: BancoReferencias = field(default_factory=BancoReferencias)
    metodo: str | None = None

    def reiniciar(self, homografia_inicial: np.ndarray | None = None) -> None:
        self._homografia_anclada = homografia_inicial.copy() if homografia_inicial is not None else None
        self._homografia_actual = homografia_inicial.copy() if homografia_inicial is not None else None
        self._contador_cuadros = 0
        self.valida = homografia_inicial is not None
        self.estado = "VERIFICADA" if self.valida else "SIN_REFERENCIA"
        self.ultimo_anclaje_t = None
        self._anterior_t = None
        self.gmc.reiniciar()
        self.banco = BancoReferencias()

    def actualizar(
        self,
        cuadro: np.ndarray,
        homografia_referencia: np.ndarray | None = None,
        cajas_excluidas: Sequence[Sequence[float]] | None = None,
        forzar_recalibracion: bool = False,
        t_s: float | None = None,
        permitir_referencia: bool = True,
    ) -> np.ndarray:
        """Actualiza la homografía para el cuadro actual y la devuelve normalizada."""
        self._contador_cuadros += 1
        t = float(t_s if t_s is not None else (self._contador_cuadros - 1) / 5)
        dt = t - self._anterior_t if self._anterior_t is not None else None
        if dt is not None and (dt <= 0 or dt > 1):
            self.valida = False
            self.estado = "PERDIDA"
            self.gmc.reiniciar()
        self._anterior_t = t

        # 1. Base inicial si no había homografía previa
        if permitir_referencia and self._homografia_anclada is None and homografia_referencia is not None:
            self._homografia_anclada = homografia_referencia.copy()
            self._homografia_actual = homografia_referencia.copy()
            self.valida = True
            self.estado = "VERIFICADA"
            self.ultimo_anclaje_t = t
            self.gmc.reiniciar()
            self.banco.agregar(cuadro, homografia_referencia, cajas_excluidas or ())
            self.metodo = "MANUAL"

        # 2. Movimiento relativo de cámara por GMC
        movimiento = self.gmc.estimar(cuadro, cajas_excluidas=cajas_excluidas or (), dt_s=dt)
        if not movimiento.es_valida:
            self.valida = False
            self.estado = "PERDIDA"
        elif self.valida:
            self.estado = "SIGUIENDO"
        if self.ultimo_anclaje_t is not None and t - self.ultimo_anclaje_t > self.max_sin_anclaje_s:
            self.valida = False
            self.estado = "PERDIDA"
        H_pred = (
            self.gmc.homografia_compensada(self._homografia_anclada)
            if self._homografia_anclada is not None
            else None
        )

        # 3. Recalibración periódica o forzada con puntos clave del campo
        toca_recalibrar = forzar_recalibracion or (t - self._ultimo_intento_t >= 1.0 and (
            self.estimador_pitch is not None
            and (
                self._homografia_anclada is None or not self.valida
                or (self.recalibrar_cada_n_cuadros > 0 and self._contador_cuadros % self.recalibrar_cada_n_cuadros == 0)
            )
        ))

        if t - self._ultimo_intento_t >= 1.0 and self.banco.referencias:
            self._ultimo_intento_t = t
            recuperada = self.banco.recuperar(cuadro, cajas_excluidas or ())
            if recuperada is not None:
                self._homografia_anclada = cargar_homografia(recuperada[0])
                self._homografia_actual = self._homografia_anclada.copy()
                self.gmc.reanclar()
                self.valida = True
                self.estado = "VERIFICADA"
                self.metodo = "REFERENCIA_VISUAL"
                self.ultimo_anclaje_t = t
                self.error_lineas_px = None
                return self._homografia_actual.copy()

        if toca_recalibrar and self.estimador_pitch is not None:
            self._ultimo_intento_t = t
            res = self.estimador_pitch.estimar(cuadro)
            if res.es_valida and res.homografia is not None:
                H_kpt = res.homografia
                if H_pred is not None and self.valida:
                    alto, ancho = cuadro.shape[:2]
                    controles = np.float64([[ancho * x, alto * y] for x in (.25, .5, .75) for y in (.35, .55, .75)])
                    anterior = cv2.perspectiveTransform(controles.reshape(-1, 1, 2), H_pred)
                    nueva = cv2.perspectiveTransform(controles.reshape(-1, 1, 2), H_kpt)
                    if np.median(np.linalg.norm(anterior - nueva, axis=2)) > 2.0:
                        return H_pred.copy()
                if H_pred is not None and self.valida:
                    # Suavizar posiciones proyectadas; las matrices tienen escala arbitraria.
                    alto, ancho = cuadro.shape[:2]
                    rejilla = np.array([[0, 0], [ancho, 0], [ancho, alto], [0, alto]], dtype=np.float64)
                    a = cv2.perspectiveTransform(rejilla.reshape(-1, 1, 2), H_pred)
                    b = cv2.perspectiveTransform(rejilla.reshape(-1, 1, 2), H_kpt)
                    destino = (1 - self.alpha_suavizado) * a + self.alpha_suavizado * b
                    suave = None
                    if np.isfinite(destino).all():
                        suave, _ = cv2.findHomography(rejilla, destino.reshape(-1, 2))
                    self._homografia_anclada = cargar_homografia(suave if suave is not None else H_kpt)
                else:
                    self._homografia_anclada = H_kpt

                # Reanclar GMC para acumular traslación a partir de esta nueva referencia
                self.gmc.reanclar()
                self.valida = True
                self.estado = "VERIFICADA"
                self.ultimo_anclaje_t = t
                self.error_lineas_px = res.error_lineas_px
                self.metodo = "MARCAS_CANCHA"
                self._homografia_actual = self._homografia_anclada.copy()
                self.banco.agregar(cuadro, self._homografia_actual, cajas_excluidas or ())
                return self._homografia_actual.copy()

        if H_pred is not None:
            self._homografia_actual = H_pred.copy()
            return self._homografia_actual.copy()

        # 4. Fallback de seguridad
        if homografia_referencia is not None:
            return homografia_referencia.copy()
        return np.eye(3, dtype=np.float64)
