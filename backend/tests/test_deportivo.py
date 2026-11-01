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


async def _crear_equipo(cliente, auth: dict, sufijo: str) -> int:
    r = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": f"Equipo {sufijo}",
        "categoria": "Primera",
        "temporada": "2026",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


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


# ---------------- T-039: CU-11 CRUD de Jugadores ----------------

async def test_crear_y_ver_jugador(cliente):
    """CU-11: alta de jugador con ficha completa y consulta por identificador."""
    _, auth = await _crear_sesion(cliente, "jug1")
    eq_id = await _crear_equipo(cliente, auth, "jug1")

    payload = {
        "equipo_id": eq_id,
        "nombre": "Marcelo",
        "apellido": "Moreno",
        "dorsal": 9,
        "posicion": "DEL",
        "pie_habil": "DER",
        "altura_cm": 181,
        "peso_kg": 78,
    }
    r_crear = await cliente.post("/api/deportivo/jugadores", headers=auth, json=payload)
    assert r_crear.status_code == 201, r_crear.text
    jug = r_crear.json()
    assert jug["id"] > 0
    assert jug["nombre"] == "Marcelo"
    assert jug["dorsal"] == 9
    assert jug["activo"] is True

    r_ver = await cliente.get(f"/api/deportivo/jugadores/{jug['id']}", headers=auth)
    assert r_ver.status_code == 200
    assert r_ver.json()["apellido"] == "Moreno"


async def test_listar_jugadores_de_un_equipo(cliente):
    """CU-11: listado del plantel ordenado por dorsal."""
    _, auth = await _crear_sesion(cliente, "jug_list")
    eq_id = await _crear_equipo(cliente, auth, "jug_list")

    for dorsal in (10, 3, 7):
        await cliente.post("/api/deportivo/jugadores", headers=auth, json={
            "equipo_id": eq_id,
            "nombre": "Jugador",
            "apellido": f"Dorsal{dorsal}",
            "dorsal": dorsal,
            "altura_cm": 175,
        })

    r = await cliente.get(f"/api/deportivo/equipos/{eq_id}/jugadores", headers=auth)
    assert r.status_code == 200
    dorsales = [j["dorsal"] for j in r.json()]
    assert dorsales == [3, 7, 10]


async def test_dorsal_duplicado_es_rechazado(cliente):
    """CU-11 / T-039: un dorsal duplicado entre jugadores activos del mismo equipo responde 409."""
    _, auth = await _crear_sesion(cliente, "jug_dorsal")
    eq_id = await _crear_equipo(cliente, auth, "jug_dorsal")

    base = {"equipo_id": eq_id, "dorsal": 10, "altura_cm": 180}
    r1 = await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        **base, "nombre": "Primero", "apellido": "Uno",
    })
    assert r1.status_code == 201

    r2 = await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        **base, "nombre": "Segundo", "apellido": "Dos",
    })
    assert r2.status_code == 409


async def test_editar_jugador_valida_dorsal(cliente):
    """CU-11: edición parcial de la ficha; el nuevo dorsal también se valida."""
    _, auth = await _crear_sesion(cliente, "jug_edit")
    eq_id = await _crear_equipo(cliente, auth, "jug_edit")

    await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        "equipo_id": eq_id, "nombre": "Uno", "apellido": "A", "dorsal": 5, "altura_cm": 170,
    })
    r2 = await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        "equipo_id": eq_id, "nombre": "Dos", "apellido": "B", "dorsal": 6, "altura_cm": 172,
    })
    jug2_id = r2.json()["id"]

    # Cambiar al dorsal ya ocupado por el jugador 1 -> 409
    r_conflicto = await cliente.patch(f"/api/deportivo/jugadores/{jug2_id}", headers=auth, json={
        "dorsal": 5,
    })
    assert r_conflicto.status_code == 409

    # Cambiar a un dorsal libre -> 200
    r_ok = await cliente.patch(f"/api/deportivo/jugadores/{jug2_id}", headers=auth, json={
        "dorsal": 11, "posicion": "ARQ",
    })
    assert r_ok.status_code == 200
    editado = r_ok.json()
    assert editado["dorsal"] == 11
    assert editado["posicion"] == "ARQ"
    assert editado["apellido"] == "B"  # Preserva los campos no modificados


