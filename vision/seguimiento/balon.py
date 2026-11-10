"""Seguimiento cinemático especializado del balón  —  CU-24 / CU-27.

El balón en cámaras tácticas 1080p es un objeto pequeño (6-16 píxeles) y rápido.
Este módulo implementa:
1. Fusión de detecciones YOLO (clase balón) con detector de candidatos morfológicos
   en el césped (brillo, circularidad, relación de aspecto).
2. Filtro cinemático de segundo orden (posición y velocidad) con amortiguamiento.
3. Compensación de movimiento de cámara (GMC) para no perder la trayectoria
   durante paneos rápidos.
4. Gestión de oclusiones temporales (inercia balística controlada) y estela visual.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cv2
import numpy as np

from seguimiento.tipos import Clase, Deteccion

if TYPE_CHECKING:
    from seguimiento.gmc import TransformacionCamara

# Verde de cancha para delimitar la zona de juego válida
_VERDE_HSV_MIN = np.array([30, 35, 35])
_VERDE_HSV_MAX = np.array([90, 255, 255])


@dataclass(frozen=True, slots=True)
class CandidatoBalon:
    x: float
    y: float
    radio: float
    confianza: float
    fuente: str  # "yolo" o "campo"


class RastreadorBalon:
    """Rastreador cinemático persistente para el balón de fútbol."""

    def __init__(
        self,
        max_cuadros_perdido: int = 10,
        distancia_max_asociacion_px: float = 120.0,
        tamano_estela: int = 8,
    ) -> None:
        self.max_cuadros_perdido = max_cuadros_perdido
        self.distancia_max_asociacion_px = distancia_max_asociacion_px
        self.tamano_estela = tamano_estela

        # Estado cinemático: [x, y, vx, vy]
        self._posicion: tuple[float, float] | None = None
        self._velocidad: tuple[float, float] = (0.0, 0.0)
        self._confianza: float = 0.0
        self._cuadros_sin_deteccion: int = 0
        self._estela: list[tuple[float, float]] = []

    def reiniciar(self) -> None:
        self._posicion = None
        self._velocidad = (0.0, 0.0)
        self._confianza = 0.0
        self._cuadros_sin_deteccion = 0
        self._estela.clear()

    @property
    def estela(self) -> list[tuple[float, float]]:
        """Historial de posiciones recientes (x, y) del balón para estela en el radar."""
        return list(self._estela)

    @property
    def posicion_actual(self) -> tuple[float, float] | None:
        return self._posicion

    def actualizar(
        self,
        cuadro_bgr: np.ndarray,
        detecciones_yolo: Sequence[Deteccion],
        cajas_jugadores: Sequence[tuple[float, float, float, float]] = (),
        transformacion_camara: TransformacionCamara | None = None,
    ) -> Deteccion | None:
        """Actualiza el estado del balón en el fotograma actual.

        Args:
            cuadro_bgr: Imagen del fotograma actual.
            detecciones_yolo: Detecciones entregadas por YOLO en este cuadro.
            cajas_jugadores: Cajas de personas detectadas (para evaluar proximidad).
            transformacion_camara: Compensación afín de la cámara (GMC).

        Returns:
            Deteccion con clase BALON y coordenadas estimadas, o None si está perdido.
        """
        # 1. Compensar movimiento de cámara sobre el estado previo
        if self._posicion is not None and transformacion_camara is not None and transformacion_camara.es_valida:
            x, y = self._posicion
            # Aplicar matriz afín: x' = a*x + c*y + tx, y' = b*x + d*y + ty
            m = transformacion_camara.matriz_afine
            nx = float(m[0, 0] * x + m[0, 1] * y + m[0, 2])
            ny = float(m[1, 0] * x + m[1, 1] * y + m[1, 2])
            self._posicion = (nx, ny)

        # 2. Predicción cinemática inercial
        pred_x, pred_y = self._posicion if self._posicion is not None else (None, None)
        if pred_x is not None and pred_y is not None:
            vx, vy = self._velocidad
            pred_x += vx
            pred_y += vy

        # 3. Recopilar candidatos (YOLO + Detector morfológico de campo)
        candidatos = self._extraer_candidatos_yolo(detecciones_yolo)

        # Si no hay detección clara de YOLO, buscamos candidatos visuales en el campo
        if not candidatos or max(c.confianza for c in candidatos) < 0.45:
            candidatos_campo = self._extraer_candidatos_campo(cuadro_bgr, pred_x, pred_y)
            candidatos.extend(candidatos_campo)

        # 4. Asociar mejor candidato
        mejor = self._seleccionar_mejor_candidato(candidatos, pred_x, pred_y)

        if mejor is not None:
            # Medición confirmada
            if self._posicion is not None:
                # Estimación de velocidad con filtro de suavizado
                dx = mejor.x - self._posicion[0]
                dy = mejor.y - self._posicion[1]
                self._velocidad = (0.6 * self._velocidad[0] + 0.4 * dx, 0.6 * self._velocidad[1] + 0.4 * dy)
            else:
                self._velocidad = (0.0, 0.0)

            self._posicion = (mejor.x, mejor.y)
            self._confianza = mejor.confianza
            self._cuadros_sin_deteccion = 0
            self._agregar_a_estela(self._posicion)

            r = max(4.0, mejor.radio)
            caja = (mejor.x - r, mejor.y - r, mejor.x + r, mejor.y + r)
            return Deteccion.desde_caja(0, Clase.BALON, caja, float(self._confianza))

        # 5. Si no hubo detección: avance inercial o pérdida
        if self._posicion is not None and self._cuadros_sin_deteccion < self.max_cuadros_perdido:
            self._cuadros_sin_deteccion += 1
            # Amortiguar velocidad por rozamiento
            vx, vy = self._velocidad
            self._velocidad = (vx * 0.9, vy * 0.9)
            self._posicion = (pred_x, pred_y)  # type: ignore[assignment]
            # Decaer confianza por cada cuadro sin ver el balón
            self._confianza = max(0.1, self._confianza * 0.8)
            self._agregar_a_estela(self._posicion)

            r = 6.0
            x, y = self._posicion
            caja = (x - r, y - r, x + r, y + r)
            return Deteccion.desde_caja(0, Clase.BALON, caja, float(self._confianza))

        # Balón definitivamente perdido
        self._posicion = None
        self._velocidad = (0.0, 0.0)
        self._confianza = 0.0
        return None

    def _agregar_a_estela(self, punto: tuple[float, float]) -> None:
        self._estela.append(punto)
        if len(self._estela) > self.tamano_estela:
            self._estela.pop(0)

    def _extraer_candidatos_yolo(self, detecciones: Sequence[Deteccion]) -> list[CandidatoBalon]:
        candidatos = []
        for d in detecciones:
            if d.clase == Clase.BALON:
                x1, y1, x2, y2 = d.caja
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                r = max((x2 - x1) / 2.0, (y2 - y1) / 2.0)
                candidatos.append(CandidatoBalon(cx, cy, r, float(d.conf), "yolo"))
        return candidatos

    def _extraer_candidatos_campo(
        self,
        cuadro_bgr: np.ndarray,
        pred_x: float | None,
        pred_y: float | None,
    ) -> list[CandidatoBalon]:
        """Detecta pequeños objetos brillantes y circulares en el área verde del césped."""
        alto, ancho = cuadro_bgr.shape[:2]

        # Si tenemos predicción cinemática previa, acotamos la búsqueda a una ROI
        if pred_x is not None and pred_y is not None:
            radio_busqueda = int(self.distancia_max_asociacion_px * 1.5)
            x_min = max(0, int(pred_x - radio_busqueda))
            x_max = min(ancho, int(pred_x + radio_busqueda))
            y_min = max(0, int(pred_y - radio_busqueda))
            y_max = min(alto, int(pred_y + radio_busqueda))
            roi = cuadro_bgr[y_min:y_max, x_min:x_max]
            offset_x, offset_y = x_min, y_min
        else:
            # Buscar en toda la mitad inferior del campo (zona de césped habitual)
            roi = cuadro_bgr[int(alto * 0.15) : int(alto * 0.95), :]
            offset_x, offset_y = 0, int(alto * 0.15)

        if roi.size == 0:
            return []

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # Máscara de césped
        cesped = cv2.inRange(hsv, _VERDE_HSV_MIN, _VERDE_HSV_MAX)

        # Dilatar máscara de césped ligeramente para atrapar el balón sobre la grama
        kernel = np.ones((5, 5), np.uint8)
        cesped_dilatado = cv2.dilate(cesped, kernel, iterations=2)

        # Canal V (brillo) alto y saturación baja/moderada (balón blanco o claro)
        v = hsv[:, :, 2]
        s = hsv[:, :, 1]
        candidatos_mask = (v > 175) & (s < 140) & (cesped_dilatado > 0)
        candidatos_mask = (candidatos_mask.astype(np.uint8)) * 255

        # Componentes conectados
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            candidatos_mask, connectivity=8
        )

        candidatos: list[CandidatoBalon] = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]

            # En 1080p el balón mide típicamente entre 5 y 22 píxeles de diámetro
            if not (12 <= area <= 400 and 4 <= w <= 25 and 4 <= h <= 25):
                continue

            relacion_aspecto = float(w) / float(h)
            if not (0.55 <= relacion_aspecto <= 1.8):
                continue  # Descartar líneas largas del campo

            cx = float(centroids[i][0]) + offset_x
            cy = float(centroids[i][1]) + offset_y
            radio = (w + h) / 4.0

            # Confianza basada en circularidad
            circularidad = 1.0 - abs(1.0 - relacion_aspecto)
            conf = float(np.clip(0.35 + 0.3 * circularidad, 0.0, 0.8))
            candidatos.append(CandidatoBalon(cx, cy, radio, conf, "campo"))

        return candidatos

    def _seleccionar_mejor_candidato(
        self,
        candidatos: Sequence[CandidatoBalon],
        pred_x: float | None,
        pred_y: float | None,
    ) -> CandidatoBalon | None:
        if not candidatos:
            return None

        if pred_x is None or pred_y is None:
            # Sin predicción previa: tomar el de mayor confianza (preferencia YOLO)
            yolo_cands = [c for c in candidatos if c.fuente == "yolo"]
            if yolo_cands:
                return max(yolo_cands, key=lambda c: c.confianza)
            return max(candidatos, key=lambda c: c.confianza)

        # Con predicción: buscar candidato más cercano dentro del radio máximo
        candidatos_validos: list[tuple[float, CandidatoBalon]] = []
        for c in candidatos:
            dist = math.hypot(c.x - pred_x, c.y - pred_y)
            if dist <= self.distancia_max_asociacion_px:
                # Puntuación combinada: cercanía a la predicción + confianza
                # Peso extra para detecciones del modelo YOLO
                bonus_yolo = 0.3 if c.fuente == "yolo" else 0.0
                score = (1.0 - dist / self.distancia_max_asociacion_px) * 0.7 + (c.confianza + bonus_yolo) * 0.3
                candidatos_validos.append((score, c))

        if not candidatos_validos:
            return None

        candidatos_validos.sort(key=lambda item: item[0], reverse=True)
        return candidatos_validos[0][1]

