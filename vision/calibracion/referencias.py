"""Recuperación contra imágenes ya calibradas, sin acumular movimiento cuadro a cuadro."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ReferenciaVisual:
    puntos: np.ndarray
    descriptores: np.ndarray
    homografia: np.ndarray


class BancoReferencias:
    def __init__(self):
        self.referencias: list[ReferenciaVisual] = []
        self._sift = cv2.SIFT_create(nfeatures=5000, contrastThreshold=.015)

    def caracteristicas(self, cuadro, cajas=()):
        escala = min(1., 1280 / cuadro.shape[1])
        imagen = cv2.resize(cuadro, None, fx=escala, fy=escala)
        # Cámara PTZ en un punto fijo: su rotación/zoom inducen una homografía
        # global también sobre el fondo. Repartir referencias por toda la imagen
        # evita extrapolar desde unos pocos puntos concentrados en mediocampo.
        mascara = np.full(imagen.shape[:2], 255, np.uint8)
        mascara[:int(imagen.shape[0] * .12)] = 0
        mascara[int(imagen.shape[0] * .88):] = 0
        for x1, y1, x2, y2 in cajas:
            cv2.rectangle(mascara, (max(0, int(x1 * escala) - 4), max(0, int(y1 * escala) - 4)),
                          (int(x2 * escala) + 4, int(y2 * escala) + 4), 0, -1)
        kp, des = self._sift.detectAndCompute(cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY), mascara)
        return np.array([p.pt for p in kp], np.float32).reshape(-1, 2) / escala, des

    def agregar(self, cuadro, homografia, cajas=()):
        if homografia is None:
            return
        puntos, des = self.caracteristicas(cuadro, cajas)
        if des is not None and len(puntos) >= 15:
            self.referencias.append(ReferenciaVisual(puntos, des, homografia.copy()))
            # Conservar siempre la primera referencia absoluta.
            if len(self.referencias) > 5:
                self.referencias.pop(1)

    def recuperar(self, cuadro, cajas=()):
        if not self.referencias:
            return None
        puntos, des = self.caracteristicas(cuadro, cajas)
        if des is None or len(puntos) < 15:
            return None
        matcher = cv2.BFMatcher()
        mejor = None
        for referencia in self.referencias:
            parejas = matcher.knnMatch(referencia.descriptores, des, k=2)
            buenas = [par[0] for par in parejas if len(par) == 2 and par[0].distance < .75 * par[1].distance]
            if len(buenas) < 12:
                continue
            src = np.float32([referencia.puntos[p.queryIdx] for p in buenas])
            dst = np.float32([puntos[p.trainIdx] for p in buenas])
            h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 2.5)
            if h is None or mask is None or not np.isfinite(h).all():
                continue
            validos = mask.ravel() == 1
            cantidad = int(validos.sum())
            if cantidad < 20 or cantidad / len(buenas) < .45:
                continue
            dst_validos = dst[validos]
            contorno = cv2.convexHull(dst_validos)
            if contorno is None or len(contorno) < 3:
                continue
            cobertura = cv2.contourArea(contorno) / (cuadro.shape[0] * cuadro.shape[1])
            extension = np.ptp(dst_validos, axis=0) / [cuadro.shape[1], cuadro.shape[0]]
            if cobertura < .08 or extension[0] < .4 or extension[1] < .3:
                continue
            try:
                efectiva = referencia.homografia @ np.linalg.inv(h)
                controles = cv2.perspectiveTransform(src[validos].reshape(-1, 1, 2), h).reshape(-1, 2)
                error = float(np.median(np.linalg.norm(controles - dst_validos, axis=1)))
                if error < 1.5 and (mejor is None or cantidad > mejor[1]):
                    mejor = (efectiva, cantidad, error)
            except np.linalg.LinAlgError:
                continue
        return mejor
