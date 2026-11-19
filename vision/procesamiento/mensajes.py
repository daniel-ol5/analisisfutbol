"""De un cuadro con detecciones a un `MensajeWorker`  —  CU-27 (T-061).

Une las piezas del pipeline:
    detecciones (YOLO + ByteTrack)
    ├──► compensación de movimiento global (GMC) y homografía dinámica
    ├──► color de equipo con suavizado temporal (CU-25)
    ├──► seguimiento cinemático del balón
    └──► homografía a metros (CU-26)

y arma el mismo diccionario que el worker manda en vivo
(`backend/app/partido/schemas.py::MensajeWorker`). Que sea el mismo contrato es
lo que hace que un video procesado genere las mismas entidades que un partido
en vivo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from calibracion.dinamica import (
    _PESOS_KEYPOINTS_DEFECTO,
    EstimadorHomografiaPitch,
    RastreadorHomografiaDinamica,
)
from calibracion.homografia import proyectar_detecciones
from calibracion.terreno import lineas_imagen
from seguimiento.balon import RastreadorBalon
from seguimiento.color import (
    CalibradorEquiposPartido,
    ClasificadorTemporalEquipos,
    ColoresEquipo,
    RecorteVacio,
    agrupar_equipos,
    clasificar_equipos,
    color_dominante,
    recortar_torso,
)
from seguimiento.gmc import CompensadorMovimientoCamara, TransformacionCamara
from seguimiento.tipos import Clase, Deteccion, EquipoDetectado

# Mismo umbral que el backend para marcar la calidad como degradada (CU-39).
MIN_JUGADORES_SANO = 16


@dataclass(frozen=True, slots=True)
class Contexto:
    """Lo que no cambia en todo el video (sale del `Trabajo` del backend)."""

    partido_id: int
    homografia: np.ndarray | None
    es_local: bool
    color_propio: str
    color_rival: str | None
    fps_muestreo: float
    largo_m: float = 105.0
    ancho_m: float = 68.0
    modo_calibracion: str = "MANUAL"
    referencia: dict | None = None


@dataclass
class EstadoPipeline:
    """Estado persistente del pipeline entre fotogramas consecutivos."""

    gmc: CompensadorMovimientoCamara = field(default_factory=CompensadorMovimientoCamara)
    balon: RastreadorBalon = field(default_factory=RastreadorBalon)
    clasificador_temporal: ClasificadorTemporalEquipos = field(default_factory=ClasificadorTemporalEquipos)
    calibrador_equipos: CalibradorEquiposPartido | None = None
    rastreador_homografia: RastreadorHomografiaDinamica | None = None
    dispositivo: str = "cpu"
    largo_m: float = 105.0
    ancho_m: float = 68.0
    habilitar_reconocimiento: bool = False

    def __post_init__(self) -> None:
        if self.rastreador_homografia is None:
            estimador = None
            if self.habilitar_reconocimiento and _PESOS_KEYPOINTS_DEFECTO.exists():
                estimador = EstimadorHomografiaPitch(ruta_pesos=_PESOS_KEYPOINTS_DEFECTO,
                    dispositivo=self.dispositivo, largo_m=self.largo_m, ancho_m=self.ancho_m)
            self.rastreador_homografia = RastreadorHomografiaDinamica(
                estimador_pitch=estimador,
                gmc=self.gmc,
            )


def _vector_de_hex(color_hex: str) -> np.ndarray:
    """Mismo espacio CIELAB normalizado [L, a, b] que `color_dominante`."""
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
        cerca = len(datos) == 1 and np.linalg.norm(datos[0] - propio) < 0.6
        return [_equipo_propio(ctx) if cerca else _equipo_rival(ctx)] * len(datos)

    etiquetas = agrupar_equipos(datos, k=2)
    distancias = []
    for grupo in (0, 1):
        miembros = datos[etiquetas == grupo]
        distancias.append(np.linalg.norm(miembros.mean(axis=0) - propio) if len(miembros) else np.inf)
    grupo_propio = int(np.argmin(distancias))
    return [_equipo_propio(ctx) if e == grupo_propio else _equipo_rival(ctx) for e in etiquetas]


def equipos_de(
    cuadro: np.ndarray,
    personas: Sequence[Deteccion],
    ctx: Contexto,
    clasificador_temporal: ClasificadorTemporalEquipos | None = None,
    calibrador_equipos: CalibradorEquiposPartido | None = None,
    posiciones_m: Sequence[tuple[float, float]] | None = None,
) -> list[EquipoDetectado]:
    """Equipo de cada persona detectada, en el mismo orden (CU-25 / Fase F4)."""
    equipos: list[EquipoDetectado | None] = [None] * len(personas)
    colores: list[np.ndarray] = []
    indices: list[int] = []
    confs: list[float] = [float(d.conf) for d in personas]

    for i, d in enumerate(personas):
        if d.clase == Clase.ARBITRO:
            equipos[i] = EquipoDetectado.ARBITRO
            continue
        try:
            colores.append(color_dominante(recortar_torso(cuadro, d.caja)))
            indices.append(i)
        except RecorteVacio:
            equipos[i] = EquipoDetectado.DESCONOCIDO

    if colores:
        if calibrador_equipos is not None:
            # 1. Acumular muestras de jugadores de campo en el calibrador
            for idx, col in zip(indices, colores, strict=True):
                d = personas[idx]
                es_port = (d.clase == Clase.PORTERO)
                calibrador_equipos.acumular_muestra(col, tid=d.tid, es_portero=es_port)

            # 2. Clasificar cada jugador contra los centroides empíricos
            for idx, col in zip(indices, colores, strict=True):
                d = personas[idx]
                pos_m = posiciones_m[idx] if posiciones_m and idx < len(posiciones_m) else None
                es_port = (d.clase == Clase.PORTERO)
                res = calibrador_equipos.clasificar_jugador(col, posicion_m=pos_m, es_portero=es_port)
                equipos[idx] = res.equipo
                confs[idx] = res.confianza
        elif ctx.color_rival:
            local, visitante = (
                (ctx.color_propio, ctx.color_rival) if ctx.es_local
                else (ctx.color_rival, ctx.color_propio)
            )
            clasificados = clasificar_equipos(colores, ColoresEquipo(local, visitante))
            for idx, c in zip(indices, clasificados, strict=True):
                equipos[idx] = c.equipo
                confs[idx] = c.confianza
        else:
            clasificados = _por_cercania_al_propio(colores, ctx)
            for idx, eq in zip(indices, clasificados, strict=True):
                equipos[idx] = eq

    resultado = [e or EquipoDetectado.DESCONOCIDO for e in equipos]

    # Suavizado temporal si se dispone del clasificador
    if clasificador_temporal is not None:
        suavizados = []
        for d, eq, conf in zip(personas, resultado, confs, strict=True):
            if d.tid > 0:
                eq_suave, _ = clasificador_temporal.registrar_y_suavizar(d.tid, eq, conf)
                suavizados.append(eq_suave)
            else:
                suavizados.append(eq)
        clasificador_temporal.avanzar_cuadro()
        if calibrador_equipos is not None:
            calibrador_equipos.avanzar_cuadro()
        return suavizados

    if calibrador_equipos is not None:
        calibrador_equipos.avanzar_cuadro()

    return resultado


def _punto(
    d: Deteccion,
    equipo: EquipoDetectado,
    xy: tuple[float, float],
    ancho_px: int | None = None,
    alto_px: int | None = None,
) -> dict[str, Any]:
    # Las posiciones fuera del terreno se descartan antes, nunca se pegan al borde.
    x_m = round(float(xy[0]), 2)
    y_m = round(float(xy[1]), 2)
    punto: dict[str, Any] = {
        "tid": d.tid,
        "equipo": equipo.value,
        "x": x_m,
        "y": y_m,
        "conf": round(min(max(float(d.conf), 0.0), 1.0), 3),
    }
    if ancho_px and alto_px and ancho_px > 0 and alto_px > 0:
        x1_pct = round(100.0 * max(0.0, float(d.caja[0])) / ancho_px, 2)
        y1_pct = round(100.0 * max(0.0, float(d.caja[1])) / alto_px, 2)
        x2_pct = round(100.0 * min(float(ancho_px), float(d.caja[2])) / ancho_px, 2)
        y2_pct = round(100.0 * min(float(alto_px), float(d.caja[3])) / alto_px, 2)
        punto["bbox"] = [x1_pct, y1_pct, x2_pct, y2_pct]
    return punto


def _en_cancha(xy: tuple[float, float], ctx: Contexto) -> bool:
    return bool(np.isfinite(xy).all() and 0 <= xy[0] <= ctx.largo_m and 0 <= xy[1] <= ctx.ancho_m)


def campo_visible(h: np.ndarray, ancho: int, alto: int, ctx: Contexto) -> list[list[float]]:
    """Intersección del encuadre con el terreno; no inventa posiciones fuera de vista."""
    esquinas = np.array([[0, 0], [ancho, 0], [ancho, alto], [0, alto]], dtype=np.float32)
    denominadores = np.c_[esquinas, np.ones(4)] @ h[2]
    if not (np.all(denominadores > 1e-8) or np.all(denominadores < -1e-8)):
        return []  # El horizonte cruza la imagen; el cuadrilátero no es acotado.
    proy = cv2.perspectiveTransform(esquinas.reshape(-1, 1, 2), h)
    if not np.isfinite(proy).all():
        return []
    terreno = np.array([[0, 0], [ctx.largo_m, 0], [ctx.largo_m, ctx.ancho_m], [0, ctx.ancho_m]], dtype=np.float32)
    _, interseccion = cv2.intersectConvexConvex(cv2.convexHull(proy), terreno)
    return np.round(interseccion.reshape(-1, 2), 2).tolist() if interseccion is not None else []


def armar_mensaje(
    ctx: Contexto,
    t: float,
    cuadro: np.ndarray,
    detecciones: Sequence[Deteccion],
    estado: EstadoPipeline | None = None,
) -> dict[str, Any]:
    """Un `MensajeWorker` (como diccionario JSON) para el cuadro del segundo `t`."""
    alto, ancho = cuadro.shape[:2] if isinstance(cuadro, np.ndarray) and cuadro.ndim >= 2 else (None, None)
    personas = [d for d in detecciones if d.clase in (Clase.JUGADOR, Clase.PORTERO, Clase.ARBITRO)]
    balones = [d for d in detecciones if d.clase == Clase.BALON]
    detecciones_imagen = []
    if ancho and alto:
        for d in detecciones:
            x1, y1, x2, y2 = d.caja
            if not np.isfinite([x1, y1, x2, y2, d.conf]).all():
                continue
            detecciones_imagen.append({"tid": d.tid, "clase": d.clase.value, "conf": float(d.conf),
                "bbox": np.clip([100 * x1 / ancho, 100 * y1 / alto,
                                  100 * x2 / ancho, 100 * y2 / alto], 0, 100).tolist()})

    # 1. Compensación de movimiento de cámara (GMC) y homografía dinámica
    t_cam: TransformacionCamara | None = None
    homografia_efectiva = ctx.homografia
    calibracion_valida = True
    if estado is not None and isinstance(cuadro, np.ndarray) and cuadro.size > 0:
        referencia = ctx.referencia or {}
        if referencia.get("ancho_px") and (ancho, alto) != (referencia["ancho_px"], referencia["alto_px"]):
            raise ValueError("La fuente cambió de resolución respecto a la calibración")
        cajas = [p.caja for p in personas]
        if estado.rastreador_homografia is not None:
            homografia_efectiva = estado.rastreador_homografia.actualizar(
                cuadro,
                homografia_referencia=ctx.homografia,
                cajas_excluidas=cajas,
                t_s=t,
                permitir_referencia=(ctx.modo_calibracion == "MANUAL" and
                    (not referencia or abs(t - referencia.get("tiempo_s", 0)) < .002)),
            )
            t_cam = estado.gmc.ultima_transformacion
            calibracion_valida = estado.rastreador_homografia.valida
        else:
            t_cam = estado.gmc.estimar(cuadro, cajas_excluidas=cajas)
            homografia_efectiva = estado.gmc.homografia_compensada(ctx.homografia)

    if homografia_efectiva is None:
        calibracion_valida = False
        homografia_efectiva = np.eye(3)
    if not calibracion_valida:
        # La identidad o la última matriz no son una nueva calibración válida.
        personas, balones = [], []

    # 2. Proyección de jugadores a coordenadas de cancha en metros
    proy_personas = [(d, xy) for d, xy in proyectar_detecciones(personas, homografia_efectiva)
                    if _en_cancha(xy, ctx)]

    # 3. Calibrador empírico de indumentaria a nivel de partido (Fase F4)
    calibrador = None
    if estado is not None:
        if estado.calibrador_equipos is None and ctx.color_rival:
            local, visitante = (
                (ctx.color_propio, ctx.color_rival) if ctx.es_local
                else (ctx.color_rival, ctx.color_propio)
            )
            estado.calibrador_equipos = CalibradorEquiposPartido(
                colores_equipo=ColoresEquipo(color_local=local, color_visitante=visitante)
            )
        calibrador = estado.calibrador_equipos

    # 4. Clasificación de equipos con persistencia temporal y centroides empíricos
    clasif_temp = estado.clasificador_temporal if estado is not None else None
    equipos = equipos_de(
        cuadro,
        [d for d, _ in proy_personas],
        ctx,
        clasificador_temporal=clasif_temp,
        calibrador_equipos=calibrador,
        posiciones_m=[xy for _, xy in proy_personas],
    )

    # 5. Estructuración de jugadores
    mapa_jugadores: dict[int, dict[str, Any]] = {}
    for (d, xy), equipo in zip(proy_personas, equipos, strict=True):
        pt = _punto(d, equipo, xy, ancho, alto)
        tid = pt["tid"]
        if tid not in mapa_jugadores or pt["conf"] > mapa_jugadores[tid]["conf"]:
            mapa_jugadores[tid] = pt
    jugadores = list(mapa_jugadores.values())

    # 4. Seguimiento cinemático y oclusiones del balón
    balon = None
    if calibracion_valida and estado is not None and isinstance(cuadro, np.ndarray) and cuadro.size > 0:
        balon_det = estado.balon.actualizar(
            cuadro,
            detecciones if calibracion_valida else [],
            cajas_jugadores=[p.caja for p in personas],
            transformacion_camara=t_cam,
        )
        # Las predicciones cortas ayudan a reencontrarlo, pero no son posesión observada.
        if balon_det is not None and estado.balon.observado:
            proy = proyectar_detecciones([balon_det], homografia_efectiva)
            if proy:
                (_, xy), = proy
                if _en_cancha(xy, ctx):
                    balon = _punto(balon_det, EquipoDetectado.DESCONOCIDO, xy, ancho, alto)
    elif balones:
        mejor = max(balones, key=lambda d: d.conf)
        proy = proyectar_detecciones([mejor], homografia_efectiva)
        if proy:
            (_, xy), = proy
            if _en_cancha(xy, ctx):
                balon = _punto(mejor, EquipoDetectado.DESCONOCIDO, xy, ancho, alto)

    cantidad = sum(j["equipo"] in ("LOCAL", "VISITANTE") for j in jugadores)
    motivos = []
    if not calibracion_valida:
        motivos.append("Calibración perdida: se necesita una nueva referencia de cancha")
    if cantidad < MIN_JUGADORES_SANO:
        motivos.append(f"Cobertura parcial: {cantidad} jugadores de equipo visibles")
    if balon is None:
        motivos.append("Balón no observado; no inferir posesión")
    return {
        "partido": ctx.partido_id,
        "t": round(t, 3),
        "jugadores": jugadores,
        "balon": balon,
        "detecciones": detecciones_imagen,
        "calidad": {
            "worker_conectado": True,
            "fps": 0.0,  # El ejecutor mide rendimiento; no es una constante nominal.
            "jugadores_detectados": cantidad,
            "balon_visible": balon is not None,
            "retraso_s": 0.0,
            "degradado": bool(motivos),
            "motivo": "; ".join(motivos) or None,
            "calibracion_valida": calibracion_valida,
            "campo_visible": campo_visible(homografia_efectiva, ancho, alto, ctx) if calibracion_valida and ancho and alto else [],
            "largo_m": ctx.largo_m,
            "ancho_m": ctx.ancho_m,
            "estado_calibracion": estado.rastreador_homografia.estado if estado and estado.rastreador_homografia else ("VERIFICADA" if calibracion_valida else "SIN_REFERENCIA"),
            "ultimo_anclaje_t": estado.rastreador_homografia.ultimo_anclaje_t if estado and estado.rastreador_homografia else None,
            "error_lineas_px": estado.rastreador_homografia.error_lineas_px if estado and estado.rastreador_homografia else None,
            "lineas_imagen": lineas_imagen(homografia_efectiva, ctx.largo_m, ctx.ancho_m, ancho, alto) if calibracion_valida and ancho and alto else [],
        },
    }
