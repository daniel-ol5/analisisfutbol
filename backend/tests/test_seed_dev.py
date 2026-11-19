"""Pruebas de los datos iniciales exclusivos del entorno de desarrollo."""

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import verificar
from app.deportivo.models import (
    Alineacion,
    AlineacionJugador,
    Competicion,
    Equipo,
    Jugador,
    Partido,
)
from app.seguridad.models import Club, Usuario
from scripts.demo_sprint4 import (
    ErrorDemo,
    calibracion_sintetica,
    ordenar_candidatos,
    validar_destino_mutable,
)
from scripts.seed_dev import (
    ConfiguracionDemo,
    configuracion_desde_entorno,
    sembrar_datos_demo,
    sembrar_deportivo_demo,
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


async def test_escenario_deportivo_es_completo_reparable_e_idempotente():
    config = ConfiguracionDemo("admin@club-demo.example.com", "password-demo-seguro")

    async with SessionLocal() as db:
        await sembrar_datos_demo(db, config)
        admin = await db.scalar(select(Usuario).where(Usuario.email == config.email))
        assert await sembrar_deportivo_demo(db, admin.club_id) is True
        assert await sembrar_deportivo_demo(db, admin.club_id) is False

        cantidades = {
            "competiciones": await db.scalar(select(func.count()).select_from(Competicion)),
            "equipos": await db.scalar(select(func.count()).select_from(Equipo)),
            "jugadores": await db.scalar(select(func.count()).select_from(Jugador)),
            "partidos": await db.scalar(select(func.count()).select_from(Partido)),
            "alineaciones": await db.scalar(select(func.count()).select_from(Alineacion)),
            "alineados": await db.scalar(select(func.count()).select_from(AlineacionJugador)),
        }
        sin_competicion = await db.scalar(
            select(func.count()).select_from(Partido).where(Partido.competicion_id.is_(None))
        )

    assert cantidades == {
        "competiciones": 1,
        "equipos": 1,
        "jugadores": 18,
        "partidos": 3,
        "alineaciones": 1,
        "alineados": 18,
    }
    assert sin_competicion == 0


def test_calibracion_sintetica_tiene_ocho_pares_y_escala_conocida():
    calibracion = calibracion_sintetica()

    assert len(calibracion["puntos_imagen"]) == 8
    assert len(calibracion["puntos_cancha"]) == 8
    assert calibracion["puntos_imagen"][2] == {"x": 1050, "y": 0}
    assert calibracion["puntos_cancha"][2] == {"x": 105.0, "y": 0.0}
    assert calibracion["referencia"]["fuente_id"] == "demo-sprint4-simulada"


def test_preparador_rechaza_escritura_remota_por_defecto():
    validar_destino_mutable("http://127.0.0.1:8000/api", permitir_host_remoto=False)

    with pytest.raises(ErrorDemo, match="host remoto"):
        validar_destino_mutable("https://api.example.com/api", permitir_host_remoto=False)

    validar_destino_mutable("https://api.example.com/api", permitir_host_remoto=True)


def test_partido_demo_se_prioriza_dentro_del_mismo_estado():
    partidos = [
        {"id": 3, "rival": "Otro", "estado": "PROGRAMADO", "fecha_hora": "2026-11-20"},
        {"id": 1, "rival": "Club Rival Uno", "estado": "PROGRAMADO", "fecha_hora": "2026-11-22"},
        {"id": 2, "rival": "Final", "estado": "FINALIZADO", "fecha_hora": "2026-11-10"},
    ]

    assert [p["id"] for p in ordenar_candidatos(partidos)] == [1, 3]
    assert [p["id"] for p in ordenar_candidatos(partidos, partido_id=3)] == [3]
