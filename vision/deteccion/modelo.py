"""Carga del modelo YOLO  —  CU-24.

El import de `ultralytics` es perezoso (ocurre dentro de `cargar()`, no al
importar este archivo): asi el resto del pipeline se puede importar y probar
en una maquina sin `ultralytics`/`torch` instalados, que es la norma fuera de
la maquina con GPU (ver vision/README.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seguimiento.tipos import Clase

from pathlib import Path

# Pesos preentrenados especializados en fútbol (Roboflow / SoccerNet)
_PESOS_FUTBOL = Path(__file__).resolve().parent.parent / "pesos" / "yolov8_futbol.pt"

# Mapa de clases por defecto: IDs de COCO, para desarrollar con el YOLO11
# preentrenado antes de tener un modelo propio entrenado (CU-29).
# 0 = "person" -> jugador, 32 = "sports ball" -> balon.
# COCO no tiene clase de arbitro: con este mapa el arbitro se detecta como
# jugador, y solo se distingue despues por color (HU-21, seguimiento/color.py).
CLASES_COCO: dict[int, Clase] = {0: Clase.JUGADOR, 32: Clase.BALON}

# Mapa de clases del modelo propio (CU-29): mismo orden e indices que
# `entrenamiento/dataset.yaml::names` (`vision/tests/test_entrenamiento.py`
# falla si se desincronizan). Se usa en cuanto ese modelo este entrenado y
# registrado via `POST /vision/modelos` — hasta entonces no hay pesos que
# produzcan estos 3 indices y `CLASES_COCO` sigue siendo el default real.
CLASES_PROPIO: dict[int, Clase] = {0: Clase.JUGADOR, 1: Clase.ARBITRO, 2: Clase.BALON}

# Mapa de clases del modelo especializado de fútbol (4 clases: ball, goalkeeper, player, referee)
CLASES_FUTBOL: dict[int, Clase] = {0: Clase.BALON, 1: Clase.PORTERO, 2: Clase.JUGADOR, 3: Clase.ARBITRO}


@dataclass
class ConfigModelo:
    ruta_pesos: str = "yolo11n.pt"
    confianza_min: float = 0.08
    dispositivo: str = "cuda:0"
    tamano_img: int = 1280
    iou_nms: float = 0.45
    mitad_precision: bool = False
    clases: dict[int, Clase] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.clases:
            if "futbol" in str(self.ruta_pesos).lower():
                self.clases = dict(CLASES_FUTBOL)
            else:
                self.clases = dict(CLASES_COCO)


class ModeloDeteccion:
    """Envoltorio del modelo de ultralytics. No carga nada hasta que se use."""

    def __init__(self, config: ConfigModelo | None = None) -> None:
        self.config = config or ConfigModelo()
        self._modelo: Any | None = None

    def dispositivo_efectivo(self) -> str:
        """Resuelve el dispositivo seguro: si pide cuda pero torch no tiene CUDA, usa cpu."""
        dev = self.config.dispositivo
        if dev.startswith("cuda"):
            try:
                import torch
                if not torch.cuda.is_available():
                    return "cpu"
            except ImportError:
                return "cpu"
        return dev

    def cargar(self) -> Any:
        from ultralytics import YOLO  # importa torch: solo en la maquina con GPU

        self._modelo = YOLO(self.config.ruta_pesos)
        return self._modelo

    @property
    def modelo(self) -> Any:
        if self._modelo is None:
            self.cargar()
        return self._modelo
