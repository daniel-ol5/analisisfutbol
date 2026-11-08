"""Prueba de regresión del modelo sobre el clip de referencia  —  T-064 (Pb-17).

Corre un modelo (pesos YOLO) sobre el clip de referencia anotado a mano,
calcula mAP@50 e IDF1 con `evaluacion.calcular_map50` / `calcular_idf1`, y
falla (código de salida 1) si la versión no alcanza los mínimos de T-055 o si
es peor que la versión activa del club. Con `--registrar` la da de alta en el
backend con sus métricas, sin activarla: al activarla, el backend vuelve a
aplicar la misma regla (409 si es peor que la vigente).

    cd vision
    python -m evaluacion.regresion --pesos runs/best.pt \\
        --clip referencia/clip.mp4 --anotaciones referencia/clip.json

    # y para registrarla si pasa:
    python -m evaluacion.regresion ... --api http://localhost:8000/api \\
        --email analista@club.com --registrar --nombre futbol-propio --version v4 \\
        --archivo-url https://cdn.club.com/modelos/futbol-v4.pt

Formato de las anotaciones (un objeto por cuadro anotado; el número es el
índice del cuadro en el video, empezando en 0):

    {"cuadros": {"0":  [{"tid": 1, "clase": "JUGADOR", "caja": [x1, y1, x2, y2]},
                        {"tid": 0, "clase": "BALON",   "caja": [x1, y1, x2, y2]}],
                 "12": [...]}}

El clip de referencia todavía no existe (ver "Verificación de campo pendiente"
en vision/README.md): este comando queda listo para el día que esté anotado.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evaluacion.idf1 import calcular_idf1
from evaluacion.mapa import EvaluacionInvalida, calcular_map50
from seguimiento.tipos import Clase, Deteccion

# Criterios de aceptación de T-055 sobre el clip de referencia.
UMBRALES = {"map50_jugador": 0.85, "idf1": 0.70}

NOMBRES = {"map50_jugador": "mAP@50 jugador", "map50_balon": "mAP@50 balón", "idf1": "IDF1"}


@dataclass(frozen=True)
class Metricas:
    map50_jugador: float
    map50_balon: float | None  # None si el clip no tiene balón anotado
    idf1: float


def cargar_anotaciones(ruta: str | Path) -> dict[int, list[Deteccion]]:
    """Verdad terreno por índice de cuadro, en el formato del docstring del módulo."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    cuadros = datos.get("cuadros") if isinstance(datos, dict) else None
    if not isinstance(cuadros, dict) or not cuadros:
        raise ValueError("Las anotaciones necesitan un objeto 'cuadros' con al menos un cuadro")
    verdad: dict[int, list[Deteccion]] = {}
    for indice, objetos in cuadros.items():
        verdad[int(indice)] = [
            Deteccion.desde_caja(
                int(o["tid"]), Clase(o["clase"]), tuple(float(v) for v in o["caja"]), 1.0
            )
            for o in objetos
        ]
    return verdad


def alinear(
    detecciones: Iterable[tuple[int, list[Deteccion]]], verdad: dict[int, list[Deteccion]]
) -> tuple[list[list[Deteccion]], list[list[Deteccion]]]:
    """Empareja, cuadro a cuadro, lo detectado con lo anotado. Un cuadro anotado sin
    detecciones cuenta como "no detectó nada" (no se descarta: eso inflaría la métrica)."""
    por_cuadro = dict(detecciones)
    indices = sorted(verdad)
    return [por_cuadro.get(i, []) for i in indices], [verdad[i] for i in indices]


def evaluar(
    detecciones_por_cuadro: Sequence[Sequence[Deteccion]],
    verdad_por_cuadro: Sequence[Sequence[Deteccion]],
) -> Metricas:
    # pycocotools escribe "creating index..." en stdout; la salida de este
    # comando es JSON (para usarla desde scripts), así que eso va a stderr.
    with contextlib.redirect_stdout(sys.stderr):
        return _evaluar(detecciones_por_cuadro, verdad_por_cuadro)


def _evaluar(
    detecciones_por_cuadro: Sequence[Sequence[Deteccion]],
    verdad_por_cuadro: Sequence[Sequence[Deteccion]],
) -> Metricas:
    try:
        map50_balon = calcular_map50(detecciones_por_cuadro, verdad_por_cuadro, Clase.BALON)
    except EvaluacionInvalida:
        map50_balon = None
    return Metricas(
        map50_jugador=calcular_map50(detecciones_por_cuadro, verdad_por_cuadro, Clase.JUGADOR),
        map50_balon=map50_balon,
        idf1=calcular_idf1(detecciones_por_cuadro, verdad_por_cuadro, Clase.JUGADOR),
    )


