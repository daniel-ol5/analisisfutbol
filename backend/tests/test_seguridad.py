"""Pruebas de Seguridad — CU-01, CU-02, CU-04, CU-05, CU-06 y acceso multi-club."""

import re

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


# ---------- CU-06 Recuperar contraseña (HU-52) ----------

@pytest.fixture
def buzon(monkeypatch) -> list[dict]:
    """Captura los correos en lugar de enviarlos."""
    enviados: list[dict] = []

    async def falso(destino: str, asunto: str, cuerpo: str) -> None:
        enviados.append({"destino": destino, "asunto": asunto, "cuerpo": cuerpo})

    monkeypatch.setattr("app.seguridad.router.enviar_correo", falso)
    return enviados


def _token_del_correo(correo: dict) -> str:
    match = re.search(r"/restablecer\?token=(\S+)", correo["cuerpo"])
    assert match, correo["cuerpo"]
    return match.group(1)


async def _pedir_enlace(cliente, email: str):
    return await cliente.post("/api/seguridad/password/olvido", json={"email": email})


async def _restablecer(cliente, token: str, nueva: str = "nuevaClave456"):
    return await cliente.post(
        "/api/seguridad/password/restablecer",
        json={"token": token, "password_nueva": nueva},
    )


async def test_recuperacion_envia_enlace_y_permite_entrar_de_inmediato(cliente, buzon):
    """HU-52 · Criterios 1 y 3: enlace por correo y sesión inmediata con la clave nueva."""
    await _registrar(cliente, "olvido")

    r = await _pedir_enlace(cliente, "adminolvido@test.com")
    assert r.status_code == 202
    assert len(buzon) == 1
    assert buzon[0]["destino"] == "adminolvido@test.com"
    assert "60 minutos" in buzon[0]["cuerpo"]

    r = await _restablecer(cliente, _token_del_correo(buzon[0]))
    assert r.status_code == 200, r.text
    sesion = r.json()
    yo = await cliente.get("/api/seguridad/yo", headers=_auth(sesion["access_token"]))
    assert yo.status_code == 200

    r_vieja = await cliente.post(
        "/api/seguridad/login",
        json={"email": "adminolvido@test.com", "password": "password123"},
    )
    assert r_vieja.status_code == 401
    r_nueva = await cliente.post(
        "/api/seguridad/login",
        json={"email": "adminolvido@test.com", "password": "nuevaClave456"},
    )
    assert r_nueva.status_code == 200


async def test_recuperacion_no_revela_si_el_email_existe(cliente, buzon):
    """HU-52: misma respuesta para un correo registrado y uno inexistente."""
    await _registrar(cliente, "existe")

    r_existe = await _pedir_enlace(cliente, "adminexiste@test.com")
    r_no_existe = await _pedir_enlace(cliente, "nadie@test.com")

    assert r_existe.status_code == r_no_existe.status_code == 202
    assert r_existe.json() == r_no_existe.json()
    assert [c["destino"] for c in buzon] == ["adminexiste@test.com"]


async def test_cuenta_desactivada_no_recibe_enlace(cliente, buzon):
    admin = await _registrar(cliente, "baja")
    creado = await _crear_usuario(cliente, admin, "baja")
    await cliente.delete(
        f"/api/seguridad/usuarios/{creado['id']}", headers=_auth(admin["access_token"])
    )

    r = await _pedir_enlace(cliente, "usuariobaja@test.com")
    assert r.status_code == 202
    assert buzon == []


async def test_enlace_es_de_un_solo_uso(cliente, buzon):
    """HU-52 · Criterio 1: el mismo enlace no sirve dos veces."""
    await _registrar(cliente, "unuso")
    await _pedir_enlace(cliente, "adminunuso@test.com")
    token = _token_del_correo(buzon[0])

    assert (await _restablecer(cliente, token)).status_code == 200
    r = await _restablecer(cliente, token, "otraClave789")
    assert r.status_code == 400
    assert "no es válido" in r.json()["detail"]


async def test_pedir_un_enlace_nuevo_anula_los_anteriores(cliente, buzon):
    """HU-52 · Criterio 3: solo el último enlace pedido es válido."""
    await _registrar(cliente, "anula")
    await _pedir_enlace(cliente, "adminanula@test.com")
    await _pedir_enlace(cliente, "adminanula@test.com")
    viejo, nuevo = (_token_del_correo(c) for c in buzon)

    assert (await _restablecer(cliente, viejo)).status_code == 400
    assert (await _restablecer(cliente, nuevo)).status_code == 200


async def test_enlace_vencido_es_rechazado(cliente, buzon, monkeypatch):
    """HU-52 · Criterio 1: el enlace vence (1 hora por defecto)."""
    from app.core.config import settings

    await _registrar(cliente, "vencido")
    monkeypatch.setattr(settings, "reset_token_minutes", -1)
    await _pedir_enlace(cliente, "adminvencido@test.com")

    r = await _restablecer(cliente, _token_del_correo(buzon[0]))
    assert r.status_code == 400


async def test_restablecer_cierra_todas_las_sesiones(cliente, buzon):
    """HU-52 · Criterio 3: quien tenía la sesión abierta queda fuera."""
    sesion = await _registrar(cliente, "intruso")
    await _pedir_enlace(cliente, "adminintruso@test.com")
    await _restablecer(cliente, _token_del_correo(buzon[0]))

    r_acc = await cliente.get("/api/seguridad/yo", headers=_auth(sesion["access_token"]))
    assert r_acc.status_code == 401
    r_ref = await cliente.post(
        "/api/seguridad/refresh", json={"refresh_token": sesion["refresh_token"]}
    )
    assert r_ref.status_code == 401


@pytest.mark.parametrize(
    "token",
    ["no-es-un-jwt", "TOKEN_DE_ACCESO", "TOKEN_DE_REFRESCO"],
)
async def test_restablecer_rechaza_tokens_que_no_son_de_recuperacion(cliente, token):
    sesion = await _registrar(cliente, "tipos")
    reemplazos = {
        "TOKEN_DE_ACCESO": sesion["access_token"],
        "TOKEN_DE_REFRESCO": sesion["refresh_token"],
    }
    r = await _restablecer(cliente, reemplazos.get(token, token))
    assert r.status_code == 400


@pytest.mark.parametrize("nueva", ["corta", "á" * 40])
async def test_restablecer_exige_la_politica_de_contrasenas(cliente, buzon, nueva):
    """HU-52 · Criterio 2: de 8 a 72 caracteres y como máximo 72 bytes."""
    await _registrar(cliente, "politica")
    await _pedir_enlace(cliente, "adminpolitica@test.com")
    token = _token_del_correo(buzon[0])

    assert (await _restablecer(cliente, token, nueva)).status_code == 422
    # Un intento rechazado por la política no consume el enlace.
    assert (await _restablecer(cliente, token)).status_code == 200


async def test_registro_con_contrasena_de_mas_de_72_bytes_da_422_y_no_500(cliente):
    """bcrypt rechaza más de 72 bytes: 40 letras acentuadas son 80 bytes."""
    r = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": "Club Bytes",
            "email": "bytes@test.com",
            "password": "á" * 40,
        },
    )
    assert r.status_code == 422
