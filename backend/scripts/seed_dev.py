"""Carga idempotente de datos ficticios para el entorno de desarrollo.

El script se ejecuta despues de Alembic en Docker Compose. Por seguridad no
permite sembrar datos cuando APP_ENV no es ``development``.
"""

import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.security import hashear
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


async def ejecutar() -> None:
    config = configuracion_desde_entorno()
    if config is None:
        print("Seed de desarrollo desactivado")
        return

    async with SessionLocal() as db:
        creado = await sembrar_datos_demo(db, config)
    estado = "creados" if creado else "ya existentes; sin cambios"
    print(f"Datos demo {estado} ({config.email})")


if __name__ == "__main__":
    asyncio.run(ejecutar())