def fallas(metricas: Metricas, vigente: dict[str, Any] | None = None) -> list[str]:
    """Motivos por los que la versión no pasa; vacío si pasa.

    1. Mínimos de T-055.
    2. No empeorar respecto de la versión activa (misma regla que el backend al
       activar: se compara lo que la activa tiene medido).
    """
    motivos = [
        f"{NOMBRES[campo]} {getattr(metricas, campo):.3f} por debajo del mínimo {minimo:.2f} (T-055)"
        for campo, minimo in UMBRALES.items()
        if getattr(metricas, campo) < minimo
    ]
    if vigente:
        for campo, nombre in NOMBRES.items():
            antes, ahora = vigente.get(campo), getattr(metricas, campo)
            if antes is None:
                continue
            if ahora is None:
                motivos.append(f"{nombre} sin medir (la versión activa tiene {antes:.2f})")
            elif ahora < antes:
                motivos.append(
                    f"{nombre} {ahora:.3f} peor que la versión activa "
                    f"{vigente.get('version', '')} ({antes:.3f})"
                )
    return motivos


Detectar = Callable[[str, Path], Iterable[tuple[int, list[Deteccion]]]]


def detectar_con_yolo(dispositivo: str, clases: str) -> Detectar:
    """Corre el modelo sobre TODOS los cuadros (vid_stride=1): el tracker necesita
    la secuencia completa para que los `tid` sean los mismos que en producción."""

    def detectar(pesos: str, clip: Path) -> Iterable[tuple[int, list[Deteccion]]]:
        from deteccion.modelo import CLASES_COCO, CLASES_PROPIO, ConfigModelo, ModeloDeteccion
        from procesamiento.fuente import seguir_con_cuadros

        config = ConfigModelo(
            ruta_pesos=pesos,
            dispositivo=dispositivo,
            clases=dict(CLASES_PROPIO if clases == "propio" else CLASES_COCO),
        )
        for indice, (_, detecciones) in enumerate(
            seguir_con_cuadros(ModeloDeteccion(config), clip, vid_stride=1)
        ):
            yield indice, detecciones

    return detectar


def correr(args: argparse.Namespace, detectar: Detectar, api: Any | None = None) -> int:
    """Evalúa, informa y (si se pide) registra. Devuelve el código de salida."""
    verdad = cargar_anotaciones(args.anotaciones)
    detectadas, anotadas = alinear(detectar(args.pesos, Path(args.clip)), verdad)
    metricas = evaluar(detectadas, anotadas)

    vigente = api.modelo_activo() if api else None
    motivos = fallas(metricas, vigente)
    print(json.dumps({
        "metricas": asdict(metricas),
        "cuadros_evaluados": len(anotadas),
        "version_activa": vigente and {k: vigente.get(k) for k in ("nombre", "version", *NOMBRES)},
        "pasa": not motivos,
        "fallas": motivos,
    }, indent=2, ensure_ascii=False))

    if motivos:
        return 1
    if args.registrar and api:
        registrado = api.registrar_modelo({
            "nombre": args.nombre,
            "version": args.version,
            "tipo": "DETECCION",
            "archivo_url": args.archivo_url,
            **{k: round(v, 4) for k, v in asdict(metricas).items() if v is not None},
            "notas": f"Regresión sobre {Path(args.clip).name}: {len(anotadas)} cuadros anotados",
        })
        print(f"Registrada {args.nombre} {args.version} (id {registrado['id']}), sin activar.")
    return 0


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prueba de regresión del modelo (T-064)")
    p.add_argument("--pesos", required=True, help="Archivo .pt a evaluar")
    p.add_argument("--clip", required=True, help="Clip de referencia")
    p.add_argument("--anotaciones", required=True, help="JSON con la verdad terreno")
    p.add_argument("--dispositivo", default="cuda:0")
    p.add_argument("--clases", choices=["coco", "propio"], default="coco")
    p.add_argument("--api", help="Para comparar con la versión activa del club (y registrar)")
    p.add_argument("--email", help="Usuario ADMIN o ANALISTA")
    p.add_argument("--password", default=os.environ.get("VISION_PASSWORD"))
    p.add_argument("--registrar", action="store_true", help="Dar de alta la versión si pasa")
    p.add_argument("--nombre")
    p.add_argument("--version")
    p.add_argument("--archivo-url", help="URL https de los pesos (nunca al repositorio)")
    args = p.parse_args(argv)
    if args.api and not (args.email and args.password):
        p.error("Con --api hacen falta --email y --password (o VISION_PASSWORD)")
    if args.registrar and not (args.api and args.nombre and args.version and args.archivo_url):
        p.error("--registrar necesita --api, --nombre, --version y --archivo-url")
    return args


def main(argv: list[str] | None = None) -> int:
    args = argumentos(argv)
    api = None
    if args.api:
        from procesamiento.api import ApiBackend

        api = ApiBackend(args.api, args.email, args.password)
    return correr(args, detectar_con_yolo(args.dispositivo, args.clases), api)


if __name__ == "__main__":
    sys.exit(main())
