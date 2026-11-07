"""Entrenamiento del modelo propio YOLO11 de 3 clases  —  CU-29.

No se puede ejecutar todavia: requiere el dataset anotado descrito en
`dataset.yaml` (jugador/arbitro/balon, formato YOLO), que no existe en este
repositorio ni en esta maquina — anotar un clip real de un partido es
trabajo humano, no de codigo (misma categoria de gap que T-055 a T-058 en
`vision/README.md`). Este archivo es el andamiaje listo para correr en la
maquina con GPU el dia que ese dataset exista, para no reinventar la
configuracion de entrenamiento en ese momento.

El import de `ultralytics` es perezoso (igual que en `deteccion/modelo.py`):
este modulo se puede importar y probar sin GPU ni ultralytics instalados.

Uso, una vez el dataset este anotado:

    python -m entrenamiento.entrenar --epochs 100 --imgsz 960 --device 0

Los pesos resultantes (`<proyecto>/weights/best.pt`) se suben a un storage
propio con URL https y se registran con `POST /vision/modelos`
(`ModeloCrear.archivo_url` exige https — ver `backend/app/vision/schemas.py`)
junto con las metricas de `vision/evaluacion/` (map50 por clase, idf1) sobre
el set de validacion.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).parent
DATASET_YAML = _AQUI / "dataset.yaml"

# Mismo punto de partida que `deteccion/modelo.py::ConfigModelo.ruta_pesos`:
# afinar (fine-tune) el YOLO11 preentrenado en vez de entrenar desde cero
# necesita muchas menos imagenes anotadas para llegar a un mAP util.
PESOS_BASE = "yolo11n.pt"


def entrenar(
    epochs: int = 100,
    imgsz: int = 960,
    batch: int | float = -1,
    device: str = "0",
    pesos_base: str = PESOS_BASE,
    dataset_yaml: Path = DATASET_YAML,
) -> Path:
    """Afina YOLO11 sobre `dataset_yaml` (3 clases: jugador, arbitro, balon).

    `batch=-1`: tamano de batch automatico de ultralytics segun la memoria
    de GPU disponible. `imgsz=960`: mayor que el default (640) porque el
    balon ocupa pocos pixeles en un plano general de cancha completa.

    Devuelve la ruta a los pesos entrenados (`weights/best.pt`).
    """
    from ultralytics import YOLO

    modelo = YOLO(pesos_base)
    resultado: Any = modelo.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
    )
    return Path(resultado.save_dir) / "weights" / "best.pt"


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument(
        "--batch", type=float, default=-1, help="-1 para tamano automatico de ultralytics"
    )
    parser.add_argument("--device", default="0", help="indice de GPU (ej. '0') o 'cpu'")
    parser.add_argument("--pesos-base", default=PESOS_BASE)
    args = parser.parse_args()

    pesos = entrenar(
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        pesos_base=args.pesos_base,
    )
    print(f"Pesos entrenados en: {pesos}")


if __name__ == "__main__":
    _cli()
