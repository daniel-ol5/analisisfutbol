"""Partidos sembrados para las pruebas de los WebSockets (T-032, T-033).

Usan los modelos reales (`Partido` de T-047 y `Posicion`). Las tablas las
crea `conftest.py` antes de cada prueba; aquí solo se siembran filas.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.deportivo.models import Equipo, Partido, Posicion
from app.deportivo.schemas import EstadoPartido
from app.seguridad.models import Club, Usuario

# Motor propio, sin pool. El TestClient corre la app en otro hilo con su propio
# event loop; con el pool de la app, una conexión abierta en el loop de pytest
# se reutilizaba en el del TestClient y el cierre del portal quedaba colgado
# de forma intermitente. Con NullPool cada sesión abre su conexión en el loop
# que la usa. Los repositorios lo reciben por su parámetro `sesiones`.
motor = create_async_engine(settings.database_url, poolclass=NullPool)
SesionesPrueba = async_sessionmaker(motor, expire_on_commit=False)

CLUB_A, CLUB_B = 1, 2
PARTIDO_A = 10      # del club A
PARTIDO_B = 20      # del club B
INEXISTENTE = 999


async def sembrar_partidos(estado: EstadoPartido = EstadoPartido.EN_CURSO) -> None:
    """PARTIDO_A del club A y PARTIDO_B del club B, ambos en `estado`.

    PostgreSQL exige las claves foráneas: se crean también el club y un equipo de cada
    uno (el equipo `n` es del club `n`). Como los ids van explícitos, se avanza la
    secuencia para que los que asigne la base después no choquen con ellos.
    """
    async with SesionesPrueba() as db:
        for club_id in (CLUB_A, CLUB_B):
            db.add(Club(id=club_id, nombre=f"Club {club_id}"))
        await db.flush()
        for club_id in (CLUB_A, CLUB_B):
            db.add(Equipo(id=club_id, club_id=club_id, nombre=f"Equipo {club_id}"))
            # El usuario `n` es del club `n` (los tokens de prueba usan esos ids).
            db.add(Usuario(id=club_id, club_id=club_id, email=f"usuario{club_id}@club.example.com",
                           password_hash="x"))
        await db.flush()
        for partido_id, club_id in ((PARTIDO_A, CLUB_A), (PARTIDO_B, CLUB_B)):
            db.add(Partido(id=partido_id, club_id=club_id, equipo_id=club_id, rival="Rival",
                           fecha_hora=datetime.now(UTC), sede="Cancha", estado=estado.value))
        await db.commit()
        for tabla in ("club", "equipo", "partido", "usuario"):
            await db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                f"(SELECT max(id) FROM {tabla}))"))
        await db.commit()


async def cambiar_estado(partido_id: int, estado: EstadoPartido) -> None:
    async with SesionesPrueba() as db:
        partido = await db.get(Partido, partido_id)
        assert partido is not None
        partido.estado = estado.value
        await db.commit()


async def contar_posiciones(partido_id: int | None = None) -> int:
    consulta = select(func.count()).select_from(Posicion)
    if partido_id is not None:
        consulta = consulta.where(Posicion.partido_id == partido_id)
    async with SesionesPrueba() as db:
        return (await db.execute(consulta)).scalar_one()
