"""Seed manual de clubes de prueba con plantel completo  —  FC Barcelona y Real Madrid.

No se ejecuta como parte de Docker Compose ni de los tests: es para levantar
datos realistas a mano durante pruebas manuales de CU-09 … CU-12.

Uso:
    python -m scripts.seed_clubes_prueba

Idempotente: si el usuario admin de un club ya existe, no lo vuelve a crear.
"""

import asyncio
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.security import hashear
from app.deportivo.models import Equipo, Jugador
from app.seguridad.models import Club, Rol, Usuario


@dataclass(frozen=True)
class JugadorDemo:
    nombre: str
    apellido: str
    dorsal: int
    posicion: str
    pie_habil: str
    altura_cm: int
    peso_kg: int
    fecha_nacimiento: date


@dataclass(frozen=True)
class ClubDemo:
    nombre_club: str
    ciudad: str
    email_admin: str
    password_admin: str
    nombre_admin: str
    apellido_admin: str
    nombre_equipo: str
    color_local: str
    color_visitante: str
    color_arquero: str
    jugadores: list[JugadorDemo]


BARCELONA = ClubDemo(
    nombre_club="FC Barcelona",
    ciudad="Barcelona",
    email_admin="admin@barcelona-demo.example.com",
    password_admin="Barcelona-Demo-2026",
    nombre_admin="Hansi",
    apellido_admin="Flick",
    nombre_equipo="Primer Equipo",
    color_local="#A50044",
    color_visitante="#FFFFFF",
    color_arquero="#04E0B5",
    jugadores=[
        JugadorDemo("Marc-André", "ter Stegen", 1, "ARQ", "IZQ", 187, 85, date(1992, 4, 30)),
        JugadorDemo("Iñaki", "Peña", 13, "ARQ", "DER", 190, 83, date(1999, 2, 2)),
        JugadorDemo("Jules", "Koundé", 23, "DEF", "DER", 178, 72, date(1998, 11, 12)),
        JugadorDemo("Ronald", "Araújo", 4, "DEF", "DER", 188, 79, date(2001, 3, 7)),
        JugadorDemo("Pau", "Cubarsí", 2, "DEF", "DER", 181, 71, date(2007, 1, 22)),
        JugadorDemo("Alejandro", "Balde", 3, "DEF", "IZQ", 175, 68, date(2003, 10, 18)),
        JugadorDemo("Andreas", "Christensen", 15, "DEF", "DER", 187, 82, date(1996, 4, 10)),
        JugadorDemo("Íñigo", "Martínez", 24, "DEF", "IZQ", 181, 76, date(1991, 5, 17)),
        JugadorDemo("Frenkie", "de Jong", 21, "MED", "DER", 180, 74, date(1997, 5, 12)),
        JugadorDemo("Pedri", "González", 8, "MED", "DER", 174, 60, date(2002, 11, 25)),
        JugadorDemo("Pablo", "Gavi", 6, "MED", "DER", 173, 68, date(2004, 8, 5)),
        JugadorDemo("Marc", "Casadó", 17, "MED", "DER", 180, 72, date(2003, 9, 14)),
        JugadorDemo("Dani", "Olmo", 20, "MED", "DER", 179, 65, date(1998, 5, 7)),
        JugadorDemo("Fermín", "López", 16, "MED", "DER", 174, 68, date(2003, 5, 11)),
        JugadorDemo("Marc", "Bernal", 36, "MED", "DER", 180, 70, date(2006, 1, 2)),
        JugadorDemo("Robert", "Lewandowski", 9, "DEL", "DER", 185, 81, date(1988, 8, 21)),
        JugadorDemo("Raphinha", "Dias", 11, "DEL", "DER", 176, 68, date(1996, 12, 14)),
        JugadorDemo("Lamine", "Yamal", 19, "DEL", "DER", 180, 69, date(2007, 7, 13)),
        JugadorDemo("Ferran", "Torres", 7, "DEL", "DER", 184, 73, date(2000, 2, 29)),
        JugadorDemo("Pau", "Víctor", 22, "DEL", "DER", 182, 76, date(2001, 5, 22)),
    ],
)

