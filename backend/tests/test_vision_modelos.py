"""Pruebas de versionado de modelos ML  —  CU-29 (T-059).

Registro, listado, activación (con reversa sin reentrenar), aislamiento por
club, validación de `archivo_url` y roles.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
URL = "/api/vision/modelos"


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _registrar(cliente, sufijo: str) -> str:
    """Registra un club y devuelve el access token de su administrador."""
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}",
        "email": f"admin{sufijo}@test.com",
        "password": "password123",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


async def _token_con_rol(cliente, token_admin: str, rol: str) -> str:
    """Crea un usuario con ese rol en el club del admin y devuelve su token."""
    email = f"{rol.lower()}@test.com"
    r = await cliente.post("/api/seguridad/usuarios", headers=_auth(token_admin), json={
        "email": email, "password": "password123", "rol": rol,
    })
    assert r.status_code == 201, r.text
    r = await cliente.post("/api/seguridad/login", json={
        "email": email, "password": "password123",
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _cuerpo(**cambios) -> dict:
    cuerpo = {
        "nombre": "futbol-propio",
        "version": "v1",
        "tipo": "DETECCION",
        "archivo_url": "https://cdn.club.com/modelos/futbol-v1.pt",
        "map50_jugador": 0.87,
        "map50_balon": 0.64,
        "idf1": 0.72,
        "notas": "Entrenado con 2000 cuadros propios",
    }
    cuerpo.update(cambios)
    return cuerpo


# ---------- registrar y listar ----------

async def test_registrar_devuelve_201_con_los_datos_guardados(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(URL, headers=_auth(token), json=_cuerpo())
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["nombre"] == "futbol-propio"
    assert data["version"] == "v1"
    assert data["tipo"] == "DETECCION"
    assert data["archivo_url"] == "https://cdn.club.com/modelos/futbol-v1.pt"
    assert data["map50_jugador"] == 0.87
    assert data["activo"] is False, "una version recien registrada no se activa sola"
    assert data["entrenado_en"]


async def test_listar_devuelve_las_versiones_mas_nueva_primero(cliente):
    token = await _registrar(cliente, "a")
    await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v1"))
    await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v2"))

    r = await cliente.get(URL, headers=_auth(token))
    assert r.status_code == 200
    versiones = [m["version"] for m in r.json()]
    assert versiones == ["v2", "v1"]


async def test_listar_sin_modelos_devuelve_lista_vacia(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.get(URL, headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


async def test_misma_version_del_mismo_nombre_es_409(cliente):
    token = await _registrar(cliente, "a")
    await cliente.post(URL, headers=_auth(token), json=_cuerpo())
    r = await cliente.post(URL, headers=_auth(token), json=_cuerpo())
    assert r.status_code == 409, r.text


# ---------- activar (con reversa) ----------

async def test_activar_marca_esa_version_como_activa(cliente):
    token = await _registrar(cliente, "a")
    creado = (await cliente.post(URL, headers=_auth(token), json=_cuerpo())).json()

    r = await cliente.post(f"{URL}/{creado['id']}/activar", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["activo"] is True


async def test_activar_otra_version_desactiva_la_anterior(cliente):
    """Solo una activa por vez: no puede haber dos simultaneas."""
    token = await _registrar(cliente, "a")
    v1 = (await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v1"))).json()
    v2 = (await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v2"))).json()

    await cliente.post(f"{URL}/{v1['id']}/activar", headers=_auth(token))
    await cliente.post(f"{URL}/{v2['id']}/activar", headers=_auth(token))

    activos = [m["activo"] for m in (await cliente.get(URL, headers=_auth(token))).json()]
    assert activos.count(True) == 1


async def test_volver_a_activar_una_version_anterior_sin_reentrenar(cliente):
    """Criterio de T-059: una version anterior se reactiva, no hace falta reentrenar."""
    token = await _registrar(cliente, "a")
    v1 = (await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v1"))).json()
    v2 = (await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v2"))).json()
    await cliente.post(f"{URL}/{v2['id']}/activar", headers=_auth(token))

    r = await cliente.post(f"{URL}/{v1['id']}/activar", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["version"] == "v1"
    assert r.json()["activo"] is True

    datos = {m["version"]: m["activo"] for m in (await cliente.get(URL, headers=_auth(token))).json()}
    assert datos == {"v1": True, "v2": False}


async def test_activar_modelo_inexistente_es_404(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(f"{URL}/9999/activar", headers=_auth(token))
    assert r.status_code == 404


# ---------- aislamiento entre clubes ----------

async def test_un_club_no_ve_los_modelos_de_otro(cliente):
    token_a = await _registrar(cliente, "a")
    token_b = await _registrar(cliente, "b")
    await cliente.post(URL, headers=_auth(token_a), json=_cuerpo())

    r = await cliente.get(URL, headers=_auth(token_b))
    assert r.status_code == 200
    assert r.json() == [], "FILTRACIÓN: el club B ve los modelos del club A"


async def test_mismo_nombre_y_version_en_clubes_distintos_no_choca(cliente):
    token_a = await _registrar(cliente, "a")
    token_b = await _registrar(cliente, "b")
    a = await cliente.post(URL, headers=_auth(token_a), json=_cuerpo())
    b = await cliente.post(URL, headers=_auth(token_b), json=_cuerpo())
    assert a.status_code == 201
    assert b.status_code == 201, "el club B no puede quedar bloqueado por el club A"


async def test_un_club_no_puede_activar_el_modelo_de_otro(cliente):
    token_a = await _registrar(cliente, "a")
    token_b = await _registrar(cliente, "b")
    de_a = (await cliente.post(URL, headers=_auth(token_a), json=_cuerpo())).json()

    r = await cliente.post(f"{URL}/{de_a['id']}/activar", headers=_auth(token_b))
    assert r.status_code == 404


# ---------- validación de archivo_url ----------

@pytest.mark.parametrize("url", [
    "http://cdn.club.com/modelos/futbol-v1.pt",
    "ftp://cdn.club.com/modelos/futbol-v1.pt",
    "file:///tmp/futbol-v1.pt",
    "cdn.club.com/modelos/futbol-v1.pt",
])
async def test_archivo_url_sin_https_es_422(cliente, url):
    token = await _registrar(cliente, "a")
    r = await cliente.post(URL, headers=_auth(token), json=_cuerpo(archivo_url=url))
    assert r.status_code == 422


@pytest.mark.parametrize("campo, valor", [
    ("map50_jugador", 1.1), ("map50_jugador", -0.1),
    ("map50_balon", 1.1), ("idf1", -0.1),
])
async def test_metricas_fuera_de_rango_son_422(cliente, campo, valor):
    token = await _registrar(cliente, "a")
    r = await cliente.post(URL, headers=_auth(token), json=_cuerpo(**{campo: valor}))
    assert r.status_code == 422


async def test_metricas_opcionales_pueden_omitirse(cliente):
    token = await _registrar(cliente, "a")
    cuerpo = _cuerpo()
    del cuerpo["map50_jugador"], cuerpo["map50_balon"], cuerpo["idf1"]
    r = await cliente.post(URL, headers=_auth(token), json=cuerpo)
    assert r.status_code == 201, r.text
    assert r.json()["map50_jugador"] is None


# ---------- autenticación y roles ----------

async def test_sin_token_es_401(cliente):
    assert (await cliente.get(URL)).status_code == 401
    assert (await cliente.post(URL, json=_cuerpo())).status_code == 401


async def test_analista_puede_registrar_y_activar(cliente):
    admin = await _registrar(cliente, "a")
    analista = await _token_con_rol(cliente, admin, "ANALISTA")
    r = await cliente.post(URL, headers=_auth(analista), json=_cuerpo())
    assert r.status_code == 201, r.text

    activar = await cliente.post(f"{URL}/{r.json()['id']}/activar", headers=_auth(analista))
    assert activar.status_code == 200


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_otros_roles_no_pueden_registrar_pero_si_leer(cliente, rol):
    admin = await _registrar(cliente, "a")
    creado = (await cliente.post(URL, headers=_auth(admin), json=_cuerpo())).json()
    token = await _token_con_rol(cliente, admin, rol)

    r = await cliente.post(URL, headers=_auth(token), json=_cuerpo(version="v2"))
    assert r.status_code == 403

    activar = await cliente.post(f"{URL}/{creado['id']}/activar", headers=_auth(token))
    assert activar.status_code == 403

    assert (await cliente.get(URL, headers=_auth(token))).status_code == 200
