"""T-029 · Endpoints de homografía: POST /calibracion calcula y guarda, POST /validar solo calcula."""

import numpy as np
import pytest
from datos_calibracion import a_json, a_pixeles, cuerpo_valido, marcas_cancha
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from test_vision_calibracion import _auth, _registrar, _token_con_rol, _url

from app.core.database import SessionLocal
from app.main import app
from app.vision.models import Calibracion


@pytest.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _cuerpo_con_clics_malos(sigma: float = 40.0, semilla: int = 3) -> dict:
    """Error medio > 2 m: clics desviados ~40 px (en el fondo de la cancha, 1 px ~ 0,3 m)."""
    rng = np.random.default_rng(semilla)
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha) + rng.normal(0, sigma, size=(len(cancha), 2))
    return cuerpo_valido(puntos_imagen=a_json(pixeles))


def _cuerpo_colineal() -> dict:
    t = np.linspace(0, 1, 10)
    recta = np.column_stack([100 + 800 * t, 200 + 300 * t])
    return cuerpo_valido(
        puntos_imagen=a_json(recta),
        puntos_cancha=a_json(marcas_cancha()[:10]),
    )


async def _filas() -> int:
    async with SessionLocal() as db:
        return (await db.execute(select(func.count()).select_from(Calibracion))).scalar_one()


# ---------- POST /validar ----------

async def test_validar_calibracion_buena_devuelve_error_cero_y_valida(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(f"{_url()}/validar", headers=_auth(token), json=cuerpo_valido())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["error_medio_m"] == pytest.approx(0.0, abs=1e-6)
    assert d["error_max_m"] == pytest.approx(0.0, abs=1e-6)
    assert isinstance(d["punto_peor"], int)
    assert d["valida"] is True
    assert "válida" in d["mensaje"]


async def test_validar_no_guarda_nada(cliente):
    token = await _registrar(cliente, "a")
    await cliente.post(f"{_url()}/validar", headers=_auth(token), json=cuerpo_valido())
    assert await _filas() == 0
    assert (await cliente.get(_url(), headers=_auth(token))).status_code == 404


async def test_validar_error_mayor_a_2_m_no_es_valida(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(f"{_url()}/validar", headers=_auth(token),
                           json=_cuerpo_con_clics_malos())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["error_medio_m"] > 2.0
    assert d["error_max_m"] >= d["error_medio_m"]
    assert d["valida"] is False
    assert "NO válida" in d["mensaje"]


async def test_validar_senala_el_punto_peor_base_0(cliente):
    token = await _registrar(cliente, "a")
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)
    pixeles[5] += [90.0, -70.0]
    r = await cliente.post(f"{_url()}/validar", headers=_auth(token),
                           json=cuerpo_valido(puntos_imagen=a_json(pixeles)))
    assert r.status_code == 200
    assert r.json()["punto_peor"] == 5


async def test_validar_no_exige_rol_ni_consulta_el_partido(cliente):
    admin = await _registrar(cliente, "a")
    dt = await _token_con_rol(cliente, admin, "DT")
    r = await cliente.post(f"{_url(99999)}/validar", headers=_auth(dt), json=cuerpo_valido())
    assert r.status_code == 200, "validar es un cálculo puro: cualquier usuario autenticado"


async def test_validar_sin_token_es_401(cliente):
    r = await cliente.post(f"{_url()}/validar", json=cuerpo_valido())
    assert r.status_code == 401


async def test_validar_puntos_colineales_es_422_con_mensaje(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(f"{_url()}/validar", headers=_auth(token), json=_cuerpo_colineal())
    assert r.status_code == 422
    assert "alineados" in r.json()["detail"]


async def test_validar_cancha_100_por_60(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(f"{_url()}/validar", headers=_auth(token),
                           json=cuerpo_valido(100.0, 60.0))
    assert r.status_code == 200
    assert r.json()["valida"] is True


# ---------- POST /calibracion ----------

async def test_calibrar_guarda_matriz_errores_y_valida(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=cuerpo_valido())
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["valida"] is True
    assert d["matriz_h"][2][2] == pytest.approx(1.0)

    async with SessionLocal() as db:
        fila = (await db.execute(select(Calibracion))).scalar_one()
    assert fila.matriz_h == d["matriz_h"]
    assert fila.valida is True
    assert (await cliente.get(_url(), headers=_auth(token))).json() == d


async def test_calibrar_con_error_mayor_a_2_m_se_guarda_como_no_valida(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo_con_clics_malos())
    assert r.status_code == 201, r.text    # se guarda, no es un 4xx
    d = r.json()
    assert d["valida"] is False
    assert d["error_medio_m"] > 2.0
    assert d["matriz_h"] is not None
    assert await _filas() == 1
    # Corregir los clics (200, upsert) la vuelve válida.
    r2 = await cliente.post(_url(), headers=_auth(token), json=cuerpo_valido())
    assert r2.status_code == 200
    assert r2.json()["valida"] is True


async def test_calibrar_matriz_degenerada_es_422_y_no_guarda_nada(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo_colineal())
    assert r.status_code == 422
    assert "alineados" in r.json()["detail"]
    assert await _filas() == 0


async def test_editar_con_puntos_degenerados_conserva_la_calibracion_anterior(cliente):
    token = await _registrar(cliente, "a")
    buena = (await cliente.post(_url(), headers=_auth(token), json=cuerpo_valido())).json()

    r = await cliente.post(_url(), headers=_auth(token), json=_cuerpo_colineal())
    assert r.status_code == 422

    assert (await cliente.get(_url(), headers=_auth(token))).json() == buena


async def test_calibrar_cancha_100_por_60_guarda_sus_medidas_y_una_matriz_exacta(cliente):
    token = await _registrar(cliente, "a")
    r = await cliente.post(_url(), headers=_auth(token), json=cuerpo_valido(100.0, 60.0))
    assert r.status_code == 201
    d = r.json()
    assert (d["largo_m"], d["ancho_m"]) == (100.0, 60.0)
    assert d["error_medio_m"] == pytest.approx(0.0, abs=1e-6)

    # La matriz guardada lleva el píxel de la esquina opuesta a (100, 60) m.
    esquina = a_pixeles(np.array([[100.0, 60.0]]))
    h = np.array(d["matriz_h"]) @ np.array([*esquina[0], 1.0])
    assert h[:2] / h[2] == pytest.approx([100.0, 60.0], abs=1e-6)


async def test_calibrar_sigue_exigiendo_rol_y_aislamiento_por_club(cliente):
    admin = await _registrar(cliente, "a")
    otro = await _registrar(cliente, "b")
    dt = await _token_con_rol(cliente, admin, "DT")

    assert (await cliente.post(_url(), headers=_auth(dt), json=cuerpo_valido())).status_code == 403
    assert await _filas() == 0

    await cliente.post(_url(), headers=_auth(admin), json=cuerpo_valido())
    assert (await cliente.get(_url(), headers=_auth(otro))).status_code == 404
