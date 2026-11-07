"""Pruebas de Alineación y formación  —  CU-17 / HU-14 (T-048).

Mientras CU-11 (jugadores) y CU-14 (partidos) no tengan endpoints, el plantel
y los partidos se cargan con el mismo seed de desarrollo que usa el equipo.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.deportivo.models import Alineacion, Jugador, Partido
from app.main import app
from scripts.seed_dev import CAPITAN_DEMO, TITULARES_DEMO, sembrar_deportivo_demo

BASE = "http://test"


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _club_con_plantel(cliente, sufijo: str) -> dict:
    """Club registrado por la API, con el equipo, plantel y partidos del seed."""
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}",
        "email": f"admin{sufijo}@test.com",
        "password": "password123",
    })
    assert r.status_code == 201, r.text
    sesion = r.json()
    club_id = sesion["usuario"]["club_id"]

    async with SessionLocal() as db:
        assert await sembrar_deportivo_demo(db, club_id) is True
        jugadores = (await db.scalars(
            select(Jugador).where(Jugador.club_id == club_id))).all()
        partidos = (await db.scalars(
            select(Partido).where(Partido.club_id == club_id))).all()

    return {
        "auth": _auth(sesion["access_token"]),
        "plantel": {j.dorsal: j.id for j in jugadores},
        "partido": {p.rival: p.id for p in partidos},
    }


def _con_alineacion(club: dict) -> int:
    return club["partido"]["Club Rival Uno"]


def _sin_alineacion(club: dict) -> int:
    return club["partido"]["Club Rival Dos"]


def _finalizado(club: dict) -> int:
    return club["partido"]["Club Rival Tres"]


def _payload(plantel: dict, titulares=None, capitanes=(CAPITAN_DEMO,),
             formacion: str = "4-3-3") -> dict:
    titulares = TITULARES_DEMO if titulares is None else titulares
    return {
        "formacion": formacion,
        "jugadores": [
            {
                "jugador_id": jugador_id,
                "es_titular": dorsal in titulares,
                "es_capitan": dorsal in capitanes,
                "pos_x": titulares.get(dorsal, (0, 0))[0],
                "pos_y": titulares.get(dorsal, (0, 0))[1],
            }
            for dorsal, jugador_id in plantel.items()
        ],
    }


def _cambiar(titulares: dict, sale: int, entra: int) -> dict:
    nuevo = dict(titulares)
    nuevo[entra] = nuevo.pop(sale)
    return nuevo


async def _guardar(cliente, club: dict, partido_id: int, payload: dict):
    return await cliente.put(
        f"/api/deportivo/partidos/{partido_id}/alineacion",
        headers=club["auth"], json=payload,
    )


# ---------------- Ver ----------------

async def test_ver_alineacion_con_datos_de_cada_jugador(cliente):
    """HU-14 · Criterio 2: posiciones, titularidad y capitán, con nombre y dorsal."""
    club = await _club_con_plantel(cliente, "ver")

    r = await cliente.get(
        f"/api/deportivo/partidos/{_con_alineacion(club)}/alineacion", headers=club["auth"])
    assert r.status_code == 200, r.text
    alineacion = r.json()

    assert alineacion["formacion"] == "4-3-3"
    assert len(alineacion["jugadores"]) == 18
    titulares = alineacion["jugadores"][:11]
    assert all(j["es_titular"] for j in titulares)
    assert not any(j["es_titular"] for j in alineacion["jugadores"][11:])
    # Titulares primero, por dorsal.
    assert [j["dorsal"] for j in titulares] == sorted(TITULARES_DEMO)

    capitan = [j for j in alineacion["jugadores"] if j["es_capitan"]]
    assert len(capitan) == 1
    assert capitan[0]["dorsal"] == CAPITAN_DEMO
    assert capitan[0]["apellido"]
    assert capitan[0]["posicion"] == "DEL"

    arquero = next(j for j in titulares if j["dorsal"] == 1)
    assert (arquero["pos_x"], arquero["pos_y"]) == (5, 50)


async def test_partido_sin_alineacion_responde_404(cliente):
    club = await _club_con_plantel(cliente, "vacio")
    r = await cliente.get(
        f"/api/deportivo/partidos/{_sin_alineacion(club)}/alineacion", headers=club["auth"])
    assert r.status_code == 404


# ---------------- Guardar ----------------

async def test_guardar_y_reemplazar_alineacion(cliente):
    """HU-14 · Criterios 1 y 2: guardar crea; guardar de nuevo reemplaza."""
    club = await _club_con_plantel(cliente, "guardar")
    partido_id = _sin_alineacion(club)

    r = await _guardar(cliente, club, partido_id, _payload(club["plantel"]))
    assert r.status_code == 200, r.text
    assert len(r.json()["jugadores"]) == 18

    # Segunda versión: 4-4-2, otro capitán y solo 14 convocados.
    titulares = _cambiar(TITULARES_DEMO, sale=11, entra=16)
    convocados = {d: club["plantel"][d] for d in [*titulares, 12, 13, 18]}
    r = await _guardar(cliente, club, partido_id,
                       _payload(convocados, titulares, capitanes=(10,), formacion="4-4-2"))
    assert r.status_code == 200, r.text

    r = await cliente.get(
        f"/api/deportivo/partidos/{partido_id}/alineacion", headers=club["auth"])
    alineacion = r.json()
    assert alineacion["formacion"] == "4-4-2"
    assert len(alineacion["jugadores"]) == 14
    assert [j["dorsal"] for j in alineacion["jugadores"] if j["es_capitan"]] == [10]

    async with SessionLocal() as db:
        cantidad = await db.scalar(
            select(func.count()).select_from(Alineacion)
            .where(Alineacion.partido_id == partido_id))
    assert cantidad == 1, "Debe haber una sola alineación por partido"


@pytest.mark.parametrize(
    ("caso", "mensaje"),
    [
        ("diez_titulares", "exactamente 11 titulares (hay 10)"),
        ("doce_titulares", "exactamente 11 titulares (hay 12)"),
        ("sin_capitan", "un solo capitán (hay 0)"),
        ("dos_capitanes", "un solo capitán (hay 2)"),
        ("capitan_suplente", "El capitán tiene que ser titular"),
        ("jugador_repetido", "más de una vez"),
    ],
)
async def test_reglas_de_la_alineacion(cliente, caso, mensaje):
    """HU-14 · Criterio 3: exactamente 11 titulares y un capitán titular."""
    club = await _club_con_plantel(cliente, f"regla{caso}")
    plantel = club["plantel"]

    if caso == "diez_titulares":
        payload = _payload(plantel, {d: p for d, p in TITULARES_DEMO.items() if d != 11})
    elif caso == "doce_titulares":
        payload = _payload(plantel, {**TITULARES_DEMO, 16: (60, 50)})
    elif caso == "sin_capitan":
        payload = _payload(plantel, capitanes=())
    elif caso == "dos_capitanes":
        payload = _payload(plantel, capitanes=(9, 10))
    elif caso == "capitan_suplente":
        payload = _payload(plantel, capitanes=(18,))
    else:
        payload = _payload(plantel)
        payload["jugadores"].append(dict(payload["jugadores"][-1]))

    r = await _guardar(cliente, club, _sin_alineacion(club), payload)
    assert r.status_code == 422
    assert mensaje in r.text


@pytest.mark.parametrize(
    ("sale", "entra", "hay"),
    [(1, 14, 0), (3, 12, 2)],
    ids=["sin_arquero", "dos_arqueros"],
)
async def test_un_solo_arquero_titular(cliente, sale, entra, hay):
    """HU-14 · Criterio 3: exactamente un arquero entre los titulares."""
    club = await _club_con_plantel(cliente, f"arq{hay}")
    titulares = _cambiar(TITULARES_DEMO, sale=sale, entra=entra)

    r = await _guardar(cliente, club, _sin_alineacion(club),
                       _payload(club["plantel"], titulares))
    assert r.status_code == 422
    assert f"un solo arquero entre los titulares (hay {hay})" in r.json()["detail"]


async def test_coordenadas_fuera_de_la_cancha(cliente):
    club = await _club_con_plantel(cliente, "coord")
    payload = _payload(club["plantel"])
    payload["jugadores"][0]["pos_x"] = 101
    r = await _guardar(cliente, club, _sin_alineacion(club), payload)
    assert r.status_code == 422


async def test_jugadores_de_otro_club_son_rechazados(cliente):
    """Pb-03: no se puede alinear a jugadores de otro club."""
    club_a = await _club_con_plantel(cliente, "aaa")
    club_b = await _club_con_plantel(cliente, "bbb")

    # Plantel de B en un partido de A.
    r = await _guardar(cliente, club_a, _sin_alineacion(club_a), _payload(club_b["plantel"]))
    assert r.status_code == 422
    assert "no están en el plantel" in r.json()["detail"]


async def test_jugador_dado_de_baja_no_puede_alinearse(cliente):
    club = await _club_con_plantel(cliente, "baja")
    async with SessionLocal() as db:
        jugador = await db.get(Jugador, club["plantel"][9])
        jugador.activo = False
        await db.commit()

    r = await _guardar(cliente, club, _sin_alineacion(club), _payload(club["plantel"]))
    assert r.status_code == 422


async def test_partido_finalizado_no_se_puede_editar(cliente):
    club = await _club_con_plantel(cliente, "final")
    r = await _guardar(cliente, club, _finalizado(club), _payload(club["plantel"]))
    assert r.status_code == 409
    assert "FINALIZADO" in r.json()["detail"]


async def test_partido_de_otro_club_responde_404(cliente):
    """Pb-03: 404 y no 403, para no revelar que el partido existe."""
    club_a = await _club_con_plantel(cliente, "cla")
    club_b = await _club_con_plantel(cliente, "clb")
    ruta = f"/api/deportivo/partidos/{_con_alineacion(club_b)}/alineacion"

    assert (await cliente.get(ruta, headers=club_a["auth"])).status_code == 404
    r = await cliente.put(ruta, headers=club_a["auth"], json=_payload(club_a["plantel"]))
    assert r.status_code == 404


async def test_analista_puede_ver_pero_no_guardar(cliente):
    """HU-14: la definen el DT y el asistente (y el administrador)."""
    club = await _club_con_plantel(cliente, "roles")
    r = await cliente.post("/api/seguridad/usuarios", headers=club["auth"], json={
        "email": "analista@test.com", "password": "password123", "rol": "ANALISTA",
    })
    assert r.status_code == 201, r.text
    login = await cliente.post("/api/seguridad/login", json={
        "email": "analista@test.com", "password": "password123",
    })
    analista = {**club, "auth": _auth(login.json()["access_token"])}
    ruta = f"/api/deportivo/partidos/{_con_alineacion(club)}/alineacion"

    assert (await cliente.get(ruta, headers=analista["auth"])).status_code == 200
    r = await cliente.put(ruta, headers=analista["auth"], json=_payload(club["plantel"]))
    assert r.status_code == 403


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_dt_y_asistente_pueden_guardar(cliente, rol):
    club = await _club_con_plantel(cliente, f"rol{rol}")
    email = f"{rol.lower()}@test.com"
    await cliente.post("/api/seguridad/usuarios", headers=club["auth"], json={
        "email": email, "password": "password123", "rol": rol,
    })
    login = await cliente.post("/api/seguridad/login", json={
        "email": email, "password": "password123",
    })
    otro = {**club, "auth": _auth(login.json()["access_token"])}

    r = await _guardar(cliente, otro, _sin_alineacion(club), _payload(club["plantel"]))
    assert r.status_code == 200, r.text


async def test_alineacion_exige_autenticacion(cliente):
    r = await cliente.get("/api/deportivo/partidos/1/alineacion")
    assert r.status_code == 401


async def test_seed_deportivo_es_idempotente(cliente):
    club = await _club_con_plantel(cliente, "idem")
    async with SessionLocal() as db:
        club_id = (await db.get(Partido, _con_alineacion(club))).club_id
        assert await sembrar_deportivo_demo(db, club_id) is False
        jugadores = await db.scalar(
            select(func.count()).select_from(Jugador).where(Jugador.club_id == club_id))
    assert jugadores == 18
