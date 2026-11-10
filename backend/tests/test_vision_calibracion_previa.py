"""Calibración previa de la misma sede  —  CU-22 (T-035).

Criterio de finalización: al reutilizar una calibración, la respuesta advierte
que hay que verificar si la cámara se movió.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from datos_calibracion import cuerpo_valido
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.core.database import SessionLocal
from app.main import app
from app.vision.models import Calibracion
from app.vision.service import ADVERTENCIA_CAMARA_MOVIDA, normalizar_sede


@pytest.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _club(cliente, sufijo: str) -> dict:
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}", "email": f"admin_{sufijo}@test.com",
        "password": "password123"})
    assert r.status_code == 201, r.text
    auth = _auth(r.json()["access_token"])
    r = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": f"Eq {sufijo}", "color_local": "#1E5AA8", "color_visitante": "#FFFFFF"})
    assert r.status_code == 201, r.text
    return {"auth": auth, "equipo_id": r.json()["id"]}


async def _partido(cliente, club: dict, sede: str, dias: int = 3) -> int:
    fecha = (datetime.now(UTC) + timedelta(days=dias)).replace(microsecond=0).isoformat()
    r = await cliente.post("/api/deportivo/partidos", headers=club["auth"], json={
        "equipo_id": club["equipo_id"], "rival": "Rival", "es_local": True,
        "fecha_hora": fecha, "sede": sede})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _calibrar(cliente, club: dict, partido_id: int, largo: float = 105.0,
                    valida: bool = True, hace_dias: int | None = None) -> dict:
    """Calibra el partido. `largo` sirve para reconocer cuál se devolvió;
    `hace_dias` fija `creada_en` para ordenar sin depender del reloj."""
    cuerpo = cuerpo_valido(largo=largo)
    if not valida:
        # Dos puntos muy desplazados: error medio > 2 m (igual que en test_partido_control)
        cuerpo["puntos_cancha"][0] = {"x": 25.0, "y": 20.0}
        cuerpo["puntos_cancha"][1] = {"x": 80.0, "y": 22.0}
    r = await cliente.post(f"/api/vision/partidos/{partido_id}/calibracion",
                           headers=club["auth"], json=cuerpo)
    assert r.status_code == 201, r.text
    assert r.json()["valida"] is valida
    if hace_dias is not None:
        async with SessionLocal() as db:
            await db.execute(update(Calibracion).where(Calibracion.id == r.json()["id"])
                             .values(creada_en=datetime.now(UTC) - timedelta(days=hace_dias)))
            await db.commit()
    return r.json()


async def _previa(cliente, club: dict, sede: str):
    return await cliente.get(f"/api/vision/sedes/{quote(sede, safe='')}/calibracion-previa",
                             headers=club["auth"])


# ---------------- Criterio: advierte que la cámara pudo moverse ----------------

async def test_devuelve_la_calibracion_con_la_advertencia(cliente):
    club = await _club(cliente, "a")
    partido = await _partido(cliente, club, "Estadio Municipal")
    guardada = await _calibrar(cliente, club, partido, largo=100.0)

    r = await _previa(cliente, club, "Estadio Municipal")

    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["advertencia"] == ADVERTENCIA_CAMARA_MOVIDA
    assert "verifica que la cámara no se haya movido" in datos["advertencia"]
    # Es la calibración tal cual: puntos, medidas, homografía y el partido de origen
    for campo in ("id", "partido_id", "largo_m", "ancho_m", "puntos_imagen", "puntos_cancha",
                  "matriz_h", "error_medio_m", "error_max_m", "valida"):
        assert datos[campo] == guardada[campo], campo


async def test_la_advertencia_solo_aparece_al_reutilizar(cliente):
    club = await _club(cliente, "a")
    partido = await _partido(cliente, club, "Estadio")
    await _calibrar(cliente, club, partido)

    r = await cliente.get(f"/api/vision/partidos/{partido}/calibracion", headers=club["auth"])
    assert r.json()["advertencia"] is None


# ---------------- Sedes escritas distinto ----------------

@pytest.mark.parametrize("consulta", [
    "Estadio Municipal",
    "estadio municipal",
    "  ESTADIO   MUNICIPAL  ",
    "Estadio\tMunicipal",
])
async def test_reconoce_la_sede_escrita_distinto(cliente, consulta):
    club = await _club(cliente, "a")
    partido = await _partido(cliente, club, " Estadio  municipal ")
    await _calibrar(cliente, club, partido)

    r = await _previa(cliente, club, consulta)
    assert r.status_code == 200, r.text
    assert r.json()["partido_id"] == partido


async def test_reconoce_mayusculas_acentuadas(cliente):
    # `lower()` de SQLite no las convierte: por eso se compara en Python
    club = await _club(cliente, "a")
    partido = await _partido(cliente, club, "Cancha Ñuñoa")
    await _calibrar(cliente, club, partido)

    assert (await _previa(cliente, club, "CANCHA ÑUÑOA")).status_code == 200


async def test_una_sede_parecida_no_es_la_misma(cliente):
    club = await _club(cliente, "a")
    await _calibrar(cliente, club, await _partido(cliente, club, "Estadio Municipal Norte"))

    assert (await _previa(cliente, club, "Estadio Municipal")).status_code == 404


def test_normalizar_sede():
    assert normalizar_sede("  Cancha \t  NORTE\n") == "cancha norte"
    assert normalizar_sede("   ") == ""


# ---------------- Cuál se elige ----------------

async def test_elige_la_mas_reciente(cliente):
    club = await _club(cliente, "a")
    vieja = await _partido(cliente, club, "Estadio", dias=1)
    nueva = await _partido(cliente, club, "Estadio", dias=2)
    # Creadas en el orden inverso al de su antigüedad: manda `creada_en`, no el id
    await _calibrar(cliente, club, nueva, largo=110.0, hace_dias=1)
    await _calibrar(cliente, club, vieja, largo=100.0, hace_dias=30)

    r = await _previa(cliente, club, "Estadio")
    assert (r.json()["partido_id"], r.json()["largo_m"]) == (nueva, 110.0)


async def test_ignora_las_no_validas(cliente):
    club = await _club(cliente, "a")
    con_error = await _partido(cliente, club, "Estadio", dias=1)
    buena = await _partido(cliente, club, "Estadio", dias=2)
    await _calibrar(cliente, club, buena, largo=100.0, hace_dias=30)
    await _calibrar(cliente, club, con_error, valida=False, hace_dias=1)   # más reciente

    r = await _previa(cliente, club, "Estadio")
    assert r.status_code == 200
    assert r.json()["partido_id"] == buena


async def test_solo_no_validas_es_404(cliente):
    club = await _club(cliente, "a")
    await _calibrar(cliente, club, await _partido(cliente, club, "Estadio"), valida=False)

    assert (await _previa(cliente, club, "Estadio")).status_code == 404


async def test_otra_sede_no_cuenta(cliente):
    club = await _club(cliente, "a")
    await _calibrar(cliente, club, await _partido(cliente, club, "Cancha Sur"))

    r = await _previa(cliente, club, "Cancha Norte")
    assert r.status_code == 404
    assert r.json()["detail"] == "No hay una calibración válida previa del club en esa sede"


async def test_sin_ninguna_calibracion_es_404(cliente):
    club = await _club(cliente, "a")
    await _partido(cliente, club, "Estadio")

    assert (await _previa(cliente, club, "Estadio")).status_code == 404


# ---------------- Aislamiento entre clubes ----------------

async def test_otro_club_no_ve_calibraciones_ajenas(cliente):
    propio = await _club(cliente, "a")
    ajeno = await _club(cliente, "b")
    await _calibrar(cliente, ajeno, await _partido(cliente, ajeno, "Estadio Compartido"))

    assert (await _previa(cliente, propio, "Estadio Compartido")).status_code == 404
    assert (await _previa(cliente, ajeno, "Estadio Compartido")).status_code == 200


async def test_no_usa_la_sede_de_un_partido_ajeno(cliente):
    """Una calibración propia colgada de un partido de OTRO club (Calibracion
    no tiene FK a partido) no se encuentra por la sede de ese partido: así no
    se filtran las sedes de otros clubes."""
    propio = await _club(cliente, "a")
    ajeno = await _club(cliente, "b")
    partido_ajeno = await _partido(cliente, ajeno, "Sede Secreta")
    await _calibrar(cliente, propio, partido_ajeno)

    assert (await _previa(cliente, propio, "Sede Secreta")).status_code == 404


async def test_sin_sesion_es_401(cliente):
    r = await cliente.get("/api/vision/sedes/Estadio/calibracion-previa")
    assert r.status_code == 401


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE", "ANALISTA"])
async def test_cualquier_rol_del_club_la_consulta(cliente, rol):
    club = await _club(cliente, "a")
    await _calibrar(cliente, club, await _partido(cliente, club, "Estadio"))
    email = f"{rol.lower()}@test.com"
    r = await cliente.post("/api/seguridad/usuarios", headers=club["auth"],
                           json={"email": email, "password": "password123", "rol": rol})
    assert r.status_code == 201, r.text
    r = await cliente.post("/api/seguridad/login", json={"email": email, "password": "password123"})

    respuesta = await _previa(cliente, {"auth": _auth(r.json()["access_token"])}, "Estadio")
    assert respuesta.status_code == 200
