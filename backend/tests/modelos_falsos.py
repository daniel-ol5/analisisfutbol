"""Modelos falsos para probar los WebSockets mientras no existan las tablas
`partido` (T-047) y `posicion`.

Viven en una metadata propia de las pruebas: no se registran en
`Base.metadata`, así que no afectan a Alembic ni al contrato. Las columnas
siguen docs/diagramas/modelo-datos.puml (más `club_id` en partido, como se
acordó para T-047).
"""

from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Motor propio, sin pool. El TestClient corre la app en otro hilo con su propio
# event loop; con el pool de la app, una conexión abierta en el loop de pytest
# se reutilizaba en el del TestClient y el cierre del portal quedaba colgado
# de forma intermitente. Con NullPool cada sesión abre su conexión en el loop
# que la usa. Los repositorios lo reciben por su parámetro `sesiones`.
motor = create_async_engine(settings.database_url, poolclass=NullPool)
SesionesPrueba = async_sessionmaker(motor, expire_on_commit=False)


class BaseFalsa(DeclarativeBase):
    pass


class PartidoFalso(BaseFalsa):
    __tablename__ = "partido_falso"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int]


class PosicionFalsa(BaseFalsa):
    __tablename__ = "posicion_falsa"

    # BigInteger en el modelo real; en SQLite solo INTEGER autoincrementa
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True)
    partido_id: Mapped[int]
    t: Mapped[float]
    track_id: Mapped[int]
    x_m: Mapped[float]
    y_m: Mapped[float]
    confianza: Mapped[float | None]


CLUB_A, CLUB_B = 1, 2
PARTIDO_A = 10      # del club A
PARTIDO_B = 20      # del club B
INEXISTENTE = 999


async def crear_tablas_falsas() -> None:
    async with motor.begin() as conn:
        await conn.run_sync(BaseFalsa.metadata.drop_all)
        await conn.run_sync(BaseFalsa.metadata.create_all)
    async with SesionesPrueba() as db:
        db.add_all([PartidoFalso(id=PARTIDO_A, club_id=CLUB_A),
                    PartidoFalso(id=PARTIDO_B, club_id=CLUB_B)])
        await db.commit()


async def borrar_tablas_falsas() -> None:
    async with motor.begin() as conn:
        await conn.run_sync(BaseFalsa.metadata.drop_all)
