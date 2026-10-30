"""Carga idempotente de datos ficticios para el entorno de desarrollo.

El script se ejecuta despues de Alembic en Docker Compose. Por seguridad no
permite sembrar datos cuando APP_ENV no es ``development``.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.security import hashear
from app.deportivo.models import Alineacion, AlineacionJugador, Equipo, Jugador, Partido
from app.seguridad.models import Club, Rol, Usuario

VALORES_VERDADEROS = {"1", "true", "yes", "si", "sí"}


@dataclass(frozen=True)
class ConfiguracionDemo:
    email: str
    password: str


def configuracion_desde_entorno() -> ConfiguracionDemo | None:
    """Devuelve la configuracion del seed o ``None`` cuando esta desactivado."""
    habilitado = os.getenv("SEED_DEMO_DATA", "false").lower() in VALORES_VERDADEROS
    if not habilitado:
        return None

    entorno = os.getenv("APP_ENV", "").lower()
    if entorno != "development":
        raise RuntimeError("SEED_DEMO_DATA solo puede usarse con APP_ENV=development")

    email = os.getenv("DEMO_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("DEMO_ADMIN_PASSWORD", "")
    if not email or len(password) < 12:
        raise RuntimeError(
            "DEMO_ADMIN_EMAIL y DEMO_ADMIN_PASSWORD (minimo 12 caracteres) son obligatorios"
        )
    return ConfiguracionDemo(email=email, password=password)


async def sembrar_datos_demo(db: AsyncSession, config: ConfiguracionDemo) -> bool:
    """Crea un club ficticio una sola vez; devuelve si realizo la insercion."""
    consulta = await db.execute(select(Usuario).where(Usuario.email == config.email))
    if consulta.scalar_one_or_none() is not None:
        return False

    club = Club(nombre="Club Demo Area Tecnica", ciudad="Ciudad de prueba")
    db.add(club)
    await db.flush()
    db.add(
        Usuario(
            club_id=club.id,
            email=config.email,
            password_hash=hashear(config.password),
            nombre="Administracion",
            apellido="Demo",
            rol=Rol.ADMIN,
        )
    )
    await db.commit()
    return True


# ---------- Gestión deportiva (T-048) ----------
#
# Mientras CU-11 (jugadores) y CU-14 (partidos) no tengan endpoints, esto es lo
# que permite probar la alineación (CU-17) a mano en web y móvil.

EQUIPO_DEMO = "Primera Demo"

# (nombre, apellido, dorsal, posicion): 2 arqueros, 6 DEF, 6 MED, 4 DEL.
PLANTEL_DEMO = [
    ("Tomás", "Arandia", 1, "ARQ"), ("Iván", "Quiroga", 12, "ARQ"),
    ("Mateo", "Rivera", 2, "DEF"), ("Bruno", "Salinas", 4, "DEF"),
    ("Lucas", "Méndez", 3, "DEF"), ("Nicolás", "Ortega", 6, "DEF"),
    ("Simón", "Paredes", 13, "DEF"), ("Hugo", "Villalba", 14, "DEF"),
    ("Joaquín", "Rojas", 5, "MED"), ("Emilio", "Navarro", 8, "MED"),
    ("Gael", "Fuentes", 10, "MED"), ("Andrés", "Coronado", 16, "MED"),
    ("Felipe", "Montaño", 15, "MED"), ("Ricardo", "Peña", 18, "MED"),
    ("Santiago", "Ibáñez", 9, "DEL"), ("Martín", "Aguilera", 7, "DEL"),
    ("Daniel", "Cuéllar", 11, "DEL"), ("Pablo", "Herrera", 19, "DEL"),
]

# Alineación de ejemplo 4-3-3 para el primer partido: dorsal -> (pos_x, pos_y).
# pos_x: 0 arco propio, 100 arco rival. pos_y: 0 banda izquierda, 100 derecha.
TITULARES_DEMO = {
    1: (5, 50),
    2: (25, 85), 4: (22, 62), 3: (22, 38), 6: (25, 15),
    5: (45, 50), 8: (52, 72), 10: (52, 28),
    7: (75, 85), 9: (80, 50), 11: (75, 15),
}
CAPITAN_DEMO = 9


async def sembrar_deportivo_demo(db: AsyncSession, club_id: int) -> bool:
    """Crea equipo, plantel, partidos y una alineación de ejemplo, una sola vez."""
    existe = await db.scalar(
        select(Equipo).where(Equipo.club_id == club_id, Equipo.nombre == EQUIPO_DEMO)
    )
    if existe is not None:
        return False

    equipo = Equipo(club_id=club_id, nombre=EQUIPO_DEMO, categoria="Primera",
                    temporada="2026")
    db.add(equipo)
    await db.flush()

    jugadores = {}
    for nombre, apellido, dorsal, posicion in PLANTEL_DEMO:
        jugador = Jugador(
            club_id=club_id, equipo_id=equipo.id, nombre=nombre, apellido=apellido,
            dorsal=dorsal, posicion=posicion,
            altura_cm=188 if posicion == "ARQ" else 176,
        )
        db.add(jugador)
        jugadores[dorsal] = jugador

    ahora = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    proximo = Partido(club_id=club_id, equipo_id=equipo.id, rival="Club Rival Uno",
                      fecha_hora=ahora + timedelta(days=3), sede="Estadio Demo")
    sin_alineacion = Partido(club_id=club_id, equipo_id=equipo.id,
                             rival="Club Rival Dos", es_local=False,
                             fecha_hora=ahora + timedelta(days=10), sede="Cancha visitante")
    # Terminado: sirve para comprobar que su alineación ya no se puede cambiar.
    jugado = Partido(club_id=club_id, equipo_id=equipo.id, rival="Club Rival Tres",
                     fecha_hora=ahora - timedelta(days=7), sede="Estadio Demo",
                     estado="FINALIZADO", goles_favor=2, goles_contra=1)
    db.add_all([proximo, sin_alineacion, jugado])
    await db.flush()

    db.add(Alineacion(
        club_id=club_id,
        partido_id=proximo.id,
        formacion="4-3-3",
        jugadores_alineados=[
            AlineacionJugador(
                jugador_id=jugador.id,
                es_titular=dorsal in TITULARES_DEMO,
                es_capitan=dorsal == CAPITAN_DEMO,
                pos_x=TITULARES_DEMO.get(dorsal, (0, 0))[0],
                pos_y=TITULARES_DEMO.get(dorsal, (0, 0))[1],
            )
            for dorsal, jugador in jugadores.items()
        ],
    ))
    await db.commit()
    return True


async def ejecutar() -> None:
    config = configuracion_desde_entorno()
    if config is None:
        print("Seed de desarrollo desactivado")
        return

    async with SessionLocal() as db:
        creado = await sembrar_datos_demo(db, config)
        admin = await db.scalar(select(Usuario).where(Usuario.email == config.email))
        deportivo = await sembrar_deportivo_demo(db, admin.club_id)
    estado = "creados" if creado else "ya existentes; sin cambios"
    print(f"Datos demo {estado} ({config.email})")
    if deportivo:
        print(f"Equipo «{EQUIPO_DEMO}» con plantel, partidos y alineación de ejemplo creados")


if __name__ == "__main__":
    asyncio.run(ejecutar())
