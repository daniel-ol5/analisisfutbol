"""Motor, sesión y clase base de SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Sin pool (DB_NULL_POOL=true) cada sesión abre su conexión en el event loop que la usa.
# Las pruebas lo necesitan: cada una corre en su propio loop y asyncpg no permite reutilizar
# una conexión creada en otro. En producción se deja el pool normal.
_pool = {"poolclass": NullPool} if settings.db_null_pool else {}
engine = create_async_engine(settings.database_url, echo=False, future=True, **_pool)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todos los modelos. Alembic la usa para detectar las tablas."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    async with SessionLocal() as session:
        yield session
