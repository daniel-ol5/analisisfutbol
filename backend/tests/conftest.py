"""Configuración de las pruebas.

Usa una base de datos separada de la de desarrollo y la recrea antes de cada
prueba, de modo que ninguna dependa del estado que dejó la anterior.
"""

import os

# Debe definirse ANTES de importar la aplicación: `settings` se instancia al
# importarse el módulo de configuración.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest  # noqa: E402

from app.core.database import Base, engine  # noqa: E402


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
