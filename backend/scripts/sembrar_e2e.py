"""Datos para las pruebas extremo a extremo (T-093).

Crea, en una base EXCLUSIVA de pruebas extremo a extremo (vacía y con las
migraciones aplicadas):

- un club con un usuario ADMIN,
- un equipo con un jugador,
- tres partidos PROGRAMADOS, uno por flujo:
    1. «Rival Calibración»: sin calibración (el flujo la crea desde la web).
    2. «Rival En Vivo»: calibración válida y alineación (para registrar una roja).
    3. «Rival Video»: calibración válida, sin fuente fija (sirve para cualquier video).

y un clip de video corto y legible por OpenCV, para el flujo 3.

Escribe en `--salida` un JSON con los ids que usan las pruebas de Playwright.

    E2E_SEMBRAR=1 DATABASE_URL=postgresql+asyncpg://.../areatecnica_e2e \\
        python scripts/sembrar_e2e.py --salida datos.json --video clip.mp4

Por seguridad se niega a correr si no está E2E_SEMBRAR=1, si el nombre de la base
no contiene «e2e» o si el club de pruebas ya existe.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hashear
from app.deportivo.models import (
    Alineacion,
    AlineacionJugador,
    Equipo,
    Jugador,
    Partido,
)
from app.seguridad.models import Club, Rol, Usuario
from app.vision.models import Calibracion

NOMBRE_CLUB = "Club E2E"
EMAIL = os.environ.get("E2E_EMAIL", "admin.e2e@clubprueba.com")
# Cuenta de una base desechable de pruebas: no es una credencial real.
PASSWORD = os.environ.get("E2E_PASSWORD", "solo-pruebas-e2e-2026")

# Ocho referencias reales de una cancha de 105 x 68 y su imagen (homografía exacta).
_CANCHA = [(0, 0), (105, 0), (105, 68), (0, 68), (52.5, 0), (52.5, 68), (16.5, 13.84), (88.5, 54.16)]


def _calibracion_valida(club_id: int, partido_id: int) -> Calibracion:
    escala = 10.0
    return Calibracion(
        club_id=club_id, partido_id=partido_id, largo_m=105.0, ancho_m=68.0, modo="MANUAL",
        referencia=None,
        puntos_imagen=[{"x": x * escala + 40, "y": y * escala + 30} for x, y in _CANCHA],
        puntos_cancha=[{"x": x, "y": y} for x, y in _CANCHA],
        matriz_h=[[1 / escala, 0, -40 / escala], [0, 1 / escala, -30 / escala], [0, 0, 1]],
        error_medio_m=0.05, error_max_m=0.1, valida=True,
    )


def escribir_clip(ruta: Path, segundos: float = 3.0, fps: int = 10) -> None:
    """Un video MP4 mínimo (verde con una pelota que se mueve), legible por OpenCV."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    if not escritor.isOpened():
        raise RuntimeError(f"OpenCV no pudo crear {ruta}")
    for i in range(int(segundos * fps)):
        cuadro = np.full((240, 320, 3), (40, 140, 40), dtype=np.uint8)
        cv2.circle(cuadro, (20 + i * 9, 120), 6, (255, 255, 255), -1)
        escritor.write(cuadro)
    escritor.release()


async def sembrar() -> dict:
    ahora = datetime.now(UTC)
    async with SessionLocal() as db:
        if (await db.execute(select(Club).where(Club.nombre == NOMBRE_CLUB))).first():
            raise SystemExit("La base ya tiene los datos de E2E: usa una base nueva.")

        club = Club(nombre=NOMBRE_CLUB, ciudad="Pruebas")
        db.add(club)
        await db.flush()
        db.add(Usuario(club_id=club.id, email=EMAIL, password_hash=hashear(PASSWORD),
                       nombre="Admin", apellido="E2E", rol=Rol.ADMIN))
        equipo = Equipo(club_id=club.id, nombre="Equipo E2E", categoria="Primera",
                        temporada="2026")
        db.add(equipo)
        await db.flush()
        jugador = Jugador(club_id=club.id, equipo_id=equipo.id, nombre="Lucas",
                          apellido="Defensor", dorsal=4, posicion="DEF", altura_cm=180)
        db.add(jugador)

        partidos: dict[str, Partido] = {}
        for clave, rival, dias in (("calibracion", "Rival Calibración", 1),
                                   ("vivo", "Rival En Vivo", 2), ("video", "Rival Video", 3)):
            partidos[clave] = Partido(
                club_id=club.id, equipo_id=equipo.id, rival=rival, es_local=True,
                fecha_hora=ahora + timedelta(days=dias), sede="Cancha E2E",
                estado="PROGRAMADO", ataca_hacia="DER")
            db.add(partidos[clave])
        await db.flush()

        for clave in ("vivo", "video"):
            db.add(_calibracion_valida(club.id, partidos[clave].id))
        alineacion = Alineacion(club_id=club.id, partido_id=partidos["vivo"].id)
        db.add(alineacion)
        await db.flush()
        db.add(AlineacionJugador(alineacion_id=alineacion.id, jugador_id=jugador.id,
                                 es_titular=True))
        await db.commit()
        return {
            "email": EMAIL, "password": PASSWORD, "club_id": club.id,
            "jugador_id": jugador.id,
            "partidos": {clave: p.id for clave, p in partidos.items()},
            "rivales": {clave: p.rival for clave, p in partidos.items()},
        }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--salida", type=Path, required=True, help="JSON con los ids sembrados")
    p.add_argument("--video", type=Path, required=True, help="Dónde escribir el clip MP4")
    args = p.parse_args()

    if os.environ.get("E2E_SEMBRAR") != "1":
        raise SystemExit("Define E2E_SEMBRAR=1: este script es solo para la base de E2E.")
    base = settings.database_url.rsplit("/", 1)[-1]
    if "e2e" not in base:
        raise SystemExit(f"La base «{base}» no parece de E2E (su nombre debe contener «e2e»).")

    datos = asyncio.run(sembrar())
    escribir_clip(args.video)
    datos["video"] = str(args.video.resolve())
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"E2E sembrado: partidos {datos['partidos']}, datos en {args.salida}")


if __name__ == "__main__":
    main()
