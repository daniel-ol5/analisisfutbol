"""Motor, sesión y clase base de SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todos los modelos. Alembic la usa para detectar las tablas."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    async with SessionLocal() as session:
        yield session


async def crear_tablas() -> None:
    """Crea las tablas al arrancar.

    Atajo para el Sprint 1. A partir del Sprint 2 el esquema se gestiona
    con migraciones de Alembic y esta función se elimina.
    """
    # Importar los módulos de modelos registra las tablas en Base.metadata
    from app import analisis, asistencia, deportivo, partido, seguridad, vision  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
