"""Pruebas de calibración de cámara  —  CU-19, CU-20 (T-028).

Solo se prueba lo que T-028 guarda y devuelve: puntos y medidas de la cancha.
La homografía y los errores son de T-029 y deben quedar en None.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.vision.models import Calibracion

BASE = "http://test"
PARTIDO = 7


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


def _imagen(n: int = 8) -> list[dict[str, float]]:
    return [{"x": 100.0 + i * 50, "y": 200.0 + i * 20} for i in range(n)]


def _cancha(n: int = 8) -> list[dict[str, float]]:
    return [{"x": i * 10.0, "y": i * 5.0} for i in range(n)]


def _cuerpo(**cambios) -> dict:
    cuerpo = {
        "puntos_imagen": _imagen(),
        "puntos_cancha": _cancha(),
        "largo_m": 105,
        "ancho_m": 68,
    }
    cuerpo.update(cambios)
    return cuerpo


def _url(partido_id: int = PARTIDO) -> str:
    return f"/api/vision/partidos/{partido_id}/calibracion"


# ---------- crear y leer ----------

async def test_crear_devuelve_201_con_los_datos_guardados(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(
        coef_distorsion=[0.1, -0.05, 0.0, 0.0, 0.0],
    ))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["partido_id"] == PARTIDO
    assert data["largo_m"] == 105.0
    assert data["ancho_m"] == 68.0
    assert data["puntos_imagen"] == _imagen()
    assert data["puntos_cancha"] == _cancha()
    assert data["coef_distorsion"] == [0.1, -0.05, 0.0, 0.0, 0.0]
    assert data["creada_en"]


async def test_crear_no_calcula_homografia(cliente):
    """T-028 solo guarda: la homografía y los errores son de T-029."""
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo())
    data = r.json()
    assert data["matriz_h"] is None
    assert data["error_medio_m"] is None
    assert data["error_max_m"] is None
    assert data["valida"] is False
    assert data["coef_distorsion"] is None


async def test_leer_devuelve_lo_guardado(cliente):
    token = await _registrar(cliente, "a")
    creada = (await cliente.post(_url(), headers=_auth(token), json=_cuerpo())).json()
    r = await cliente.get(_url(), headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == creada


async def test_leer_sin_calibracion_es_404(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.get(_url(), headers=_auth(token))
    assert r.status_code == 404


# ---------- editar (upsert) ----------

async def test_editar_actualiza_la_calibracion_existente(cliente):
    token = await _registrar(cliente, "a")
    primera = await cliente.post(_url(), headers=_auth(token), json=_cuerpo())
    assert primera.status_code == 201

    segunda = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(
        largo_m=100, ancho_m=60, puntos_imagen=_imagen(9), puntos_cancha=_cancha(9),
    ))
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["id"] == primera.json()["id"]
    assert segunda.json()["creada_en"] == primera.json()["creada_en"]

    leida = (await cliente.get(_url(), headers=_auth(token))).json()
    assert leida["largo_m"] == 100.0
    assert leida["ancho_m"] == 60.0
    assert len(leida["puntos_imagen"]) == 9

    async with SessionLocal() as db:
        filas = (await db.execute(select(Calibracion))).scalars().all()
    assert len(filas) == 1


async def test_editar_reinicia_los_resultados_de_calculo(cliente):
    """Una matriz calculada con los puntos anteriores no sirve para los nuevos."""
    token = await _registrar(cliente, "a")
    await cliente.post(_url(), headers=_auth(token), json=_cuerpo())

    async with SessionLocal() as db:
        fila = (await db.execute(select(Calibracion))).scalar_one()
        fila.matriz_h = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        fila.error_medio_m = 0.4
        fila.error_max_m = 0.9
        fila.valida = True
        await db.commit()

    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(largo_m=100))
    assert r.status_code == 200
    data = r.json()
    assert data["matriz_h"] is None
    assert data["error_medio_m"] is None
    assert data["error_max_m"] is None
    assert data["valida"] is False


# ---------- aislamiento entre clubes ----------

async def test_un_club_no_ve_la_calibracion_de_otro(cliente):
    token_a = await _registrar(cliente, "a")
    token_b = await _registrar(cliente, "b")
    await cliente.post(_url(), headers=_auth(token_a), json=_cuerpo(largo_m=100))

    r = await cliente.get(_url(), headers=_auth(token_b))
    assert r.status_code == 404, "FILTRACIÓN: el club B ve la calibración del club A"


async def test_cada_club_tiene_su_propia_calibracion_del_mismo_partido(cliente):
    token_a = await _registrar(cliente, "a")
    token_b = await _registrar(cliente, "b")
    a = await cliente.post(_url(), headers=_auth(token_a), json=_cuerpo(largo_m=100))
    b = await cliente.post(_url(), headers=_auth(token_b), json=_cuerpo(largo_m=110))
    assert a.status_code == 201
    assert b.status_code == 201, "el club B no puede quedar bloqueado por el club A"
    assert a.json()["id"] != b.json()["id"]

    assert (await cliente.get(_url(), headers=_auth(token_a))).json()["largo_m"] == 100.0
    assert (await cliente.get(_url(), headers=_auth(token_b))).json()["largo_m"] == 110.0


# ---------- validación ----------

@pytest.mark.parametrize("campo, valor", [
    ("largo_m", 40), ("largo_m", 39.9), ("largo_m", 130), ("largo_m", 130.1),
    ("ancho_m", 25), ("ancho_m", 24.9), ("ancho_m", 90), ("ancho_m", 90.1),
])
async def test_medidas_fuera_de_rango_son_422(cliente, campo, valor):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(**{campo: valor}))
    assert r.status_code == 422


async def test_menos_de_8_puntos_es_422(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(
        puntos_imagen=_imagen(7), puntos_cancha=_cancha(7),
    ))
    assert r.status_code == 422


async def test_distinta_cantidad_de_puntos_es_422(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(
        puntos_imagen=_imagen(8), puntos_cancha=_cancha(9),
    ))
    assert r.status_code == 422
    assert "misma cantidad" in r.text


# ---------- cancha no reglamentaria ----------

async def test_cancha_no_reglamentaria_devuelve_sus_medidas_exactas(cliente):
    """Criterio de T-028: una cancha de 100 x 60 no se reemplaza por 105 x 68."""
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(
        largo_m=100, ancho_m=60,
    ))
    assert r.status_code == 201
    assert r.json()["largo_m"] == 100.0
    assert r.json()["ancho_m"] == 60.0

    leida = (await cliente.get(_url(), headers=_auth(token))).json()
    assert leida["largo_m"] == 100.0
    assert leida["ancho_m"] == 60.0


# ---------- autenticación y roles ----------

async def test_sin_token_es_401(cliente):
    assert (await cliente.get(_url())).status_code == 401
    assert (await cliente.post(_url(), json=_cuerpo())).status_code == 401


async def test_analista_puede_calibrar(cliente):
    admin = await _registrar(cliente, "a")
    analista = await _token_con_rol(cliente, admin, "ANALISTA")
    r = await cliente.post(_url(), headers=_auth(analista), json=_cuerpo())
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_otros_roles_no_pueden_calibrar_pero_si_leer(cliente, rol):
    admin = await _registrar(cliente, "a")
    await cliente.post(_url(), headers=_auth(admin), json=_cuerpo())
    token = await _token_con_rol(cliente, admin, rol)

    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo(largo_m=100))
    assert r.status_code == 403

    assert (await cliente.get(_url(), headers=_auth(token))).status_code == 200


# ---------- fuera de alcance de T-028 ----------

async def test_validar_y_calibracion_previa_siguen_en_501(cliente):
    """T-029 (validar) y T-035 (calibracion previa) no se implementan acá."""
    token = await _registrar(cliente, "a")
    validar = await cliente.post(f"{_url()}/validar", headers=_auth(token), json=_cuerpo())
    assert validar.status_code == 501
    previa = await cliente.get("/api/vision/sedes/Estadio/calibracion-previa",
                               headers=_auth(token))
    assert previa.status_code == 501
