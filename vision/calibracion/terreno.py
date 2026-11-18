"""Comprobación de una proyección contra líneas pintadas, independiente del residual de hitos."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares


def mascara_terreno(cuadro: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(cuadro, cv2.COLOR_BGR2HSV)
    verde = cv2.inRange(hsv, (28, 30, 25), (90, 255, 255))
    verde = cv2.morphologyEx(verde, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contornos, _ = cv2.findContours(verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    if contornos:
        mayor = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(mayor) > .15 * mascara.size:
            cv2.fillConvexPoly(mascara, cv2.convexHull(mayor), 255)
            mascara = cv2.dilate(mascara, np.ones((7, 7), np.uint8))
    return mascara


def segmentos_lineas(largo: float, ancho: float) -> list:
    segmentos = [((0, 0), (largo, 0)), ((0, ancho), (largo, ancho)),
                 ((0, 0), (0, ancho)), ((largo, 0), (largo, ancho)),
                 ((largo / 2, 0), (largo / 2, ancho))]
    for fondo, signo in ((0, 1), (largo, -1)):
        for profundidad, semiancho in ((16.5, 20.16), (5.5, 9.16)):
            x = fondo + signo * profundidad
            abajo, arriba = ancho / 2 - semiancho, ancho / 2 + semiancho
            segmentos.extend([((fondo, abajo), (x, abajo)), ((x, abajo), (x, arriba)),
                              ((x, arriba), (fondo, arriba))])
    return segmentos


def puntos_lineas(largo: float = 105, ancho: float = 68) -> np.ndarray:
    segmentos = segmentos_lineas(largo, ancho)
    puntos = [np.linspace(a, b, max(4, int(np.linalg.norm(np.subtract(a, b)) / 1.5)))
              for a, b in segmentos]
    angulos = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    puntos.append(np.c_[largo / 2 + 9.15 * np.cos(angulos), ancho / 2 + 9.15 * np.sin(angulos)])
    for fondo, signo in ((0, 1), (largo, -1)):
        arco = np.c_[fondo + signo * (11 + 9.15 * np.cos(angulos)), ancho / 2 + 9.15 * np.sin(angulos)]
        puntos.append(arco[signo * (arco[:, 0] - fondo) >= 16.5])
    return np.vstack(puntos).astype(np.float64)


def lineas_imagen(h: np.ndarray, largo: float, ancho: float, ancho_px: int, alto_px: int) -> list:
    """Polilíneas en porcentaje del video para inspección visual de la calibración."""
    lineas = [np.array([[0, 0], [largo, 0], [largo, ancho], [0, ancho], [0, 0]]),
              np.array([[largo / 2, 0], [largo / 2, ancho]])]
    for fondo, signo in ((0, 1), (largo, -1)):
        for prof, semi in ((16.5, 20.16), (5.5, 9.16)):
            a, b = ancho / 2 - semi, ancho / 2 + semi
            lineas.append(np.array([[fondo, a], [fondo + signo * prof, a],
                                   [fondo + signo * prof, b], [fondo, b]]))
    ang = np.linspace(0, 2 * np.pi, 48)
    lineas.append(np.c_[largo / 2 + 9.15 * np.cos(ang), ancho / 2 + 9.15 * np.sin(ang)])
    try:
        inversa = np.linalg.inv(h)
        salida = []
        for linea in lineas:
            puntos = cv2.perspectiveTransform(linea.astype(np.float64).reshape(-1, 1, 2), inversa).reshape(-1, 2)
            if np.isfinite(puntos).all() and np.abs(puntos).max() < max(ancho_px, alto_px) * 50:
                salida.append(np.round(puntos / [ancho_px, alto_px] * 100, 2).tolist())
        return salida
    except (cv2.error, np.linalg.LinAlgError):
        return []


def refinar_con_lineas(cuadro: np.ndarray, h: np.ndarray, largo: float, ancho: float,
                       optimizar: bool = True) -> tuple[np.ndarray, float, bool]:
    """Refina una semilla absoluta; rechaza líneas desalineadas o muy poco visibles.

    El error devuelto está en píxeles de la imagen original, nunca en metros.
    No convierte una cancha sin referencia semántica en una ubicación absoluta.
    """
    alto, anchopx = cuadro.shape[:2]
    escala = min(1., 800 / anchopx)
    pequena = cv2.resize(cuadro, None, fx=escala, fy=escala)
    suelo = mascara_terreno(pequena)
    hsv = cv2.cvtColor(pequena, cv2.COLOR_BGR2HSV)
    gris = cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY)
    contraste = cv2.subtract(gris, cv2.GaussianBlur(gris, (0, 0), 3))
    blancas = (cv2.inRange(hsv, (0, 0, 110), (179, 130, 255)) & suelo
               & np.where(contraste > 4, 255, 0).astype(np.uint8))
    if np.count_nonzero(blancas) < 80:
        return h, float("inf"), False
    distancia = cv2.distanceTransform(255 - blancas, cv2.DIST_L2, 3)
    distancia = cv2.GaussianBlur(distancia, (3, 3), .6)
    si = np.diag([anchopx, alto, 1.])
    sc = np.diag([largo, ancho, 1.])
    try:
        inversa = np.linalg.inv(si) @ np.linalg.inv(h) @ sc
    except np.linalg.LinAlgError:
        return h, float("inf"), False
    inversa /= inversa[2, 2]
    mundo = puntos_lineas(largo, ancho) / [largo, ancho]

    def proyectar(p: np.ndarray) -> np.ndarray:
        matriz = np.r_[p, 1.].reshape(3, 3)
        return cv2.perspectiveTransform(mundo.reshape(-1, 1, 2), matriz).reshape(-1, 2) * [anchopx * escala, alto * escala]

    p0 = inversa.ravel()[:8]
    inicial = proyectar(p0)
    ap, lp = pequena.shape[:2]
    visibles = ((inicial[:, 0] > 4) & (inicial[:, 0] < lp - 4)
                & (inicial[:, 1] > 4) & (inicial[:, 1] < ap - 4))
    if visibles.sum() < 35:
        return h, float("inf"), False

    # Asociar segmentos semánticos con rectas observadas cerca de la semilla.
    # Evita que el ajuste salte de una banda a una línea del área técnica.
    hough = cv2.HoughLinesP(blancas, 1, np.pi / 720, threshold=35,
                            minLineLength=max(30, lp // 20), maxLineGap=12)
    anclajes = []
    if hough is not None:
        for indice_linea, (a, b) in enumerate(segmentos_lineas(largo, ancho)):
            extremos = np.array([a, b], np.float64) / [largo, ancho]
            px = cv2.perspectiveTransform(extremos.reshape(-1, 1, 2), inversa).reshape(-1, 2) * [lp, ap]
            direccion = px[1] - px[0]
            longitud = np.linalg.norm(direccion)
            if longitud < 25:
                continue
            direccion /= longitud
            normal = np.array([-direccion[1], direccion[0]])
            mejor = None
            for x1, y1, x2, y2 in hough.reshape(-1, 4):
                vector = np.array([x2 - x1, y2 - y1], dtype=float)
                norm = np.linalg.norm(vector)
                if norm < 20 or abs(np.dot(vector / norm, normal)) > .30:
                    continue
                medio = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
                distancia_linea = abs(np.dot(medio - px[0], normal))
                recorrido = np.dot(medio - px[0], direccion) / longitud
                if distancia_linea > max(35, .04 * lp) or not -.2 < recorrido < 1.2:
                    continue
                score = distancia_linea - .3 * np.log(norm)
                if mejor is None or score < mejor[0]:
                    n = np.array([-(y2 - y1), x2 - x1], dtype=float) / norm
                    mejor = (score, n, -np.dot(n, [x1, y1]))
            if mejor is not None:
                muestras = np.linspace(extremos[0], extremos[1], 8)
                anclajes.append((muestras, mejor[1], mejor[2], 1.))
    if len(anclajes) < 4:
        return h, float("inf"), False

    # El círculo aporta escala en el interior del campo. Sus extremos en imagen
    # no se tratan como puntos métricos: se ajusta la cónica completa observada.
    angulos = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    circulo = np.c_[.5 + 9.15 / largo * np.cos(angulos), .5 + 9.15 / ancho * np.sin(angulos)]
    semilla_circulo = cv2.perspectiveTransform(circulo.reshape(-1, 1, 2), inversa).reshape(-1, 2) * [lp, ap]

    def distancia_elipse(px, elipse):
        (cx, cy), (diam_a, diam_b), angulo = elipse
        rad = np.deg2rad(angulo)
        rotacion = np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])
        q = (px - [cx, cy]) @ rotacion / [diam_a / 2, diam_b / 2]
        return (np.linalg.norm(q, axis=1) - 1) * min(diam_a, diam_b) / 2

    elipse = None
    try:
        inicial_elipse = cv2.fitEllipse(semilla_circulo.astype(np.float32))
        yy, xx = np.nonzero(blancas)
        candidatos = np.c_[xx, yy].astype(np.float32)
        dist = distancia_elipse(candidatos, inicial_elipse)
        radio = min(inicial_elipse[1]) / 2
        candidatos = candidatos[np.abs(dist) < max(25, radio * .65)]
        # Excluir la línea de mediocampo, que atraviesa el círculo.
        media = cv2.perspectiveTransform(np.float64([[[.5, 0]], [[.5, 1]]]), inversa).reshape(-1, 2) * [lp, ap]
        v = media[1] - media[0]
        normal = np.array([-v[1], v[0]]) / np.linalg.norm(v)
        candidatos = candidatos[np.abs((candidatos - media[0]) @ normal) > 4]
        elegidos = candidatos
        for _ in range(5):
            if len(elegidos) < 40:
                break
            ajuste = cv2.fitEllipse(elegidos)
            dist = np.abs(distancia_elipse(candidatos, ajuste))
            elegidos = candidatos[dist < min(4., np.quantile(dist, .7))]
        if len(elegidos) >= 40:
            centro, ejes, _ = ajuste
            if (.3 < min(ejes) / max(ejes) < .95 and
                    np.linalg.norm(np.array(centro) - inicial_elipse[0]) < .08 * lp):
                elipse = ajuste
    except (cv2.error, ValueError, ZeroDivisionError):
        elipse = None

    def errores_rectas(p: np.ndarray) -> np.ndarray:
        matriz = np.r_[p, 1.].reshape(3, 3)
        errores_linea = []
        for muestras, normal, constante, peso in anclajes:
            px = cv2.perspectiveTransform(muestras.reshape(-1, 1, 2), matriz).reshape(-1, 2) * [lp, ap]
            errores_linea.extend(peso * (px @ normal + constante))
        return np.array(errores_linea)

    def errores(p: np.ndarray) -> np.ndarray:
        px = proyectar(p)[visibles]
        dist = map_coordinates(distancia, [px[:, 1], px[:, 0]], order=1, mode="constant", cval=30)
        error_circulo = []
        if elipse is not None:
            px_circulo = cv2.perspectiveTransform(circulo.reshape(-1, 1, 2), np.r_[p, 1.].reshape(3, 3)).reshape(-1, 2) * [lp, ap]
            error_circulo = 3 * distancia_elipse(px_circulo, elipse)
        return np.r_[dist, 3 * errores_rectas(p), error_circulo, .5 * (p - p0)]

    try:
        p = least_squares(errores, p0, loss="soft_l1", f_scale=3,
                          diff_step=1e-4, max_nfev=35).x if optimizar else p0
        residuales = errores(p)[:int(visibles.sum())]
        error = float(np.median(residuales) / escala)
        proporcion = float(np.mean(residuales < 5 * escala))
        nueva = sc @ np.linalg.inv(np.r_[p, 1.].reshape(3, 3)) @ np.linalg.inv(si)
        nueva /= nueva[2, 2]
        desplazamiento = np.median(np.linalg.norm(proyectar(p)[visibles] - inicial[visibles], axis=1))
        valida = (np.isfinite(nueva).all() and error < 2 / escala and proporcion > .55
                  and np.median(np.abs(errores_rectas(p))) < 8
                  and desplazamiento < .10 * np.hypot(lp, ap))
        return (nueva if valida else h), error, valida
    except (ValueError, np.linalg.LinAlgError, cv2.error):
        return h, float("inf"), False
