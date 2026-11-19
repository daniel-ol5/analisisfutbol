"""Carga del modelo YOLO  —  CU-24.

El import de `ultralytics` es perezoso (ocurre dentro de `cargar()`, no al
importar este archivo): asi el resto del pipeline se puede importar y probar
en una maquina sin `ultralytics`/`torch` instalados, que es la norma fuera de
la maquina con GPU (ver vision/README.md).
"""

from __future__ import annotations

import hashlib
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seguimiento.tipos import Clase

log = logging.getLogger(__name__)

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


def validar_clases(nombres: dict[int, str] | list[str], clases: dict[int, Clase]) -> None:
    """Impide interpretar etiquetas de otro checkpoint como jugadores o balón."""
    alias = {
        Clase.JUGADOR: {"person", "player", "jugador"},
        Clase.PORTERO: {"goalkeeper", "goalie", "portero", "arquero"},
        Clase.ARBITRO: {"referee", "arbitro"},
        Clase.BALON: {"ball", "sports ball", "balon", "pelota"},
    }
    nombres = dict(enumerate(nombres)) if isinstance(nombres, list) else nombres
    for indice, clase in clases.items():
        nombre = str(nombres.get(indice, "")).lower().replace("_", " ").strip()
        nombre = "".join(c for c in unicodedata.normalize("NFD", nombre) if not unicodedata.combining(c))
        if nombre not in alias[clase]:
            raise ValueError(
                f"Modelo incompatible: clase {indice} es {nombre!r}, se esperaba {clase.value}. "
                "Selecciona el mapa de clases correspondiente a estos pesos."
            )


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
        self._dispositivo_observado: str | None = None
        self._cajas_antes_del_tracker: tuple[Any, ...] = ()

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

    def dispositivo_inferencia(self) -> str | None:
        """Dispositivo del predictor que ejecutó la inferencia, no de los pesos base.

        Ultralytics puede copiar el modelo al preparar su predictor. Consultar
        `YOLO.model.parameters()` puede devolver CPU aunque el predictor use CUDA.
        Se conserva también la lectura tomada al terminar una inferencia, para
        que siga disponible aunque Ultralytics libere o sustituya el predictor.
        """
        if self._dispositivo_observado is not None:
            return self._dispositivo_observado
        predictor = getattr(self._modelo, "predictor", None)
        dispositivo = getattr(predictor, "device", None)
        return str(dispositivo) if dispositivo is not None else None

    def _guardar_resultado_previo(self, predictor: Any) -> None:
        dispositivo = getattr(predictor, "device", None)
        self._dispositivo_observado = str(dispositivo) if dispositivo is not None else None
        # Este callback se registra antes del callback de seguimiento de Ultralytics.
        self._cajas_antes_del_tracker = tuple(r.boxes for r in getattr(predictor, "results", ()))

    def _adjuntar_cajas_originales(self, predictor: Any) -> None:
        # El tracker puede reemplazar cada Results por un subconjunto de detecciones.
        for resultado, cajas in zip(predictor.results, self._cajas_antes_del_tracker, strict=True):
            resultado.cajas_antes_del_tracker = cajas
        self._cajas_antes_del_tracker = ()

    def cargar(self) -> Any:
        from ultralytics import YOLO  # importa torch: solo en la maquina con GPU

        modelo = YOLO(self.config.ruta_pesos)
        validar_clases(modelo.names, self.config.clases)
        modelo.add_callback("on_predict_postprocess_end", self._guardar_resultado_previo)
        modelo.add_callback("on_predict_batch_end", self._adjuntar_cajas_originales)
        self._dispositivo_observado = None
        self._cajas_antes_del_tracker = ()
        ruta = Path(self.config.ruta_pesos)
        digest = None
        if ruta.is_file():
            with ruta.open("rb") as archivo:
                digest = hashlib.file_digest(archivo, "sha256").hexdigest()
        log.info("Modelo cargado: %s | SHA256=%s | clases=%s", ruta, digest, modelo.names)
        self._modelo = modelo
        return self._modelo

    @property
    def modelo(self) -> Any:
        if self._modelo is None:
            self.cargar()
        return self._modelo
