"""Compensación de Movimiento Global de Cámara (GMC)  —  CU-24 / CU-26.

Permite estimar el movimiento de la cámara táctica (paneo horizontal, leve inclinación
y zoom) entre fotogramas consecutivos mediante flujo óptico ralo (Lucas-Kanade)
y estimación afín robusta (RANSAC).

Propósitos:
1. Seguimiento persistente (ByteTrack): compensa las posiciones predichas de los
   jugadores para que el filtro de Kalman no diverja cuando la cámara se desplaza.
2. Homografía dinámica: actualiza la matriz de proyección H_t = H_0 * T_cam^{-1}
   para mantener sincronizada la cancha 2D aunque la cámara rote o panee.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class TransformacionCamara:
    """Transformación afín estimada de la cámara entre el fotograma t-1 y t.

    x_t = M * x_{t-1}
    """

    dx: float
    dy: float
    rotacion_rad: float
    escala: float
    matriz_afine: np.ndarray  # Matriz 2x3
    matriz_3x3: np.ndarray    # Matriz homogénea 3x3
    inliers_pct: float        # Porcentaje de correspondencias válidas
    es_valida: bool           # True si la estimación es confiable


def _matriz_identidad_3x3() -> np.ndarray:
    return np.eye(3, dtype=np.float64)


def _matriz_identidad_2x3() -> np.ndarray:
    return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)


class CompensadorMovimientoCamara:
    """Estimador y acumulador de movimiento global de cámara (GMC).

    Utiliza características de esquinas (Shi-Tomasi) sobre el fondo (excluyendo
    a los jugadores para no confundir su carrera con el movimiento del plano)
    y calcula la transformación afín parcial (traslación, rotación, escala uniforme).
    """

    def __init__(
        self,
        max_puntos: int = 400,
        calidad_esquinas: float = 0.02,
        distancia_minima_puntos: float = 20.0,
        umbral_ransac: float = 3.0,
        min_inliers: int = 10,
    ) -> None:
        self.max_puntos = max_puntos
        self.calidad_esquinas = calidad_esquinas
        self.distancia_minima_puntos = distancia_minima_puntos
        self.umbral_ransac = umbral_ransac
        self.min_inliers = min_inliers

        self._cuadro_anterior_gris: np.ndarray | None = None
        self._puntos_anteriores: np.ndarray | None = None
        self._ultima_transformacion: TransformacionCamara | None = None
        # Matriz acumulada desde el fotograma inicial: x_t = T_acum * x_0
        self._t_acumulada_3x3: np.ndarray = _matriz_identidad_3x3()

    def reiniciar(self) -> None:
        """Reinicia el estado y la matriz acumulada a la identidad."""
        self._cuadro_anterior_gris = None
        self._puntos_anteriores = None
        self._ultima_transformacion = None
        self._t_acumulada_3x3 = _matriz_identidad_3x3()

    def reanclar(self) -> None:
        """Reinicia la matriz acumulada a la identidad manteniendo el cuadro previo."""
        self._t_acumulada_3x3 = _matriz_identidad_3x3()

    @property
    def ultima_transformacion(self) -> TransformacionCamara | None:
        """Última transformación de cámara estimada."""
        return self._ultima_transformacion

    @property
    def matriz_acumulada(self) -> np.ndarray:
        """Matriz homogénea 3x3 que mapea coordenadas del fotograma 0 al actual."""
        return self._t_acumulada_3x3.copy()

    def estimar(
        self,
        cuadro_bgr: np.ndarray,
        cajas_excluidas: Sequence[tuple[float, float, float, float]] = (),
    ) -> TransformacionCamara:
        """Estima la transformación entre el cuadro anterior y el cuadro actual.

        Args:
            cuadro_bgr: Fotograma actual en BGR.
            cajas_excluidas: Bounding boxes (x1, y1, x2, y2) de jugadores u objetos
                             móviles a ignorar para el cálculo de fondo.

        Returns:
            TransformacionCamara con el delta de movimiento y las matrices afines.
        """
        # 0. Verificación de plano táctico por cobertura de césped en transmisiones reales:
        # En primeros planos de TV, túnel o repeticiones gráficas, el césped cae (< 28%).
        # Al no ser el plano general del estadio, reiniciamos la acumulación para evitar deriva.
        alto, ancho = cuadro_bgr.shape[:2]
        if alto >= 400 and ancho >= 600:
            hsv_sub = cv2.cvtColor(cuadro_bgr[::4, ::4], cv2.COLOR_BGR2HSV)
            mascara_cesped = (
                (hsv_sub[:, :, 0] >= 30) & (hsv_sub[:, :, 0] <= 85) &
                (hsv_sub[:, :, 1] >= 30) & (hsv_sub[:, :, 2] >= 30)
            )
            if (np.count_nonzero(mascara_cesped) / mascara_cesped.size) < 0.28:
                self._cuadro_anterior_gris = None
                self._puntos_anteriores = None
                self._t_acumulada_3x3 = _matriz_identidad_3x3()
                return self._transformacion_identidad()

        gris = cv2.cvtColor(cuadro_bgr, cv2.COLOR_BGR2GRAY)
        alto, ancho = gris.shape[:2]

        # Si es el primer fotograma, inicializamos puntos y retornamos identidad
        if self._cuadro_anterior_gris is None:
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            return self._transformacion_identidad()

        # Si nos quedamos con muy pocos puntos del cuadro anterior, extraemos de nuevo
        if self._puntos_anteriores is None or len(self._puntos_anteriores) < self.min_inliers:
            self._extraer_nuevos_puntos(self._cuadro_anterior_gris, cajas_excluidas)

        if self._puntos_anteriores is None or len(self._puntos_anteriores) < self.min_inliers:
            # Imposible extraer puntos suficientes
            self._cuadro_anterior_gris = gris
            return self._transformacion_identidad()

        # Flujo óptico piramidal Lucas-Kanade
        puntos_actuales, estado, _ = cv2.calcOpticalFlowPyrLK(
            self._cuadro_anterior_gris,
            gris,
            self._puntos_anteriores,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )

        if puntos_actuales is None or estado is None:
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            return self._transformacion_identidad()

        validos = (estado.flatten() == 1)
        p_ant = self._puntos_anteriores[validos]
        p_act = puntos_actuales[validos]

        if len(p_ant) < self.min_inliers:
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            return self._transformacion_identidad()

        # Estimación afín parcial con RANSAC
        m_2x3, inliers = cv2.estimateAffinePartial2D(
            p_ant,
            p_act,
            method=cv2.RANSAC,
            ransacReprojThreshold=self.umbral_ransac,
        )

        if m_2x3 is None or inliers is None:
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            return self._transformacion_identidad()

        num_inliers = int(np.sum(inliers))
        pct_inliers = num_inliers / max(1, len(p_ant))

        if num_inliers < self.min_inliers:
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            return self._transformacion_identidad()

        # Descomponer matriz 2x3 afín parcial:
        # [[a, -b, tx],
        #  [b,  a, ty]]
        a = float(m_2x3[0, 0])
        b = float(m_2x3[1, 0])
        tx = float(m_2x3[0, 2])
        ty = float(m_2x3[1, 2])

        escala = float(np.sqrt(a * a + b * b))
        rotacion = float(np.arctan2(b, a))

        # Restricciones físicas de cámara táctica de estadio (montada en trípode elevado):
        # 1. Paneo horizontal suave: máx 40 px por fotograma muestreado (200 ms)
        # 2. Inclinación vertical (tilt) casi nula: máx 15 px por fotograma
        # 3. Zoom estable (0.95 a 1.05) y rotación/roll casi cero (< 0.08 rad)
        # 4. Inliers suficientes (al menos 20% de puntos estables)
        es_valida = (
            abs(tx) < 40.0 and
            abs(ty) < 15.0 and
            0.95 <= escala <= 1.05 and
            abs(rotacion) < 0.08 and
            pct_inliers >= 0.20
        )

        if not es_valida:
            # Corte de plano, repetición de TV o cambio de escena: reanclar al encuadre de referencia
            self._cuadro_anterior_gris = gris
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
            self._t_acumulada_3x3 = _matriz_identidad_3x3()
            return self._transformacion_identidad()

        m_3x3 = np.eye(3, dtype=np.float64)
        m_3x3[:2, :] = m_2x3

        # En cámaras tácticas montadas en tribuna (trípode nivelado):
        # El movimiento físico real es exclusivamente paneo horizontal (dx) y micro-tilt vertical (dy).
        # Para evitar la acumulación de distorsiones angulares espurias en videos largos (1000+ cuadros),
        # acumulamos el desplazamiento translacional neto y mantenemos la ortogonalidad perfecta.
        # Acumulación de traslación con límite proporcional a la resolución del plano
        max_dx = float(ancho * 1.2)
        max_dy = float(alto * 0.35)
        dx_acum = float(np.clip(self._t_acumulada_3x3[0, 2] + tx, -max_dx, max_dx))
        dy_acum = float(np.clip(self._t_acumulada_3x3[1, 2] + ty, -max_dy, max_dy))

        nueva_acum = np.eye(3, dtype=np.float64)
        nueva_acum[0, 2] = dx_acum
        nueva_acum[1, 2] = dy_acum
        self._t_acumulada_3x3 = nueva_acum

        # Guardar estado para el siguiente cuadro
        self._cuadro_anterior_gris = gris
        # Mantenemos los inliers válidos y refrescamos si caen por debajo de la mitad
        if num_inliers < self.max_puntos // 2:
            self._extraer_nuevos_puntos(gris, cajas_excluidas)
        else:
            inliers_mask = (inliers.flatten() == 1)
            self._puntos_anteriores = p_act[inliers_mask].reshape(-1, 1, 2)

        res = TransformacionCamara(
            dx=tx,
            dy=ty,
            rotacion_rad=rotacion,
            escala=escala,
            matriz_afine=m_2x3,
            matriz_3x3=m_3x3,
            inliers_pct=pct_inliers,
            es_valida=True,
        )
        self._ultima_transformacion = res
        return res

    def _extraer_nuevos_puntos(
        self,
        gris: np.ndarray,
        cajas_excluidas: Sequence[tuple[float, float, float, float]],
    ) -> None:
        """Extrae características en zonas de fondo (excluyendo cajas de jugadores)."""
        alto, ancho = gris.shape[:2]
        mascara = np.full((alto, ancho), 255, dtype=np.uint8)

        # Excluir márgenes extremos (marcadores de TV, barras de estado y vallas publicitarias LED)
        mascara[:int(alto * 0.12), :] = 0
        mascara[int(alto * 0.88):, :] = 0

        # Enmascarar jugadores
        for x1, y1, x2, y2 in cajas_excluidas:
            ix1 = max(0, int(x1) - 5)
            iy1 = max(0, int(y1) - 5)
            ix2 = min(ancho, int(x2) + 5)
            iy2 = min(alto, int(y2) + 5)
            mascara[iy1:iy2, ix1:ix2] = 0

        puntos = cv2.goodFeaturesToTrack(
            gris,
            maxCorners=self.max_puntos,
            qualityLevel=self.calidad_esquinas,
            minDistance=self.distancia_minima_puntos,
            mask=mascara,
        )
        self._puntos_anteriores = puntos

    def _transformacion_identidad(self) -> TransformacionCamara:
        res = TransformacionCamara(
            dx=0.0,
            dy=0.0,
            rotacion_rad=0.0,
            escala=1.0,
            matriz_afine=_matriz_identidad_2x3(),
            matriz_3x3=_matriz_identidad_3x3(),
            inliers_pct=1.0,
            es_valida=True,
        )
        self._ultima_transformacion = res
        return res

    def compensar_caja(
        self,
        caja: tuple[float, float, float, float],
        transformacion: TransformacionCamara,
    ) -> tuple[float, float, float, float]:
        """Aplica la transformación de cámara a una caja delimitadora (x1, y1, x2, y2)."""
        if not transformacion.es_valida:
            return caja
        x1, y1, x2, y2 = caja
        puntos = np.array([
            [x1, y1],
            [x2, y1],
            [x2, y2],
            [x1, y2],
        ], dtype=np.float32).reshape(-1, 1, 2)
        transformados = cv2.transform(puntos, transformacion.matriz_afine).reshape(-1, 2)
        nx1 = float(np.min(transformados[:, 0]))
        ny1 = float(np.min(transformados[:, 1]))
        nx2 = float(np.max(transformados[:, 0]))
        ny2 = float(np.max(transformados[:, 1]))
        return (nx1, ny1, nx2, ny2)

    def homografia_compensada(self, homografia_inicial_3x3: np.ndarray) -> np.ndarray:
        """Devuelve la matriz de homografía actualizada para el encuadre actual:

        H_t = H_0 * T_acumulada^{-1}

        Esto permite proyectar directamente las coordenadas en píxeles del cuadro
        actual a metros en el radar 2D sin importar cuánto haya paneado la cámara.
        """
        try:
            t_inv = np.linalg.inv(self._t_acumulada_3x3)
            return homografia_inicial_3x3 @ t_inv
        except np.linalg.LinAlgError:
            return homografia_inicial_3x3.copy()

