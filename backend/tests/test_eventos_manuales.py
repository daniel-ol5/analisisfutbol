"""T-066 · Eventos manuales del partido (CU-36, CU-37 y CU-38)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.deportivo.models import Jugador, Partido
from app.main import app
from app.partido.models import EventoManual, RelojPartido
from scripts.seed_dev import sembrar_deportivo_demo

BASE = "http://test"


@pytest.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _club_con_partido(cliente: AsyncClient, sufijo: str, *, en_curso: bool = True) -> dict:
    registro = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": f"Club eventos {sufijo}",
            "email": f"eventos_{sufijo}@test.com",
            "password": "password123",
        },
    )
    assert registro.status_code == 201, registro.text
    sesion = registro.json()
    club_id = sesion["usuario"]["club_id"]

    async with SessionLocal() as db:
        await sembrar_deportivo_demo(db, club_id)
        partido = await db.scalar(
            select(Partido).where(
                Partido.club_id == club_id,
                Partido.rival == "Club Rival Uno",
            )
        )
        jugadores = (
            await db.scalars(select(Jugador).where(Jugador.club_id == club_id))
        ).all()
        if en_curso:
            partido.estado = "EN_CURSO"
            partido.minuto_actual = 23
            await db.commit()

    return {
        "auth": _auth(sesion["access_token"]),
        "club_id": club_id,
        "partido_id": partido.id,
        "jugadores": {jugador.dorsal: jugador.id for jugador in jugadores},
    }


async def _auth_rol(
    cliente: AsyncClient, club: dict, rol: str, sufijo: str
) -> dict[str, str]:
    email = f"eventos_{rol.lower()}_{sufijo}@test.com"
    creado = await cliente.post(
        "/api/seguridad/usuarios",
        headers=club["auth"],
        json={"email": email, "password": "password123", "rol": rol},
    )
    assert creado.status_code == 201, creado.text
    login = await cliente.post(
        "/api/seguridad/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _url(club: dict) -> str:
    return f"/api/partido/{club['partido_id']}/eventos"


async def _registrar(
    cliente: AsyncClient, club: dict, tipo: str, jugador: int | None = 9, **extra
):
    payload = {
        "tipo": tipo,
        "equipo": "LOCAL",
        "jugador_id": club["jugadores"][jugador] if jugador is not None else None,
        **extra,
    }
    return await cliente.post(_url(club), headers=club["auth"], json=payload)


async def test_registrar_gol_actualiza_marcador_y_toma_minuto_del_partido(cliente):
    club = await _club_con_partido(cliente, "gol")

    respuesta = await _registrar(cliente, club, "GOL")

    assert respuesta.status_code == 201, respuesta.text
    evento = respuesta.json()
    assert evento["tipo"] == "GOL"
    assert evento["minuto"] == 23
    assert evento["origen"] == "MANUAL"
    assert evento["uuid"]
    async with SessionLocal() as db:
        partido = await db.get(Partido, club["partido_id"])
        assert (partido.goles_favor, partido.goles_contra) == (1, 0)


async def test_registrar_evento_toma_minuto_del_reloj_persistente(cliente):
    club = await _club_con_partido(cliente, "reloj")
    async with SessionLocal() as db:
        db.add(
            RelojPartido(
                club_id=club["club_id"],
                partido_id=club["partido_id"],
                parte=1,
                en_curso=False,
                acumulado_s=37 * 60,
            )
        )
        await db.commit()

    respuesta = await _registrar(cliente, club, "AMARILLA")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["minuto"] == 37


async def test_tarjetas_primera_amarilla_segunda_roja_y_roja_directa(cliente):
    club = await _club_con_partido(cliente, "tarjetas")

    primera = await _registrar(cliente, club, "AMARILLA")
    segunda = await _registrar(cliente, club, "AMARILLA")
    directa = await _registrar(cliente, club, "ROJA", jugador=10)

    assert primera.status_code == segunda.status_code == directa.status_code == 201
    assert primera.json()["convertida_en_roja"] is False
    assert segunda.json()["tipo"] == "AMARILLA"
    assert segunda.json()["convertida_en_roja"] is True
    assert directa.json()["tipo"] == "ROJA"
    assert directa.json()["convertida_en_roja"] is False


async def test_sustitucion_exige_dos_jugadores_alineados_y_distintos(cliente):
    club = await _club_con_partido(cliente, "cambio")
    sale = club["jugadores"][9]
    entra = club["jugadores"][19]

    valida = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={
            "tipo": "SUSTITUCION",
            "equipo": "LOCAL",
            "jugador_id": sale,
            "jugador_entra_id": entra,
        },
    )
    sin_entrante = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={"tipo": "SUSTITUCION", "equipo": "LOCAL", "jugador_id": sale},
    )
    repetido = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={
            "tipo": "SUSTITUCION",
            "equipo": "LOCAL",
            "jugador_id": sale,
            "jugador_entra_id": sale,
        },
    )

    assert valida.status_code == 201, valida.text
    assert valida.json()["jugador_entra_id"] == entra
    assert sin_entrante.status_code == 422
    assert repetido.status_code == 422


async def test_rechaza_jugador_ajeno_y_partido_que_no_esta_en_curso(cliente):
    club = await _club_con_partido(cliente, "valida")
    otro = await _club_con_partido(cliente, "ajeno")

    jugador_ajeno = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={
            "tipo": "GOL",
            "equipo": "LOCAL",
            "jugador_id": otro["jugadores"][9],
        },
    )
    async with SessionLocal() as db:
        partido = await db.get(Partido, club["partido_id"])
        partido.estado = "FINALIZADO"
        await db.commit()
    finalizado = await _registrar(cliente, club, "GOL")

    assert jugador_ajeno.status_code == 422
    assert finalizado.status_code == 409


async def test_evento_del_rival_sin_plantel_actualiza_goles_contra(cliente):
    club = await _club_con_partido(cliente, "rival")

    respuesta = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={"tipo": "GOL", "equipo": "VISITANTE", "minuto": 31},
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["jugador_id"] is None
    async with SessionLocal() as db:
        partido = await db.get(Partido, club["partido_id"])
        assert (partido.goles_favor, partido.goles_contra) == (0, 1)


async def test_uuid_hace_idempotente_el_registro_y_rechaza_otro_contenido(cliente):
    club = await _club_con_partido(cliente, "uuid")
    identificador = str(uuid4())
    payload = {
        "uuid": identificador,
        "tipo": "GOL",
        "equipo": "LOCAL",
        "jugador_id": club["jugadores"][9],
        "minuto": 15,
    }

    primera = await cliente.post(_url(club), headers=club["auth"], json=payload)
    repetida = await cliente.post(_url(club), headers=club["auth"], json=payload)
    conflicto = await cliente.post(
        _url(club),
        headers=club["auth"],
        json={**payload, "tipo": "ROJA"},
    )

    assert primera.status_code == repetida.status_code == 201
    assert primera.json()["id"] == repetida.json()["id"]
    assert conflicto.status_code == 409
    async with SessionLocal() as db:
        cantidad = await db.scalar(select(func.count()).select_from(EventoManual))
        partido = await db.get(Partido, club["partido_id"])
        assert cantidad == 1
        assert partido.goles_favor == 1


async def test_deshacer_ultimo_evento_dentro_de_60_segundos_revierte_gol(cliente):
    club = await _club_con_partido(cliente, "deshacer")
    creado = await _registrar(cliente, club, "GOL")
    evento_id = creado.json()["id"]

    borrado = await cliente.delete(
        f"/api/partido/eventos/{evento_id}", headers=club["auth"]
    )
    listado = await cliente.get(_url(club), headers=club["auth"])

    assert borrado.status_code == 204, borrado.text
    assert listado.status_code == 200
    assert listado.json() == []
    async with SessionLocal() as db:
        partido = await db.get(Partido, club["partido_id"])
        evento = await db.get(EventoManual, evento_id)
        assert partido.goles_favor == 0
        assert evento.anulado_en is not None


async def test_deshacer_rechaza_evento_vencido_y_un_evento_que_no_es_el_ultimo(cliente):
    club = await _club_con_partido(cliente, "plazo")
    primero = await _registrar(cliente, club, "AMARILLA")
    segundo = await _registrar(cliente, club, "ROJA", jugador=10)

    no_ultimo = await cliente.delete(
        f"/api/partido/eventos/{primero.json()['id']}", headers=club["auth"]
    )
    async with SessionLocal() as db:
        evento = await db.get(EventoManual, segundo.json()["id"])
        evento.creado_en = datetime.now(UTC) - timedelta(seconds=61)
        await db.commit()
    vencido = await cliente.delete(
        f"/api/partido/eventos/{segundo.json()['id']}", headers=club["auth"]
    )

    assert no_ultimo.status_code == 409
    assert vencido.status_code == 409


async def test_aislamiento_entre_clubes_y_permisos(cliente):
    club = await _club_con_partido(cliente, "permisos")
    otro = await _club_con_partido(cliente, "oculto")
    asistente = await _auth_rol(cliente, club, "ASISTENTE", "permitido")
    analista = await _auth_rol(cliente, club, "ANALISTA", "rechazado")
    payload = {
        "tipo": "AMARILLA",
        "equipo": "LOCAL",
        "jugador_id": club["jugadores"][9],
    }

    permitido = await cliente.post(_url(club), headers=asistente, json=payload)
    rechazado = await cliente.post(_url(club), headers=analista, json=payload)
    oculto = await cliente.get(_url(club), headers=otro["auth"])

    assert permitido.status_code == 201, permitido.text
    assert rechazado.status_code == 403
    assert oculto.status_code == 404
