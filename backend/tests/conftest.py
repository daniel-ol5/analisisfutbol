"""Configuración de las pruebas.

Las pruebas corren SOLO contra PostgreSQL 16 (el motor del proyecto): la URL
llega en `TEST_DATABASE_URL`. La base se vacía y se recrea antes de cada prueba,
de modo que ninguna dependa del estado que dejó la anterior, así que debe ser una
base exclusiva para pruebas, nunca la de desarrollo.

    docker compose --profile test up -d db_test
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:<clave>@localhost:55432/areatecnica_test pytest
"""

import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError(
        "Define TEST_DATABASE_URL con una base PostgreSQL 16 exclusiva para pruebas "
        "(postgresql+asyncpg://...). Las pruebas ya no usan SQLite."
    )

# Debe definirse ANTES de importar la aplicación: `settings` se instancia al
# importarse el módulo de configuración.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DB_NULL_POOL"] = "true"

import pytest

from app.core.database import Base, engine


@pytest.fixture(autouse=True)
async def base_limpia():
    # Importar los paquetes registra sus tablas en Base.metadata
    from app import (  # noqa: F401
        analisis,
        asistencia,
        deportivo,
        partido,
        seguridad,
        vision,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
