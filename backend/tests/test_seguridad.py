"""Pruebas de Seguridad  —  CU-01, CU-02, CU-04.

Incluye la prueba de aislamiento entre clubes (Pb-03), que es criterio de
aceptación y debe correr en cada integración.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


async def _registrar(cliente, sufijo: str) -> dict:
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}",
        "ciudad": "Santa Cruz",
        "email": f"admin{sufijo}@test.com",
        "password": "password123",
        "nombre": "Admin",
        "apellido": sufijo,
    })
    assert r.status_code == 201, r.text
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
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": "Otro", "email": "admindos@test.com",
        "password": "password123",
    })
    assert r.status_code == 409



async def test_login_con_credenciales_invalidas(cliente):
    """CU-02: el error no revela si el email existe."""
    await _registrar(cliente, "tres")
    r = await cliente.post("/api/seguridad/login", json={
        "email": "admintres@test.com", "password": "incorrecta",
    })
    assert r.status_code == 401



async def test_endpoint_protegido_sin_token(cliente):
    r = await cliente.get("/api/seguridad/usuarios")
    assert r.status_code == 401



async def test_aislamiento_entre_clubes(cliente):
    """Pb-03: un club nunca ve usuarios de otro club."""
    club_a = await _registrar(cliente, "aaa")
    club_b = await _registrar(cliente, "bbb")

    token_a = club_a["access_token"]
    r = await cliente.get("/api/seguridad/usuarios",
                          headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200

    emails = {u["email"] for u in r.json()}
    assert club_b["usuario"]["email"] not in emails, (
        "FILTRACIÓN: el club A puede ver usuarios del club B"
    )