async def test_baja_jugador_preserva_metricas_y_libera_dorsal(cliente):
    """CU-11 / T-039: la baja lógica no borra al jugador y libera su dorsal."""
    _, auth = await _crear_sesion(cliente, "jug_baja")
    eq_id = await _crear_equipo(cliente, auth, "jug_baja")

    r_crear = await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        "equipo_id": eq_id, "nombre": "Saliente", "apellido": "X", "dorsal": 4, "altura_cm": 169,
    })
    jug_id = r_crear.json()["id"]

    r_baja = await cliente.delete(f"/api/deportivo/jugadores/{jug_id}", headers=auth)
    assert r_baja.status_code == 204

    # Ya no aparece en el listado de activos
    r_activos = await cliente.get(f"/api/deportivo/equipos/{eq_id}/jugadores", headers=auth)
    assert jug_id not in [j["id"] for j in r_activos.json()]

    # Pero su ficha sigue existiendo con activo=False (conserva historial)
    r_ver = await cliente.get(f"/api/deportivo/jugadores/{jug_id}", headers=auth)
    assert r_ver.status_code == 200
    assert r_ver.json()["activo"] is False

    # El dorsal queda libre para un nuevo jugador activo
    r_nuevo = await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        "equipo_id": eq_id, "nombre": "Entrante", "apellido": "Y", "dorsal": 4, "altura_cm": 174,
    })
    assert r_nuevo.status_code == 201


async def test_aislamiento_entre_clubes_en_jugadores(cliente):
    """Pb-03: un club no puede acceder a jugadores de un equipo de otro club."""
    _, auth_a = await _crear_sesion(cliente, "club_jug_a")
    _, auth_b = await _crear_sesion(cliente, "club_jug_b")
    eq_b = await _crear_equipo(cliente, auth_b, "club_jug_b")

    # Club A no puede crear un jugador en el equipo de B
    r_crear = await cliente.post("/api/deportivo/jugadores", headers=auth_a, json={
        "equipo_id": eq_b, "nombre": "Infiltrado", "apellido": "Z", "dorsal": 1, "altura_cm": 180,
    })
    assert r_crear.status_code == 404

    r_jug_b = await cliente.post("/api/deportivo/jugadores", headers=auth_b, json={
        "equipo_id": eq_b, "nombre": "Legitimo", "apellido": "W", "dorsal": 1, "altura_cm": 180,
    })
    jug_b_id = r_jug_b.json()["id"]

    # Club A no puede ver, editar ni dar de baja al jugador de B
    assert (await cliente.get(f"/api/deportivo/jugadores/{jug_b_id}", headers=auth_a)).status_code == 404
    assert (await cliente.patch(f"/api/deportivo/jugadores/{jug_b_id}", headers=auth_a,
                                 json={"nombre": "Hackeado"})).status_code == 404
    assert (await cliente.delete(f"/api/deportivo/jugadores/{jug_b_id}", headers=auth_a)).status_code == 404

    # Club A no puede listar el plantel del equipo de B
    assert (await cliente.get(f"/api/deportivo/equipos/{eq_b}/jugadores", headers=auth_a)).status_code == 404


# ---------------- T-040: CU-12 Importación CSV ----------------

def _archivo_csv(contenido: str) -> dict:
    return {"archivo": ("plantel.csv", contenido.encode("utf-8"), "text/csv")}


async def test_importar_csv_vista_previa_no_guarda(cliente):
    """CU-12: sin confirmar=true se devuelve la vista previa y no se persiste nada."""
    _, auth = await _crear_sesion(cliente, "csv_preview")
    eq_id = await _crear_equipo(cliente, auth, "csv_preview")

    texto = (
        "nombre,apellido,dorsal,altura_cm\n"
        "Marcelo,Moreno,9,181\n"
        "Ever,Banega,5,170\n"
    )
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_id}/jugadores/importar", headers=auth, files=_archivo_csv(texto),
    )
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["total"] == 2
    assert resultado["importadas"] == 2
    assert resultado["con_error"] == 0

    r_list = await cliente.get(f"/api/deportivo/equipos/{eq_id}/jugadores", headers=auth)
    assert r_list.json() == []


