"""Partidos sembrados para las pruebas de los WebSockets (T-032, T-033).

Usan los modelos reales (`Partido` de T-047 y `Posicion`). Las tablas las
crea `conftest.py` antes de cada prueba; aquí solo se siembran filas.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.deportivo.models import Partido, Posicion
from app.deportivo.schemas import EstadoPartido

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

    SQLite no exige las claves foráneas (no se activa `PRAGMA foreign_keys`),
    así que no hace falta crear clubes ni equipos.
    """
    async with SesionesPrueba() as db:
        for partido_id, club_id in ((PARTIDO_A, CLUB_A), (PARTIDO_B, CLUB_B)):
            db.add(Partido(id=partido_id, club_id=club_id, equipo_id=1, rival="Rival",
                           fecha_hora=datetime.now(UTC), sede="Cancha", estado=estado.value))
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
