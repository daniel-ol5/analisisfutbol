"""Pruebas de programacion, agenda, reprogramacion y cancelacion de partidos."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.deportivo.models import Partido
from app.main import app
from app.partido.service import MODELO_PARTIDO, obtener_repositorio_partidos

BASE = "http://test"


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fecha_futura(dias: int = 5) -> str:
    return (datetime.now(UTC) + timedelta(days=dias)).replace(microsecond=0).isoformat()


def _fecha_pasada() -> str:
    return (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat()


async def _crear_club(cliente, sufijo: str) -> dict:
    registro = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": f"Club {sufijo}",
            "email": f"admin_{sufijo}@test.com",
            "password": "password123",
        },
    )
    assert registro.status_code == 201, registro.text
    sesion = registro.json()
    auth = _auth(sesion["access_token"])

    equipo = await cliente.post(
        "/api/deportivo/equipos",
        headers=auth,
        json={
            "nombre": f"Equipo {sufijo}",
            "categoria": "Primera",
            "temporada": "2026",
        },
    )
    assert equipo.status_code == 201, equipo.text

    competicion = await cliente.post(
        "/api/deportivo/competiciones",
        headers=auth,
        json={"nombre": f"Liga {sufijo}", "temporada": "2026"},
    )
    assert competicion.status_code == 201, competicion.text

    return {
        "sesion": sesion,
        "auth": auth,
        "equipo_id": equipo.json()["id"],
        "competicion_id": competicion.json()["id"],
    }


async def _auth_rol(cliente, club: dict, rol: str, sufijo: str) -> dict[str, str]:
    email = f"{rol.lower()}_{sufijo}@test.com"
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


def _datos_partido(club: dict, dias: int = 5, **cambios) -> dict:
    datos = {
        "equipo_id": club["equipo_id"],
        "rival": "Club Rival",
        "es_local": True,
        "fecha_hora": _fecha_futura(dias),
        "sede": "Estadio Municipal",
        "competicion_id": club["competicion_id"],
    }
    datos.update(cambios)
    return datos


async def _programar(cliente, club: dict, dias: int = 5, **cambios) -> dict:
    respuesta = await cliente.post(
        "/api/deportivo/partidos",
        headers=club["auth"],
        json=_datos_partido(club, dias, **cambios),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


async def _cambiar_estado(partido_id: int, estado: str) -> None:
    async with SessionLocal() as db:
        partido = await db.get(Partido, partido_id)
        partido.estado = estado
        await db.commit()


async def test_programar_y_consultar_partido(cliente):
    """HU-11: se persiste con equipo, rival, sede, torneo y estado PROGRAMADO."""
    club = await _crear_club(cliente, "programar")
    creado = await _programar(
        cliente,
        club,
        rival="  Deportivo Rival  ",
        sede="  Cancha Principal  ",
        es_local=False,
    )

    assert creado["estado"] == "PROGRAMADO"
    assert creado["equipo_id"] == club["equipo_id"]
    assert creado["competicion_id"] == club["competicion_id"]
    assert creado["rival"] == "Deportivo Rival"
    assert creado["sede"] == "Cancha Principal"
    assert creado["es_local"] is False

    consulta = await cliente.get(
        f"/api/deportivo/partidos/{creado['id']}", headers=club["auth"]
    )
    assert consulta.status_code == 200
    assert consulta.json() == creado


@pytest.mark.parametrize(
    "cambios",
    [
        {"fecha_hora": _fecha_pasada()},
        {"rival": "   "},
        {"sede": "   "},
    ],
)
async def test_programar_rechaza_datos_invalidos(cliente, cambios):
    club = await _crear_club(cliente, f"invalido_{len(cambios)}")
    respuesta = await cliente.post(
        "/api/deportivo/partidos",
        headers=club["auth"],
        json=_datos_partido(club, **cambios),
    )
    assert respuesta.status_code == 422


async def test_partido_exige_equipo_y_competicion_del_mismo_club(cliente):
    club_a = await _crear_club(cliente, "pertenencia_a")
    club_b = await _crear_club(cliente, "pertenencia_b")

    equipo_ajeno = await cliente.post(
        "/api/deportivo/partidos",
        headers=club_a["auth"],
        json=_datos_partido(club_a, equipo_id=club_b["equipo_id"]),
    )
    assert equipo_ajeno.status_code == 404

    competicion_ajena = await cliente.post(
        "/api/deportivo/partidos",
        headers=club_a["auth"],
        json=_datos_partido(club_a, competicion_id=club_b["competicion_id"]),
    )
    assert competicion_ajena.status_code == 404


async def test_dt_puede_programar_partido(cliente):
    club = await _crear_club(cliente, "rol_dt")
    auth_dt = await _auth_rol(cliente, club, "DT", "programa")
    respuesta = await cliente.post(
        "/api/deportivo/partidos",
        headers=auth_dt,
        json=_datos_partido(club),
    )
    assert respuesta.status_code == 201, respuesta.text


@pytest.mark.parametrize("rol", ["ANALISTA", "ASISTENTE"])
async def test_otros_roles_no_pueden_programar(cliente, rol):
    club = await _crear_club(cliente, f"rol_{rol.lower()}")
    auth = await _auth_rol(cliente, club, rol, "no_programa")
    respuesta = await cliente.post(
        "/api/deportivo/partidos",
        headers=auth,
        json=_datos_partido(club),
    )
    assert respuesta.status_code == 403
    agenda = await cliente.get("/api/deportivo/partidos", headers=auth)
    assert agenda.status_code == 200


async def test_agenda_cronologica_y_filtros(cliente):
    """HU-12: filtra por equipo, competicion, estado y rango inclusivo de fechas."""
    club = await _crear_club(cliente, "agenda")
    temprano = await _programar(cliente, club, dias=2, rival="Temprano")
    medio = await _programar(cliente, club, dias=5, rival="Medio")
    tarde = await _programar(
        cliente,
        club,
        dias=8,
        rival="Tarde",
        competicion_id=None,
    )
    await _cambiar_estado(medio["id"], "EN_CURSO")
    await _cambiar_estado(tarde["id"], "FINALIZADO")

    agenda = await cliente.get("/api/deportivo/partidos", headers=club["auth"])
    assert agenda.status_code == 200
    assert [p["rival"] for p in agenda.json()] == ["Temprano", "Medio", "Tarde"]

    por_estado = await cliente.get(
        "/api/deportivo/partidos",
        headers=club["auth"],
        params={"estado": "EN_CURSO"},
    )
    assert [p["id"] for p in por_estado.json()] == [medio["id"]]

    por_competicion = await cliente.get(
        "/api/deportivo/partidos",
        headers=club["auth"],
        params={"competicion_id": club["competicion_id"]},
    )
    assert [p["id"] for p in por_competicion.json()] == [
        temprano["id"],
        medio["id"],
    ]

    por_equipo = await cliente.get(
        "/api/deportivo/partidos",
        headers=club["auth"],
        params={"equipo_id": club["equipo_id"]},
    )
    assert len(por_equipo.json()) == 3

    fecha_medio = datetime.fromisoformat(medio["fecha_hora"]).date().isoformat()
    por_fecha = await cliente.get(
        "/api/deportivo/partidos",
        headers=club["auth"],
        params={"desde": fecha_medio, "hasta": fecha_medio},
    )
    assert [p["id"] for p in por_fecha.json()] == [medio["id"]]


@pytest.mark.parametrize(
    "params",
    [
        {"desde": "05/11/2026"},
        {"hasta": "fecha-invalida"},
        {"desde": "2026-12-01", "hasta": "2026-11-01"},
        {"estado": "DESCONOCIDO"},
    ],
)
async def test_agenda_rechaza_filtros_invalidos(cliente, params):
    club = await _crear_club(cliente, f"filtro_{len(params)}_{next(iter(params))}")
    respuesta = await cliente.get(
        "/api/deportivo/partidos", headers=club["auth"], params=params
    )
    assert respuesta.status_code == 422


async def test_agenda_y_detalle_respetan_aislamiento_multiclub(cliente):
    club_a = await _crear_club(cliente, "agenda_a")
    club_b = await _crear_club(cliente, "agenda_b")
    partido_a = await _programar(cliente, club_a, rival="Visible A")
    partido_b = await _programar(cliente, club_b, rival="Secreto B")

    agenda_a = await cliente.get("/api/deportivo/partidos", headers=club_a["auth"])
    assert [p["id"] for p in agenda_a.json()] == [partido_a["id"]]

    detalle_ajeno = await cliente.get(
        f"/api/deportivo/partidos/{partido_b['id']}", headers=club_a["auth"]
    )
    assert detalle_ajeno.status_code == 404

    reprogramar_ajeno = await cliente.patch(
        f"/api/deportivo/partidos/{partido_b['id']}",
        headers=club_a["auth"],
        json={"sede": "Intento ajeno"},
    )
    cancelar_ajeno = await cliente.post(
        f"/api/deportivo/partidos/{partido_b['id']}/cancelar",
        headers=club_a["auth"],
        json={"motivo": "Intento ajeno"},
    )
    assert reprogramar_ajeno.status_code == 404
    assert cancelar_ajeno.status_code == 404

    competicion_ajena = await cliente.patch(
        f"/api/deportivo/partidos/{partido_a['id']}",
        headers=club_a["auth"],
        json={"competicion_id": club_b["competicion_id"]},
    )
    assert competicion_ajena.status_code == 404


async def test_admin_reprograma_partido_programado(cliente):
    club = await _crear_club(cliente, "reprogramar")
    partido = await _programar(cliente, club)
    nueva_fecha = _fecha_futura(12)

    respuesta = await cliente.patch(
        f"/api/deportivo/partidos/{partido['id']}",
        headers=club["auth"],
        json={
            "fecha_hora": nueva_fecha,
            "sede": "Nueva Sede",
            "rival": "Nuevo Rival",
            "es_local": False,
            "competicion_id": None,
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    actualizado = respuesta.json()
    assert actualizado["estado"] == "PROGRAMADO"
    assert actualizado["fecha_hora"] == nueva_fecha.replace("+00:00", "Z")
    assert actualizado["sede"] == "Nueva Sede"
    assert actualizado["rival"] == "Nuevo Rival"
    assert actualizado["es_local"] is False
    assert actualizado["competicion_id"] is None


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"fecha_hora": _fecha_pasada()}, {"sede": None}],
)
async def test_reprogramacion_rechaza_cambios_invalidos(cliente, cuerpo):
    club = await _crear_club(cliente, f"reprogramacion_invalida_{len(cuerpo)}")
    partido = await _programar(cliente, club)
    respuesta = await cliente.patch(
        f"/api/deportivo/partidos/{partido['id']}",
        headers=club["auth"],
        json=cuerpo,
    )
    assert respuesta.status_code == 422


async def test_solo_admin_reprograma_y_cancela(cliente):
    club = await _crear_club(cliente, "rol_admin")
    partido = await _programar(cliente, club)
    auth_dt = await _auth_rol(cliente, club, "DT", "no_modifica")

    reprogramar = await cliente.patch(
        f"/api/deportivo/partidos/{partido['id']}",
        headers=auth_dt,
        json={"sede": "Otra cancha"},
    )
    cancelar = await cliente.post(
        f"/api/deportivo/partidos/{partido['id']}/cancelar",
        headers=auth_dt,
        json={"motivo": "Lluvia"},
    )
    assert reprogramar.status_code == 403
    assert cancelar.status_code == 403


async def test_cancelar_partido_programado_persiste_motivo(cliente):
    club = await _crear_club(cliente, "cancelar")
    partido = await _programar(cliente, club)

    respuesta = await cliente.post(
        f"/api/deportivo/partidos/{partido['id']}/cancelar",
        headers=club["auth"],
        json={"motivo": "  Suspendido por lluvia  "},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "CANCELADO"

    async with SessionLocal() as db:
        guardado = await db.get(Partido, partido["id"])
        assert guardado.estado == "CANCELADO"
        assert guardado.motivo_cancelacion == "Suspendido por lluvia"


@pytest.mark.parametrize("estado", ["EN_CURSO", "FINALIZADO", "CANCELADO"])
@pytest.mark.parametrize("operacion", ["reprogramar", "cancelar"])
async def test_solo_partidos_programados_se_pueden_modificar(
    cliente, estado, operacion
):
    club = await _crear_club(cliente, f"estado_{estado}_{operacion}")
    partido = await _programar(cliente, club)
    await _cambiar_estado(partido["id"], estado)

    if operacion == "reprogramar":
        respuesta = await cliente.patch(
            f"/api/deportivo/partidos/{partido['id']}",
            headers=club["auth"],
            json={"sede": "Otra cancha"},
        )
    else:
        respuesta = await cliente.post(
            f"/api/deportivo/partidos/{partido['id']}/cancelar",
            headers=club["auth"],
            json={"motivo": "Suspendido"},
        )
    assert respuesta.status_code == 409


async def test_partidos_exigen_autenticacion(cliente):
    rutas = [
        ("get", "/api/deportivo/partidos", None),
        ("get", "/api/deportivo/partidos/1", None),
        ("post", "/api/deportivo/partidos", {}),
        ("patch", "/api/deportivo/partidos/1", {"sede": "Cancha"}),
        ("post", "/api/deportivo/partidos/1/cancelar", {"motivo": "Lluvia"}),
    ]
    for metodo, ruta, cuerpo in rutas:
        respuesta = await cliente.request(metodo, ruta, json=cuerpo)
        assert respuesta.status_code == 401


async def test_operacion_en_vivo_usa_la_tabla_real_de_partidos(cliente):
    """T-047 elimina el modo provisorio que aceptaba cualquier partido_id."""
    club_a = await _crear_club(cliente, "repositorio_a")
    club_b = await _crear_club(cliente, "repositorio_b")
    partido = await _programar(cliente, club_a)
    usuario_a = UsuarioActual(
        id=club_a["sesion"]["usuario"]["id"],
        club_id=club_a["sesion"]["usuario"]["club_id"],
        rol="ADMIN",
    )
    usuario_b = UsuarioActual(
        id=club_b["sesion"]["usuario"]["id"],
        club_id=club_b["sesion"]["usuario"]["club_id"],
        rol="ADMIN",
    )

    assert MODELO_PARTIDO is Partido
    repositorio = obtener_repositorio_partidos()
    await repositorio.verificar(partido["id"], usuario_a)
    with pytest.raises(HTTPException) as error:
        await repositorio.verificar(partido["id"], usuario_b)
    assert error.value.status_code == 404
