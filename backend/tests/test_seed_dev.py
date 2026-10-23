"""Pruebas de los datos iniciales exclusivos del entorno de desarrollo."""

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import verificar
from app.seguridad.models import Club, Usuario
from scripts.seed_dev import (
    ConfiguracionDemo,
    configuracion_desde_entorno,
    sembrar_datos_demo,
)


async def test_seed_es_idempotente():
    config = ConfiguracionDemo("admin@club-demo.example.com", "password-demo-seguro")

    async with SessionLocal() as db:
        assert await sembrar_datos_demo(db, config) is True
        assert await sembrar_datos_demo(db, config) is False

        clubes = await db.scalar(select(func.count()).select_from(Club))
        usuarios = await db.scalar(select(func.count()).select_from(Usuario))
        admin = await db.scalar(select(Usuario).where(Usuario.email == config.email))

    assert clubes == 1
    assert usuarios == 1
    assert admin is not None
    assert verificar(config.password, admin.password_hash)


def test_seed_desactivado_no_exige_credenciales(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    assert configuracion_desde_entorno() is None


def test_seed_se_rechaza_fuera_de_desarrollo(monkeypatch):
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="solo puede usarse"):
        configuracion_desde_entorno()
