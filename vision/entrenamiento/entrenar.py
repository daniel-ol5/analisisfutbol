"""Afina YOLO11 con un dataset de fútbol anotado en formato YOLO."""

from __future__ import annotations

import argparse
from pathlib import Path

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
    proyecto: Path | None = None,
) -> Path:
    """Afina YOLO11 sobre las clases indicadas en `dataset_yaml`.

    `batch=-1`: tamano de batch automatico de ultralytics segun la memoria
    de GPU disponible. `imgsz=960`: mayor que el default (640) porque el
    balon ocupa pocos pixeles en un plano general de cancha completa.

    Devuelve la ruta a los pesos entrenados (`weights/best.pt`).
    """
    from ultralytics import YOLO

    datos = dataset_yaml.resolve(strict=True)
    if not (batch == -1 or 0 < batch < 1 or batch >= 1 and float(batch).is_integer()):
        raise ValueError("El batch debe ser -1, una fracción de la VRAM o un entero positivo")
    if batch >= 1:
        batch = int(batch)
    modelo = YOLO(pesos_base)
    opciones = {"project": str(proyecto.resolve()), "name": datos.stem} if proyecto else {}
    modelo.train(
        data=str(datos),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        **opciones,
    )
    return Path(modelo.trainer.best)


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument(
        "--batch", type=float, default=-1, help="-1, fracción de VRAM o tamaño entero"
    )
    parser.add_argument("--device", default="0", help="indice de GPU (ej. '0') o 'cpu'")
    parser.add_argument("--pesos-base", default=PESOS_BASE)
    parser.add_argument("--dataset", type=Path, default=DATASET_YAML, help="YAML del dataset anotado")
    parser.add_argument("--proyecto", type=Path, help="Carpeta para guardar las corridas")
    args = parser.parse_args()

    pesos = entrenar(
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        pesos_base=args.pesos_base,
        dataset_yaml=args.dataset,
        proyecto=args.proyecto,
    )
    print(f"Pesos entrenados en: {pesos}")


if __name__ == "__main__":
    _cli()
