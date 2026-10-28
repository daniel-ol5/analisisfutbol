"""Pruebas de Seguridad — CU-01, CU-02, CU-04, CU-05 y acceso multi-club."""

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
        ("PATCH", "/api/seguridad/yo", {"nombre": "Sin auth"}),
        (
            "POST",
            "/api/seguridad/yo/password",
            {"password_actual": "password123", "password_nueva": "nuevaClave456"},
        ),
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


# ---------- T-004: CU-02, CU-03 Login, logout y refresco ----------

async def test_refresco_token_exitoso_y_rotacion(cliente):
    """CU-02: el token de refresco emite nueva sesión y no puede reutilizarse (rotación)."""
    sesion = await _registrar(cliente, "rotacion")
    refresh_1 = sesion["refresh_token"]

    # Refresco exitoso
    r = await cliente.post("/api/seguridad/refresh", json={"refresh_token": refresh_1})
    assert r.status_code == 200, r.text
    nueva_sesion = r.json()
    assert nueva_sesion["access_token"]
    assert nueva_sesion["refresh_token"]
    assert nueva_sesion["refresh_token"] != refresh_1

    # Rotación: el token previo queda revocado y es rechazado
    r_reuso = await cliente.post("/api/seguridad/refresh", json={"refresh_token": refresh_1})
    assert r_reuso.status_code == 401

    # El nuevo token de refresco sí es válido
    r_nuevo = await cliente.post("/api/seguridad/refresh", json={"refresh_token": nueva_sesion["refresh_token"]})
    assert r_nuevo.status_code == 200


async def test_logout_invalida_token_acceso_y_refresco(cliente):
    """CU-03 / Pb-01: logout revoca token de acceso y de refresco en la lista negra."""
    sesion = await _registrar(cliente, "logout")
    token_acc = sesion["access_token"]
    token_ref = sesion["refresh_token"]

    # Cerrar sesión pasando el refresh token
    r = await cliente.post(
        "/api/seguridad/logout",
        headers={"Authorization": f"Bearer {token_acc}"},
        json={"refresh_token": token_ref},
    )
    assert r.status_code == 204

    # El token de acceso revocado ya no sirve
    r_acc = await cliente.get(
        "/api/seguridad/usuarios",
        headers={"Authorization": f"Bearer {token_acc}"},
    )
    assert r_acc.status_code == 401
    assert "revocado" in r_acc.text.lower()

    # El token de refresco revocado ya no sirve
    r_ref = await cliente.post("/api/seguridad/refresh", json={"refresh_token": token_ref})
    assert r_ref.status_code == 401


async def test_refresco_con_token_invalido_o_tipo_incorrecto(cliente):
    """CU-02: tokens malformados o tokens de acceso usados como refresco son rechazados."""
    sesion = await _registrar(cliente, "falso")
    r1 = await cliente.post("/api/seguridad/refresh", json={"refresh_token": "token_invalido"})
    assert r1.status_code == 401

    # Intentar usar access_token como refresh_token
    r2 = await cliente.post("/api/seguridad/refresh", json={"refresh_token": sesion["access_token"]})
    assert r2.status_code == 401


# ---------- T-005: CU-04 ABM de usuarios y control de roles ----------

async def test_admin_abm_completo_usuario(cliente):
    """CU-04: admin puede crear, consultar por id, editar y dar de baja usuarios."""
    sesion = await _registrar(cliente, "abm")
    auth = {"Authorization": f"Bearer {sesion['access_token']}"}

    # Crear usuario
    r_crear = await cliente.post("/api/seguridad/usuarios", headers=auth, json={
        "email": "dt_abm@test.com",
        "password": "password123",
        "nombre": "Carlos",
        "apellido": "Bilardo",
        "rol": "DT",
    })
    assert r_crear.status_code == 201
    usr = r_crear.json()
    u_id = usr["id"]
    assert usr["rol"] == "DT"

    # Consultar por ID
    r_get = await cliente.get(f"/api/seguridad/usuarios/{u_id}", headers=auth)
    assert r_get.status_code == 200
    assert r_get.json()["email"] == "dt_abm@test.com"

    # Editar usuario (cambiar nombre y rol)
    r_patch = await cliente.patch(f"/api/seguridad/usuarios/{u_id}", headers=auth, json={
        "nombre": "Carlos Salvador",
        "rol": "ANALISTA",
    })
    assert r_patch.status_code == 200
    editado = r_patch.json()
    assert editado["nombre"] == "Carlos Salvador"
    assert editado["rol"] == "ANALISTA"

    # Dar de baja (soft-delete activo=False)
    r_del = await cliente.delete(f"/api/seguridad/usuarios/{u_id}", headers=auth)
    assert r_del.status_code == 204

    # Verificar que quedó inactivo
    r_get_del = await cliente.get(f"/api/seguridad/usuarios/{u_id}", headers=auth)
    assert r_get_del.status_code == 200
    assert r_get_del.json()["activo"] is False


