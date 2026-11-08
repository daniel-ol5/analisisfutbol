"""Pruebas de la regla de evaluación al activar un modelo  —  CU-29 (T-064).

Criterio de aceptación: un modelo con métricas peores que el vigente no se
promueve a activo. Volver atrás a propósito (criterio de T-059) sigue siendo
posible, forzando con un motivo que queda registrado.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

URL = "/api/vision/modelos"


@pytest.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _club(cliente, sufijo: str = "a") -> dict[str, str]:
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}", "email": f"admin{sufijo}@test.com",
        "password": "password123",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _modelo(cliente, auth, version: str, **metricas) -> dict:
    cuerpo = {"nombre": "futbol", "version": version, "tipo": "DETECCION",
              "archivo_url": f"https://cdn.club.com/futbol-{version}.pt", **metricas}
    r = await cliente.post(URL, headers=auth, json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


async def _activar(cliente, auth, modelo, **cuerpo):
    if cuerpo:
        return await cliente.post(f"{URL}/{modelo['id']}/activar", headers=auth, json=cuerpo)
    return await cliente.post(f"{URL}/{modelo['id']}/activar", headers=auth)


BUENAS = {"map50_jugador": 0.88, "map50_balon": 0.65, "idf1": 0.74}


async def _activo(cliente, auth) -> str | None:
    modelos = (await cliente.get(URL, headers=auth)).json()
    return next((m["version"] for m in modelos if m["activo"]), None)


async def test_el_primer_modelo_se_activa_sin_comparar(cliente):
    auth = await _club(cliente)
    v1 = await _modelo(cliente, auth, "v1")  # sin métricas: no hay contra qué comparar
    r = await _activar(cliente, auth, v1)
    assert r.status_code == 200
    assert r.json()["activado_en"] is not None
    assert r.json()["motivo_activacion"] is None


@pytest.mark.parametrize("metricas", [
    {"map50_jugador": 0.90, "map50_balon": 0.70, "idf1": 0.80},   # mejor en todo
    dict(BUENAS),                                                  # igual
])
async def test_un_modelo_mejor_o_igual_se_activa(cliente, metricas):
    auth = await _club(cliente)
    await _activar(cliente, auth, await _modelo(cliente, auth, "v1", **BUENAS))
    r = await _activar(cliente, auth, await _modelo(cliente, auth, "v2", **metricas))
    assert r.status_code == 200
    assert await _activo(cliente, auth) == "v2"


@pytest.mark.parametrize(("campo", "valor", "texto"), [
    ("map50_jugador", 0.84, "mAP@50 jugador 0.84 < 0.88"),
    ("map50_balon", 0.60, "mAP@50 balón 0.60 < 0.65"),
    ("idf1", 0.70, "IDF1 0.70 < 0.74"),
])
async def test_criterio_t064_un_modelo_peor_no_se_promueve(cliente, campo, valor, texto):
    auth = await _club(cliente)
    await _activar(cliente, auth, await _modelo(cliente, auth, "v1", **BUENAS))
    peor = await _modelo(cliente, auth, "v2", **{**BUENAS, campo: valor})

    r = await _activar(cliente, auth, peor)

    assert r.status_code == 409
    assert texto in r.json()["detail"]
    assert "futbol v1" in r.json()["detail"]
    assert await _activo(cliente, auth) == "v1"  # la vigente sigue activa


async def test_una_metrica_sin_medir_cuenta_como_peor(cliente):
    auth = await _club(cliente)
    await _activar(cliente, auth, await _modelo(cliente, auth, "v1", **BUENAS))
    sin_idf1 = await _modelo(cliente, auth, "v2", map50_jugador=0.95, map50_balon=0.70)
    r = await _activar(cliente, auth, sin_idf1)
    assert r.status_code == 409
    assert "IDF1 sin medir" in r.json()["detail"]


async def test_lo_que_la_vigente_no_midio_no_se_compara(cliente):
    auth = await _club(cliente)
    await _activar(cliente, auth, await _modelo(cliente, auth, "v1", map50_jugador=0.80))
    r = await _activar(cliente, auth, await _modelo(cliente, auth, "v2", map50_jugador=0.85))
    assert r.status_code == 200


async def test_volver_atras_forzando_con_motivo_queda_registrado(cliente):
    """T-059 sigue valiendo: se vuelve a una versión anterior, pero a propósito."""
    auth = await _club(cliente)
    v1 = await _modelo(cliente, auth, "v1", **BUENAS)
    v2 = await _modelo(cliente, auth, "v2", map50_jugador=0.92, map50_balon=0.70, idf1=0.80)
    await _activar(cliente, auth, v1)
    await _activar(cliente, auth, v2)

    assert (await _activar(cliente, auth, v1)).status_code == 409
    r = await _activar(cliente, auth, v1, forzar=True,
                       motivo="  v2 confunde a los árbitros con jugadores  ")

    assert r.status_code == 200
    assert r.json()["motivo_activacion"] == "v2 confunde a los árbitros con jugadores"
    assert await _activo(cliente, auth) == "v1"


async def test_forzar_sin_motivo_es_invalido(cliente):
    auth = await _club(cliente)
    v1 = await _modelo(cliente, auth, "v1")
    for cuerpo in ({"forzar": True}, {"forzar": True, "motivo": "   "}):
        assert (await _activar(cliente, auth, v1, **cuerpo)).status_code == 422


async def test_forzar_un_modelo_que_no_es_peor_no_guarda_motivo(cliente):
    auth = await _club(cliente)
    await _activar(cliente, auth, await _modelo(cliente, auth, "v1", **BUENAS))
    v2 = await _modelo(cliente, auth, "v2", **BUENAS)
    r = await _activar(cliente, auth, v2, forzar=True, motivo="por las dudas")
    assert r.status_code == 200
    assert r.json()["motivo_activacion"] is None


async def test_reactivar_la_que_ya_esta_activa_no_se_compara_consigo(cliente):
    auth = await _club(cliente)
    v1 = await _modelo(cliente, auth, "v1", **BUENAS)
    await _activar(cliente, auth, v1)
    assert (await _activar(cliente, auth, v1)).status_code == 200


async def test_se_compara_solo_con_la_activa_del_mismo_club(cliente):
    a = await _club(cliente, "a")
    b = await _club(cliente, "b")
    await _activar(cliente, b, await _modelo(cliente, b, "v1",
                                             map50_jugador=0.99, map50_balon=0.99, idf1=0.99))
    r = await _activar(cliente, a, await _modelo(cliente, a, "v1", **BUENAS))
    assert r.status_code == 200
