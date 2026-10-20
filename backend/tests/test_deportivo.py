"""Pruebas de Gestión Deportiva  —  CU-09 y CU-10 (T-037 y T-038).

Valida:
- CRUD de equipos con pertenencia al club (T-037).
- Baja lógica de equipo preservando histórico (T-037).
- Aislamiento multi-inquilino entre clubes (Pb-03).
- Verificación de contraste de indumentaria en espacio HSV (T-038).
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


async def _crear_sesion(cliente, sufijo: str) -> tuple[dict, dict]:
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club Deportivo {sufijo}",
        "ciudad": "Santa Cruz",
        "email": f"admin_{sufijo}@test.com",
        "password": "password123",
        "nombre": "Admin",
        "apellido": sufijo,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    auth = {"Authorization": f"Bearer {data['access_token']}"}
    return data, auth


# ---------------- T-037: CU-09 CRUD de Equipos ----------------

async def test_crear_y_ver_equipo(cliente):
    """CU-09: alta de equipo y consulta por identificador."""
    _, auth = await _crear_sesion(cliente, "eq1")

    # Alta
    payload = {
        "nombre": "Primera División",
        "categoria": "Primera",
        "temporada": "2026",
        "color_local": "#1E5AA8",
        "color_visitante": "#FFFFFF",
        "color_arquero": "#F2C200",
    }
    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json=payload)
    assert r_crear.status_code == 201, r_crear.text
    eq = r_crear.json()
    assert eq["id"] > 0
    assert eq["nombre"] == "Primera División"
    assert eq["color_local"] == "#1E5AA8"
    assert eq["activo"] is True
    assert eq["jugadores"] == 0

    # Ver por id
    r_ver = await cliente.get(f"/api/deportivo/equipos/{eq['id']}", headers=auth)
    assert r_ver.status_code == 200
    assert r_ver.json()["nombre"] == "Primera División"


async def test_listar_equipos_del_club(cliente):
    """CU-09: listado de equipos activos e inactivos."""
    _, auth = await _crear_sesion(cliente, "eq_list")

    for i in range(2):
        await cliente.post("/api/deportivo/equipos", headers=auth, json={
            "nombre": f"Equipo {i}",
            "categoria": "Sub-17",
            "temporada": "2026",
            "color_local": "#1E5AA8",
            "color_visitante": "#FFFFFF",
            "color_arquero": "#F2C200",
        })

    r = await cliente.get("/api/deportivo/equipos", headers=auth)
    assert r.status_code == 200
    equipos = r.json()
    assert len(equipos) == 2


async def test_editar_equipo(cliente):
    """CU-09: actualización parcial de datos y colores del equipo."""
    _, auth = await _crear_sesion(cliente, "eq_edit")

    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": "Juvenil A",
        "categoria": "Sub-19",
        "temporada": "2026",
        "color_local": "#1E5AA8",
        "color_visitante": "#FFFFFF",
        "color_arquero": "#F2C200",
    })
    eq_id = r_crear.json()["id"]

    # Editar
    r_patch = await cliente.patch(f"/api/deportivo/equipos/{eq_id}", headers=auth, json={
        "nombre": "Juvenil Promocional",
        "color_local": "#112233",
    })
    assert r_patch.status_code == 200
    editado = r_patch.json()
    assert editado["nombre"] == "Juvenil Promocional"
    assert editado["color_local"] == "#112233"
    assert editado["categoria"] == "Sub-19"  # Preserva los campos no modificados


async def test_desactivar_equipo_baja_logica(cliente):
    """CU-09 / T-037: baja lógica preservando el histórico."""
    _, auth = await _crear_sesion(cliente, "eq_del")

    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": "Equipo Baja",
        "categoria": "Reserva",
        "temporada": "2026",
    })
    eq_id = r_crear.json()["id"]

    # Baja lógica
    r_del = await cliente.delete(f"/api/deportivo/equipos/{eq_id}", headers=auth)
    assert r_del.status_code == 204

    # Ya no aparece en activos
    r_activos = await cliente.get("/api/deportivo/equipos?activos=true", headers=auth)
    assert eq_id not in [e["id"] for e in r_activos.json()]

    # Sí aparece en todos (activos=false)
    r_todos = await cliente.get("/api/deportivo/equipos?activos=false", headers=auth)
    assert eq_id in [e["id"] for e in r_todos.json()]

    # El registro sigue existiendo con activo=False (no se elimina físicamente)
    r_ver = await cliente.get(f"/api/deportivo/equipos/{eq_id}", headers=auth)
    assert r_ver.status_code == 200
    assert r_ver.json()["activo"] is False


async def test_aislamiento_entre_clubes_en_equipos(cliente):
    """Pb-03: un club no puede acceder ni modificar equipos de otro club."""
    _, auth_a = await _crear_sesion(cliente, "club_eq_a")
    _, auth_b = await _crear_sesion(cliente, "club_eq_b")

    # Club B crea equipo
    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth_b, json={
        "nombre": "Equipo Secreto B",
        "categoria": "Primera",
        "temporada": "2026",
    })
    id_b = r_crear.json()["id"]

    # Club A intenta consultar, editar o desactivar el equipo de B -> 404
    r_get = await cliente.get(f"/api/deportivo/equipos/{id_b}", headers=auth_a)
    assert r_get.status_code == 404

    r_patch = await cliente.patch(f"/api/deportivo/equipos/{id_b}", headers=auth_a, json={
        "nombre": "Infiltrado",
    })
    assert r_patch.status_code == 404

    r_del = await cliente.delete(f"/api/deportivo/equipos/{id_b}", headers=auth_a)
    assert r_del.status_code == 404


# ---------------- T-038: CU-10 Colores de Indumentaria y HSV ----------------

async def test_verificar_colores_sin_riesgo(cliente):
    """CU-10: colores suficientemente contrastados en HSV (distancia >= 40)."""
    _, auth = await _crear_sesion(cliente, "colores_ok")

    # Azul marino (#1E5AA8) vs Blanco (#FFFFFF)
    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": "Equipo Azul",
        "color_local": "#1E5AA8",
    })
    eq_id = r_crear.json()["id"]

    r = await cliente.get(
        f"/api/deportivo/equipos/{eq_id}/colores/verificar",
        params={"color_rival": "#FFFFFF"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    aviso = r.json()
    assert aviso["hay_riesgo"] is False
    assert aviso["distancia_hsv"] >= 40.0
    assert "adecuado" in aviso["mensaje"].lower()


async def test_verificar_colores_con_riesgo(cliente):
    """CU-10 / T-038: colores muy cercanos en HSV advierten riesgo visual (distancia < 40)."""
    _, auth = await _crear_sesion(cliente, "colores_riesgo")

    # Azul #1E5AA8 vs Azul similar #1E60B5
    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": "Equipo Azul",
        "color_local": "#1E5AA8",
    })
    eq_id = r_crear.json()["id"]

    r = await cliente.get(
        f"/api/deportivo/equipos/{eq_id}/colores/verificar",
        params={"color_rival": "#1E60B5"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    aviso = r.json()
    assert aviso["hay_riesgo"] is True
    assert aviso["distancia_hsv"] < 40.0
    assert "riesgo" in aviso["mensaje"].lower() or "alternativa" in aviso["mensaje"].lower()


async def test_verificar_colores_formato_invalido_responde_422(cliente):
    """CU-10: color con formato hexadecimal inválido."""
    _, auth = await _crear_sesion(cliente, "colores_bad")

    r_crear = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": "Equipo Test",
        "color_local": "#1E5AA8",
    })
    eq_id = r_crear.json()["id"]

    r = await cliente.get(
        f"/api/deportivo/equipos/{eq_id}/colores/verificar",
        params={"color_rival": "no_hex_color"},
        headers=auth,
    )
    assert r.status_code == 422