REAL_MADRID = ClubDemo(
    nombre_club="Real Madrid CF",
    ciudad="Madrid",
    email_admin="admin@realmadrid-demo.example.com",
    password_admin="RealMadrid-Demo-2026",
    nombre_admin="Carlo",
    apellido_admin="Ancelotti",
    nombre_equipo="Primer Equipo",
    color_local="#FFFFFF",
    color_visitante="#5B2D8E",
    color_arquero="#111111",
    jugadores=[
        JugadorDemo("Thibaut", "Courtois", 1, "ARQ", "IZQ", 199, 96, date(1992, 5, 11)),
        JugadorDemo("Andriy", "Lunin", 13, "ARQ", "IZQ", 192, 86, date(1999, 2, 11)),
        JugadorDemo("Dani", "Carvajal", 2, "DEF", "DER", 173, 73, date(1992, 1, 11)),
        JugadorDemo("Éder", "Militão", 3, "DEF", "DER", 186, 79, date(1998, 1, 18)),
        JugadorDemo("David", "Alaba", 4, "DEF", "IZQ", 180, 77, date(1992, 6, 24)),
        JugadorDemo("Ferland", "Mendy", 23, "DEF", "IZQ", 180, 78, date(1995, 6, 8)),
        JugadorDemo("Antonio", "Rüdiger", 22, "DEF", "DER", 190, 85, date(1993, 3, 3)),
        JugadorDemo("Raúl", "Asencio", 34, "DEF", "DER", 184, 78, date(2003, 5, 13)),
        JugadorDemo("Fran", "García", 20, "DEF", "IZQ", 176, 68, date(1999, 8, 14)),
        JugadorDemo("Jude", "Bellingham", 5, "MED", "DER", 186, 75, date(2003, 6, 29)),
        JugadorDemo("Federico", "Valverde", 15, "MED", "DER", 182, 78, date(1998, 7, 22)),
        JugadorDemo("Eduardo", "Camavinga", 6, "MED", "IZQ", 182, 73, date(2002, 11, 10)),
        JugadorDemo("Aurélien", "Tchouaméni", 18, "MED", "DER", 187, 80, date(2000, 1, 27)),
        JugadorDemo("Luka", "Modrić", 10, "MED", "DER", 172, 66, date(1985, 9, 9)),
        JugadorDemo("Arda", "Güler", 24, "MED", "IZQ", 173, 68, date(2005, 2, 25)),
        JugadorDemo("Vinícius", "Júnior", 7, "DEL", "DER", 176, 73, date(2000, 7, 12)),
        JugadorDemo("Kylian", "Mbappé", 9, "DEL", "DER", 178, 73, date(1998, 12, 20)),
        JugadorDemo("Rodrygo", "Goes", 11, "DEL", "DER", 174, 64, date(2001, 1, 9)),
        JugadorDemo("Brahim", "Díaz", 21, "DEL", "DER", 171, 65, date(1999, 8, 3)),
        JugadorDemo("Endrick", "Felipe", 16, "DEL", "DER", 176, 73, date(2006, 7, 21)),
    ],
)

CLUBES_DEMO = [BARCELONA, REAL_MADRID]


async def sembrar_club(db: AsyncSession, datos: ClubDemo) -> bool:
    """Crea club, usuario admin, equipo y plantel si el admin no existe aún."""
    existente = await db.execute(select(Usuario).where(Usuario.email == datos.email_admin))
    if existente.scalar_one_or_none() is not None:
        return False

    club = Club(nombre=datos.nombre_club, ciudad=datos.ciudad)
    db.add(club)
    await db.flush()

    db.add(
        Usuario(
            club_id=club.id,
            email=datos.email_admin,
            password_hash=hashear(datos.password_admin),
            nombre=datos.nombre_admin,
            apellido=datos.apellido_admin,
            rol=Rol.ADMIN,
        )
    )

    equipo = Equipo(
        club_id=club.id,
        nombre=datos.nombre_equipo,
        categoria="Primera",
        temporada="2025/2026",
        color_local=datos.color_local,
        color_visitante=datos.color_visitante,
        color_arquero=datos.color_arquero,
    )
    db.add(equipo)
    await db.flush()

    for j in datos.jugadores:
        db.add(
            Jugador(
                club_id=club.id,
                equipo_id=equipo.id,
                nombre=j.nombre,
                apellido=j.apellido,
                dorsal=j.dorsal,
                posicion=j.posicion,
                pie_habil=j.pie_habil,
                altura_cm=j.altura_cm,
                peso_kg=j.peso_kg,
                fecha_nacimiento=j.fecha_nacimiento,
            )
        )

    await db.commit()
    return True


async def ejecutar() -> None:
    async with SessionLocal() as db:
        for datos in CLUBES_DEMO:
            creado = await sembrar_club(db, datos)
            estado = "creado" if creado else "ya existente; sin cambios"
            print(f"{datos.nombre_club}: {estado} ({datos.email_admin} / {datos.password_admin})")


if __name__ == "__main__":
    asyncio.run(ejecutar())
