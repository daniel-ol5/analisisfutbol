"""Tipos compartidos entre `deteccion` y `seguimiento`  —  CU-24.

Sin dependencias de torch/ultralytics: se pueden importar y probar en
cualquier maquina, incluso sin GPU.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Clase(StrEnum):
    """Clase de deteccion de YOLO (no confundir con `EquipoDetectado`, que es
    el resultado de CU-25/color de camiseta sobre una deteccion ya `JUGADOR`).

    `ARBITRO` solo existe como clase propia en el modelo entrenado por CU-29
    (ver `deteccion/modelo.py::CLASES_PROPIO`); el modelo COCO de desarrollo
    (`CLASES_COCO`) no distingue arbitro de jugador a nivel de deteccion, por
    eso hoy el arbitro se separa despues, por color (HU-21).
    """

    JUGADOR = "JUGADOR"
    ARBITRO = "ARBITRO"
    BALON = "BALON"
    PORTERO = "PORTERO"


class EquipoDetectado(StrEnum):
    """Espejo de `backend/app/partido/schemas.py::EquipoDetectado`.

    Mismos valores de texto que el backend, sin importar su paquete: el
    worker de vision corre fuera de este backend (proceso y maquina propios,
    ver vision/README.md) y solo necesita que el texto coincida para que el
    mensaje que eventualmente emita (CU-32, aun pendiente) sea compatible.
    """

    LOCAL = "LOCAL"
    VISITANTE = "VISITANTE"
    ARBITRO = "ARBITRO"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass(frozen=True, slots=True)
class Deteccion:
    """Una deteccion trackeada en un cuadro, en coordenadas de pixel.

    `punto_apoyo` es el punto de apoyo del jugador, no el centro de la caja:
    la homografia de CU-26 proyecta el plano del suelo, y el centro desplaza
    la posicion varios metros cerca de los bordes (ver vision/README.md).
    """

    tid: int
    clase: Clase
    caja: tuple[float, float, float, float]  # x1, y1, x2, y2 en pixeles
    conf: float
    punto_apoyo: tuple[float, float]

    @staticmethod
    def desde_caja(
        tid: int, clase: Clase, caja: tuple[float, float, float, float], conf: float
    ) -> Deteccion:
        x1, y1, x2, y2 = caja
        punto_apoyo = ((x1 + x2) / 2, y2)
        return Deteccion(tid=tid, clase=clase, caja=caja, conf=conf, punto_apoyo=punto_apoyo)