async def test_importar_csv_confirmar_guarda_filas_validas(cliente):
    """CU-12: con confirmar=true se persisten las filas válidas del CSV."""
    _, auth = await _crear_sesion(cliente, "csv_confirma")
    eq_id = await _crear_equipo(cliente, auth, "csv_confirma")

    texto = (
        "nombre,apellido,dorsal,altura_cm\n"
        "Marcelo,Moreno,9,181\n"
        "Ever,Banega,5,170\n"
    )
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_id}/jugadores/importar", headers=auth,
        params={"confirmar": "true"}, files=_archivo_csv(texto),
    )
    assert r.status_code == 200, r.text
    assert r.json()["importadas"] == 2

    r_list = await cliente.get(f"/api/deportivo/equipos/{eq_id}/jugadores", headers=auth)
    dorsales = {j["dorsal"] for j in r_list.json()}
    assert dorsales == {5, 9}


async def test_importar_csv_fila_con_error_no_bloquea_las_demas(cliente):
    """CU-12: una fila inválida se reporta con error pero no impide importar las demás."""
    _, auth = await _crear_sesion(cliente, "csv_error_fila")
    eq_id = await _crear_equipo(cliente, auth, "csv_error_fila")

    texto = (
        "nombre,apellido,dorsal,altura_cm\n"
        "Valido,Uno,9,181\n"
        "Invalido,Dos,abc,170\n"
    )
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_id}/jugadores/importar", headers=auth,
        params={"confirmar": "true"}, files=_archivo_csv(texto),
    )
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["total"] == 2
    assert resultado["importadas"] == 1
    assert resultado["con_error"] == 1

    fila_buena = next(f for f in resultado["detalle"] if f["fila"] == 1)
    fila_mala = next(f for f in resultado["detalle"] if f["fila"] == 2)
    assert fila_buena["error"] is None
    assert fila_mala["error"] is not None

    r_list = await cliente.get(f"/api/deportivo/equipos/{eq_id}/jugadores", headers=auth)
    assert [j["dorsal"] for j in r_list.json()] == [9]


async def test_importar_csv_dorsal_duplicado_en_archivo_o_existente(cliente):
    """CU-12: dorsales que ya existen en el equipo o se repiten en el archivo se rechazan."""
    _, auth = await _crear_sesion(cliente, "csv_dorsal_dup")
    eq_id = await _crear_equipo(cliente, auth, "csv_dorsal_dup")

    await cliente.post("/api/deportivo/jugadores", headers=auth, json={
        "equipo_id": eq_id, "nombre": "Existente", "apellido": "X", "dorsal": 9, "altura_cm": 180,
    })

    texto = (
        "nombre,apellido,dorsal,altura_cm\n"
        "ChocaConDB,Uno,9,181\n"
        "Nuevo,Dos,15,170\n"
        "DuplicadoEnArchivo,Tres,15,172\n"
    )
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_id}/jugadores/importar", headers=auth,
        params={"confirmar": "true"}, files=_archivo_csv(texto),
    )
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["total"] == 3
    assert resultado["importadas"] == 1
    assert resultado["con_error"] == 2

    detalle = {f["fila"]: f["error"] for f in resultado["detalle"]}
    assert detalle[1] is not None  # choca con el dorsal ya existente en BD
    assert detalle[2] is None
    assert detalle[3] is not None  # duplicado dentro del mismo archivo


async def test_importar_csv_columnas_faltantes_responde_422(cliente):
    """CU-12: un CSV sin las columnas obligatorias responde 422."""
    _, auth = await _crear_sesion(cliente, "csv_columnas")
    eq_id = await _crear_equipo(cliente, auth, "csv_columnas")

    texto = "nombre,apellido,dorsal\nFalta,Altura,5\n"
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_id}/jugadores/importar", headers=auth, files=_archivo_csv(texto),
    )
    assert r.status_code == 422


async def test_importar_csv_aislamiento_entre_clubes(cliente):
    """Pb-03: un club no puede importar un plantel en un equipo de otro club."""
    _, auth_a = await _crear_sesion(cliente, "csv_club_a")
    _, auth_b = await _crear_sesion(cliente, "csv_club_b")
    eq_b = await _crear_equipo(cliente, auth_b, "csv_club_b")

    texto = "nombre,apellido,dorsal,altura_cm\nIntento,Hack,1,180\n"
    r = await cliente.post(
        f"/api/deportivo/equipos/{eq_b}/jugadores/importar", headers=auth_a, files=_archivo_csv(texto),
    )
    assert r.status_code == 404