async def test_admin_no_puede_desactivar_su_propia_cuenta(cliente):
    """CU-04: protección contra bloqueo accidental del administrador."""
    sesion = await _registrar(cliente, "autobloqueo")
    auth = {"Authorization": f"Bearer {sesion['access_token']}"}
    admin_id = sesion["usuario"]["id"]

    r_del = await cliente.delete(f"/api/seguridad/usuarios/{admin_id}", headers=auth)
    assert r_del.status_code == 400

    r_patch = await cliente.patch(f"/api/seguridad/usuarios/{admin_id}", headers=auth, json={
        "activo": False,
    })
    assert r_patch.status_code == 400

    r_rol = await cliente.patch(f"/api/seguridad/usuarios/{admin_id}", headers=auth, json={
        "rol": "ASISTENTE",
    })
    assert r_rol.status_code == 400


async def test_asistente_recibe_403_al_intentar_gestionar_usuarios(cliente):
    """CU-04: un ASISTENTE recibe 403 al intentar crear, ver, editar o borrar usuarios."""
    sesion = await _registrar(cliente, "asistente_club")
    auth_admin = {"Authorization": f"Bearer {sesion['access_token']}"}

    # Admin crea al asistente
    r_crear = await cliente.post("/api/seguridad/usuarios", headers=auth_admin, json={
        "email": "asistente@test.com",
        "password": "password123",
        "nombre": "Pedro",
        "apellido": "Asistente",
        "rol": "ASISTENTE",
    })
    assert r_crear.status_code == 201
    asistente_id = r_crear.json()["id"]

    # Login del asistente
    r_login = await cliente.post("/api/seguridad/login", json={
        "email": "asistente@test.com",
        "password": "password123",
    })
    assert r_login.status_code == 200
    auth_asistente = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    # Intentos no autorizados responden 403
    r_list = await cliente.get("/api/seguridad/usuarios", headers=auth_asistente)
    assert r_list.status_code == 403

    r_post = await cliente.post("/api/seguridad/usuarios", headers=auth_asistente, json={
        "email": "otro@test.com", "password": "password123", "rol": "DT",
    })
    assert r_post.status_code == 403

    r_ver = await cliente.get(f"/api/seguridad/usuarios/{asistente_id}", headers=auth_asistente)
    assert r_ver.status_code == 403

    r_edit = await cliente.patch(f"/api/seguridad/usuarios/{asistente_id}", headers=auth_asistente, json={
        "nombre": "Hack",
    })
    assert r_edit.status_code == 403

    r_del = await cliente.delete(f"/api/seguridad/usuarios/{asistente_id}", headers=auth_asistente)
    assert r_del.status_code == 403


async def test_aislamiento_entre_clubes_en_abm(cliente):
    """CU-04: un administrador no puede consultar, editar ni dar de baja usuarios de otro club."""
    club_x = await _registrar(cliente, "clubx")
    club_y = await _registrar(cliente, "cuby")

    auth_x = {"Authorization": f"Bearer {club_x['access_token']}"}
    auth_y = {"Authorization": f"Bearer {club_y['access_token']}"}

    # Club Y crea un usuario
    r_crear = await cliente.post("/api/seguridad/usuarios", headers=auth_y, json={
        "email": "dt_y@test.com", "password": "password123", "rol": "DT",
    })
    id_y = r_crear.json()["id"]

    # Admin de Club X no puede ver, editar ni eliminar usuario de Club Y (debe ser 404)
    r_get = await cliente.get(f"/api/seguridad/usuarios/{id_y}", headers=auth_x)
    assert r_get.status_code == 404

    r_patch = await cliente.patch(f"/api/seguridad/usuarios/{id_y}", headers=auth_x, json={"nombre": "Infiltrado"})
    assert r_patch.status_code == 404

    r_delete = await cliente.delete(f"/api/seguridad/usuarios/{id_y}", headers=auth_x)
    assert r_delete.status_code == 404


# ---------- CU-05 Administrar perfil propio ----------

async def test_perfil_muestra_datos_y_club(cliente):
    """CU-05 · Criterio 1: el perfil incluye nombre, apellido, email, rol y club."""
    sesion = await _registrar(cliente, "perfil")
    r = await cliente.get("/api/seguridad/yo", headers=_auth(sesion["access_token"]))
    assert r.status_code == 200, r.text
    perfil = r.json()
    assert perfil["nombre"] == "Admin"
    assert perfil["apellido"] == "perfil"
    assert perfil["email"] == "adminperfil@test.com"
    assert perfil["rol"] == "ADMIN"
    assert perfil["club_nombre"] == "Club perfil"


