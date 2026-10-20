"""Pruebas de Seguridad — CU-01, CU-02, CU-04 y acceso multi-club."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import token_acceso
from app.main import app

BASE = "http://test"


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


async def _registrar(cliente, sufijo: str) -> dict:
    r = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": f"Club {sufijo}",
            "ciudad": "Santa Cruz",
            "email": f"admin{sufijo}@test.com",
            "password": "password123",
            "nombre": "Admin",
            "apellido": sufijo,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _crear_usuario(
    cliente, sesion: dict, sufijo: str, rol: str = "DT", **extra
) -> dict:
    datos = {
        "email": f"usuario{sufijo}@test.com",
        "password": "password123",
        "nombre": "Usuario",
        "apellido": sufijo,
        "rol": rol,
        **extra,
    }
    r = await cliente.post(
        "/api/seguridad/usuarios",
        json=datos,
        headers=_auth(sesion["access_token"]),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _login(cliente, email: str) -> dict:
    r = await cliente.post(
        "/api/seguridad/login",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_salud(cliente):
    r = await cliente.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


async def test_registro_devuelve_sesion(cliente):
    """CU-01: registrar un club crea el admin y devuelve sesión iniciada."""
    data = await _registrar(cliente, "uno")
    assert data["access_token"]
    assert data["usuario"]["rol"] == "ADMIN"


async def test_email_duplicado_es_rechazado(cliente):
    """CU-01: un email solo puede tener una cuenta."""
    await _registrar(cliente, "dos")
    r = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": "Otro",
            "email": "admindos@test.com",
            "password": "password123",
        },
    )
    assert r.status_code == 409


async def test_login_con_credenciales_invalidas(cliente):
    """CU-02: el error no revela si el email existe."""
    await _registrar(cliente, "tres")
    r = await cliente.post(
        "/api/seguridad/login",
        json={"email": "admintres@test.com", "password": "incorrecta"},
    )
    assert r.status_code == 401


@pytest.mark.parametrize(
    ("metodo", "ruta", "json"),
    [
        ("GET", "/api/seguridad/yo", None),
        ("GET", "/api/seguridad/usuarios", None),
        (
            "POST",
            "/api/seguridad/usuarios",
            {
                "email": "sin-auth@test.com",
                "password": "password123",
                "rol": "DT",
            },
        ),
    ],
)
async def test_todos_los_endpoints_de_usuario_exigen_autenticacion(
    cliente, metodo, ruta, json
):
    r = await cliente.request(metodo, ruta, json=json)
    assert r.status_code == 401


async def test_usuario_puede_consultar_sus_recursos(cliente):
    club_a = await _registrar(cliente, "propio")
    creado = await _crear_usuario(cliente, club_a, "propio")

    yo = await cliente.get(
        "/api/seguridad/yo", headers=_auth(club_a["access_token"])
    )
    listado = await cliente.get(
        "/api/seguridad/usuarios", headers=_auth(club_a["access_token"])
    )

    assert yo.status_code == 200
    assert yo.json()["id"] == club_a["usuario"]["id"]
    assert {u["id"] for u in listado.json()} == {
        club_a["usuario"]["id"],
        creado["id"],
    }


async def test_aislamiento_entre_clubes(cliente):
    """T-010: un club nunca ve usuarios de otro club en sus listados."""
    club_a = await _registrar(cliente, "aaa")
    club_b = await _registrar(cliente, "bbb")

    r = await cliente.get(
        "/api/seguridad/usuarios", headers=_auth(club_a["access_token"])
    )
    assert r.status_code == 200

    emails = {u["email"] for u in r.json()}
    assert club_a["usuario"]["email"] in emails
    assert club_b["usuario"]["email"] not in emails, (
        "FILTRACIÓN: el club A puede ver usuarios del club B"
    )


async def test_identidad_cruzada_no_revela_usuario_de_otro_club(cliente):
    club_a = await _registrar(cliente, "identidad-a")
    club_b = await _registrar(cliente, "identidad-b")

    token_cruzado = token_acceso(
        club_b["usuario"]["id"], club_a["usuario"]["club_id"], "ADMIN"
    )
    token_inexistente = token_acceso(
        999_999, club_a["usuario"]["club_id"], "ADMIN"
    )

    cruzado = await cliente.get("/api/seguridad/yo", headers=_auth(token_cruzado))
    inexistente = await cliente.get(
        "/api/seguridad/yo", headers=_auth(token_inexistente)
    )

    assert cruzado.status_code == inexistente.status_code == 404
    assert cruzado.json() == inexistente.json() == {"detail": "No encontrado"}


async def test_creacion_no_permite_elegir_otro_club(cliente):
    club_a = await _registrar(cliente, "creacion-a")
    club_b = await _registrar(cliente, "creacion-b")

    creado = await _crear_usuario(
        cliente,
        club_a,
        "inyectado",
        club_id=club_b["usuario"]["club_id"],
    )

    assert creado["club_id"] == club_a["usuario"]["club_id"]
    listado_b = await cliente.get(
        "/api/seguridad/usuarios", headers=_auth(club_b["access_token"])
    )
    assert creado["email"] not in {u["email"] for u in listado_b.json()}


async def test_rol_sin_privilegios_no_puede_eludir_aislamiento(cliente):
    club_a = await _registrar(cliente, "rol-a")
    club_b = await _registrar(cliente, "rol-b")
    dt = await _crear_usuario(cliente, club_a, "dt", rol="DT")
    sesion_dt = await _login(cliente, dt["email"])

    listado = await cliente.get(
        "/api/seguridad/usuarios", headers=_auth(sesion_dt["access_token"])
    )
    creacion = await cliente.post(
        "/api/seguridad/usuarios",
        headers=_auth(sesion_dt["access_token"]),
        json={
            "email": "ataque@test.com",
            "password": "password123",
            "rol": "ADMIN",
            "club_id": club_b["usuario"]["club_id"],
        },
    )

    assert listado.status_code == 403
    assert creacion.status_code == 403