@pytest.mark.parametrize("rol", ["DT", "ANALISTA", "ASISTENTE"])
async def test_cualquier_rol_edita_su_nombre_y_apellido(cliente, rol):
    """CU-05 · Criterio 2: cualquier usuario autenticado edita su propio perfil."""
    admin = await _registrar(cliente, f"edit{rol}")
    await _crear_usuario(cliente, admin, f"edit{rol}", rol=rol)
    sesion = await _login(cliente, f"usuarioedit{rol}@test.com")

    r = await cliente.patch(
        "/api/seguridad/yo",
        headers=_auth(sesion["access_token"]),
        json={"nombre": "Nuevo", "apellido": "Apellido"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Nuevo"
    assert r.json()["apellido"] == "Apellido"
    assert r.json()["club_nombre"] == f"Club edit{rol}"
    assert r.json()["rol"] == rol


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"rol": "ADMIN"},
        {"nombre": "X", "email": "otro@test.com"},
        {"nombre": "X", "activo": False},
        {"nombre": "x" * 81},
    ],
)
async def test_editar_perfil_rechaza_campos_no_permitidos(cliente, cuerpo):
    """CU-05: el perfil propio no permite cambiar email, rol ni estado."""
    sesion = await _registrar(cliente, "restringido")
    r = await cliente.patch(
        "/api/seguridad/yo", headers=_auth(sesion["access_token"]), json=cuerpo
    )
    assert r.status_code == 422


async def test_cambio_password_exige_la_actual(cliente):
    """CU-05 · Criterio 2: sin la contraseña actual válida no se cambia nada."""
    sesion = await _registrar(cliente, "clave")
    auth = _auth(sesion["access_token"])

    r_mal = await cliente.post(
        "/api/seguridad/yo/password",
        headers=auth,
        json={"password_actual": "incorrecta", "password_nueva": "nuevaClave456"},
    )
    assert r_mal.status_code == 403

    r_igual = await cliente.post(
        "/api/seguridad/yo/password",
        headers=auth,
        json={"password_actual": "password123", "password_nueva": "password123"},
    )
    assert r_igual.status_code == 400

    r_corta = await cliente.post(
        "/api/seguridad/yo/password",
        headers=auth,
        json={"password_actual": "password123", "password_nueva": "corta"},
    )
    assert r_corta.status_code == 422

    # Nada de lo anterior cambió la clave ni cerró la sesión.
    await _login(cliente, "adminclave@test.com")
    assert (await cliente.get("/api/seguridad/yo", headers=auth)).status_code == 200


async def test_cambio_password_cierra_las_demas_sesiones(cliente):
    """CU-05: tras cambiar la clave, solo sirve la sesión nueva que devuelve el endpoint."""
    movil = await _registrar(cliente, "sesiones")
    web = await _login(cliente, "adminsesiones@test.com")

    r = await cliente.post(
        "/api/seguridad/yo/password",
        headers=_auth(web["access_token"]),
        json={"password_actual": "password123", "password_nueva": "nuevaClave456"},
    )
    assert r.status_code == 200, r.text
    nueva = r.json()

    # La sesión nueva funciona.
    r_nueva = await cliente.get("/api/seguridad/yo", headers=_auth(nueva["access_token"]))
    assert r_nueva.status_code == 200

    # Los tokens de acceso y de refresco anteriores ya no sirven, en ningún dispositivo.
    for viejo in (movil, web):
        r_acc = await cliente.get("/api/seguridad/yo", headers=_auth(viejo["access_token"]))
        assert r_acc.status_code == 401
        r_ref = await cliente.post(
            "/api/seguridad/refresh", json={"refresh_token": viejo["refresh_token"]}
        )
        assert r_ref.status_code == 401

    # El refresco de la sesión nueva sí sirve.
    r_ref_nuevo = await cliente.post(
        "/api/seguridad/refresh", json={"refresh_token": nueva["refresh_token"]}
    )
    assert r_ref_nuevo.status_code == 200

    # La clave vieja ya no entra; la nueva sí.
    r_vieja = await cliente.post(
        "/api/seguridad/login",
        json={"email": "adminsesiones@test.com", "password": "password123"},
    )
    assert r_vieja.status_code == 401
    r_login = await cliente.post(
        "/api/seguridad/login",
        json={"email": "adminsesiones@test.com", "password": "nuevaClave456"},
    )
    assert r_login.status_code == 200
