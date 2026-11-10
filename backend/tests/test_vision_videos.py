"""Pruebas de la carga de video por partes  —  CU-28 (T-060).

Criterio de aceptación: un formato no soportado se rechaza ANTES de empezar la
carga. Además: carga reanudable por trozos, lectura del video al terminar,
aislamiento por club y roles.
"""

from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.vision.almacen import AlmacenEnDisco, obtener_almacen_videos

BASE = "http://test"


@pytest.fixture
def almacen(tmp_path):
    almacen = AlmacenEnDisco(tmp_path / "videos")
    app.dependency_overrides[obtener_almacen_videos] = lambda: almacen
    yield almacen
    app.dependency_overrides.pop(obtener_almacen_videos, None)


@pytest.fixture
async def cliente(almacen):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


@pytest.fixture(scope="module")
def mp4(tmp_path_factory) -> bytes:
    """Un MP4 real de 2 s a 25 fps y 64x48, con ruido para que pese algo."""
    ruta = tmp_path_factory.mktemp("clip") / "clip.mp4"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), 25, (64, 48))
    rng = np.random.default_rng(7)
    for _ in range(50):
        escritor.write(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8))
    escritor.release()
    datos = ruta.read_bytes()
    assert datos[4:8] == b"ftyp"
    assert len(datos) > 3000
    return datos


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _club(cliente, sufijo: str) -> dict:
    """Club con un equipo y un partido programado."""
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}",
        "email": f"admin_{sufijo}@test.com",
        "password": "password123",
    })
    assert r.status_code == 201, r.text
    auth = _auth(r.json()["access_token"])
    r = await cliente.post("/api/deportivo/equipos", headers=auth, json={"nombre": f"Eq {sufijo}"})
    assert r.status_code == 201, r.text
    fecha = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0).isoformat()
    r = await cliente.post("/api/deportivo/partidos", headers=auth, json={
        "equipo_id": r.json()["id"], "rival": "Rival", "es_local": True,
        "fecha_hora": fecha, "sede": "Cancha",
    })
    assert r.status_code == 201, r.text
    return {"auth": auth, "partido_id": r.json()["id"]}


async def _con_rol(cliente, club: dict, rol: str) -> dict[str, str]:
    email = f"{rol.lower()}@test.com"
    r = await cliente.post("/api/seguridad/usuarios", headers=club["auth"],
                           json={"email": email, "password": "password123", "rol": rol})
    assert r.status_code == 201, r.text
    r = await cliente.post("/api/seguridad/login",
                           json={"email": email, "password": "password123"})
    return _auth(r.json()["access_token"])


async def _iniciar(cliente, club, nombre="partido.mp4", tipo="video/mp4", tamano=1000, auth=None):
    return await cliente.post(
        f"/api/vision/partidos/{club['partido_id']}/videos",
        headers=auth or club["auth"],
        json={"nombre": nombre, "tipo": tipo, "tamano_bytes": tamano},
    )


async def _trozo(cliente, club, video_id, datos: bytes, inicio: int, total: int, rango=None):
    fin = inicio + len(datos) - 1
    return await cliente.put(
        f"/api/vision/videos/{video_id}/contenido",
        headers={**club["auth"], "Content-Type": "application/octet-stream",
                 "Content-Range": rango or f"bytes {inicio}-{fin}/{total}"},
        content=datos,
    )


async def _subir_todo(cliente, club, video_id, datos: bytes, trozo=1024):
    r = None
    for inicio in range(0, len(datos), trozo):
        r = await _trozo(cliente, club, video_id, datos[inicio:inicio + trozo], inicio, len(datos))
        assert r.status_code == 200, r.text
    return r


# ---------- Paso 1: validar ANTES de subir (criterio de aceptación) ----------

async def test_iniciar_crea_el_video_en_carga_sin_recibir_bytes(cliente):
    club = await _club(cliente, "a")
    r = await _iniciar(cliente, club, tamano=4_500_000_000)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["estado"] == "CARGANDO"
    assert v["bytes_recibidos"] == 0
    assert v["tamano_bytes"] == 4_500_000_000
    assert v["nombre"] == "partido.mp4"
    assert v["archivo_url"].endswith(f"video-{v['id']}.mp4")


@pytest.mark.parametrize("nombre", ["partido.avi", "partido.wmv", "partido.txt", "partido"])
async def test_formato_no_soportado_se_rechaza_antes_de_subir(cliente, nombre):
    club = await _club(cliente, "a")
    r = await _iniciar(cliente, club, nombre=nombre, tipo="")
    assert r.status_code == 415
    assert "MP4, MOV, MKV" in r.json()["detail"]
    lista = await cliente.get(f"/api/vision/partidos/{club['partido_id']}/videos",
                              headers=club["auth"])
    assert lista.json() == []  # no quedó nada a medio crear


async def test_tipo_mime_que_no_corresponde_se_rechaza(cliente):
    club = await _club(cliente, "a")
    r = await _iniciar(cliente, club, nombre="partido.mp4", tipo="image/png")
    assert r.status_code == 415
    assert "image/png" in r.json()["detail"]


@pytest.mark.parametrize(("nombre", "tipo"), [
    ("Partido.MP4", "video/mp4"),
    ("partido.mov", "video/quicktime"),
    ("partido.mkv", ""),                         # el navegador no conoce el MIME
    ("partido.mkv", "application/octet-stream"),
])
async def test_formatos_soportados(cliente, nombre, tipo):
    club = await _club(cliente, "a")
    assert (await _iniciar(cliente, club, nombre=nombre, tipo=tipo)).status_code == 201


async def test_video_demasiado_grande(cliente, monkeypatch):
    monkeypatch.setattr(settings, "video_max_bytes", 5000)
    club = await _club(cliente, "a")
    r = await _iniciar(cliente, club, tamano=5001)
    assert r.status_code == 413
    assert (await _iniciar(cliente, club, tamano=5000)).status_code == 201


async def test_tamano_cero_es_invalido(cliente):
    club = await _club(cliente, "a")
    assert (await _iniciar(cliente, club, tamano=0)).status_code == 422


async def test_partido_cancelado_no_admite_video(cliente):
    club = await _club(cliente, "a")
    r = await cliente.post(f"/api/deportivo/partidos/{club['partido_id']}/cancelar",
                           headers=club["auth"], json={"motivo": "Lluvia"})
    assert r.status_code == 200, r.text
    assert (await _iniciar(cliente, club)).status_code == 409


# ---------- Paso 2: carga por trozos ----------

async def test_carga_completa_lee_duracion_fps_y_resolucion(cliente, almacen, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()

    r = await _subir_todo(cliente, club, v["id"], mp4)

    final = r.json()
    assert final["estado"] == "SUBIDO", final
    assert final["bytes_recibidos"] == len(mp4)
    assert final["fps"] == 25
    assert final["duracion_s"] == 2
    assert final["resolucion"] == "64x48"
    assert final["mensaje_error"] is None
    assert almacen.ruta_local(final["archivo_url"]).read_bytes() == mp4


async def test_una_carga_cortada_se_retoma_desde_bytes_recibidos(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    await _trozo(cliente, club, v["id"], mp4[:1000], 0, len(mp4))
    await _trozo(cliente, club, v["id"], mp4[1000:2000], 1000, len(mp4))

    # Se cortó la red: el cliente pregunta dónde quedó y sigue desde ahí.
    estado = (await cliente.get(f"/api/vision/videos/{v['id']}", headers=club["auth"])).json()
    assert estado["estado"] == "CARGANDO"
    desde = estado["bytes_recibidos"]
    assert desde == 2000

    r = await _trozo(cliente, club, v["id"], mp4[desde:], desde, len(mp4))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "SUBIDO"


async def test_reenviar_un_trozo_ya_recibido_responde_409(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    await _trozo(cliente, club, v["id"], mp4[:1000], 0, len(mp4))

    r = await _trozo(cliente, club, v["id"], mp4[:1000], 0, len(mp4))
    assert r.status_code == 409
    assert "byte 1000" in r.json()["detail"]


async def test_un_trozo_salteado_responde_409(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    r = await _trozo(cliente, club, v["id"], mp4[1000:2000], 1000, len(mp4))
    assert r.status_code == 409
    assert "byte 0" in r.json()["detail"]


@pytest.mark.parametrize("rango", [None, "", "bytes 0-9", "bytes=0-9/100", "bytes 9-0/100"])
async def test_content_range_invalido(cliente, mp4, rango):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=100)).json()
    headers = {**club["auth"], "Content-Type": "application/octet-stream"}
    if rango is not None:
        headers["Content-Range"] = rango
    r = await cliente.put(f"/api/vision/videos/{v['id']}/contenido", headers=headers,
                          content=mp4[:10])
    assert r.status_code == 400


async def test_total_distinto_al_declarado(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    r = await _trozo(cliente, club, v["id"], mp4[:1000], 0, len(mp4) + 1)
    assert r.status_code == 400


async def test_trozo_que_se_pasa_del_final(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=100)).json()
    r = await _trozo(cliente, club, v["id"], mp4[:200], 0, 100, rango="bytes 0-199/100")
    assert r.status_code == 416


async def test_cuerpo_mas_corto_que_el_rango_no_avanza(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    r = await _trozo(cliente, club, v["id"], mp4[:500], 0, len(mp4),
                     rango=f"bytes 0-999/{len(mp4)}")
    assert r.status_code == 400
    estado = (await cliente.get(f"/api/vision/videos/{v['id']}", headers=club["auth"])).json()
    assert estado["bytes_recibidos"] == 0


async def test_cuerpo_mas_largo_que_el_rango(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    r = await _trozo(cliente, club, v["id"], mp4[:2000], 0, len(mp4),
                     rango=f"bytes 0-999/{len(mp4)}")
    assert r.status_code == 400


async def test_trozo_mayor_al_maximo(cliente, monkeypatch, mp4):
    monkeypatch.setattr(settings, "video_max_trozo_bytes", 1000)
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    assert (await _trozo(cliente, club, v["id"], mp4[:1001], 0, len(mp4))).status_code == 413


async def test_contenido_que_no_es_video_se_rechaza_en_el_primer_trozo(cliente, almacen):
    club = await _club(cliente, "a")
    falso = b"Esto es un texto renombrado a .mp4" * 10
    v = (await _iniciar(cliente, club, tamano=len(falso))).json()

    r = await _trozo(cliente, club, v["id"], falso[:100], 0, len(falso))

    assert r.status_code == 415
    estado = (await cliente.get(f"/api/vision/videos/{v['id']}", headers=club["auth"])).json()
    assert estado["estado"] == "ERROR"
    assert "no es un video MP4" in estado["mensaje_error"]
    assert not almacen.ruta_local(v["archivo_url"]).exists()


async def test_mkv_con_firma_de_mp4_se_rechaza(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, nombre="p.mkv", tipo="", tamano=len(mp4))).json()
    assert (await _trozo(cliente, club, v["id"], mp4[:1000], 0, len(mp4))).status_code == 415


async def test_archivo_completo_pero_ilegible_queda_en_error(cliente):
    club = await _club(cliente, "a")
    # Firma de MP4 válida, pero el resto es basura: se nota recién al leerlo.
    datos = b"\x00\x00\x00\x18ftypisom" + bytes(range(256)) * 20
    v = (await _iniciar(cliente, club, tamano=len(datos))).json()

    final = (await _subir_todo(cliente, club, v["id"], datos)).json()

    assert final["estado"] == "ERROR"
    assert "no se pudo leer como video" in final["mensaje_error"]


async def test_despues_de_terminar_no_se_aceptan_mas_trozos(cliente, mp4):
    club = await _club(cliente, "a")
    v = (await _iniciar(cliente, club, tamano=len(mp4))).json()
    await _subir_todo(cliente, club, v["id"], mp4)
    r = await _trozo(cliente, club, v["id"], mp4[:10], 0, len(mp4))
    assert r.status_code == 409


# ---------- Consulta, aislamiento y roles ----------

async def test_listar_videos_del_partido_el_mas_nuevo_primero(cliente):
    club = await _club(cliente, "a")
    primero = (await _iniciar(cliente, club, nombre="primer-tiempo.mp4")).json()
    segundo = (await _iniciar(cliente, club, nombre="segundo-tiempo.mp4")).json()
    r = await cliente.get(f"/api/vision/partidos/{club['partido_id']}/videos",
                          headers=club["auth"])
    assert [v["id"] for v in r.json()] == [segundo["id"], primero["id"]]


async def test_otro_club_no_ve_ni_carga_videos_ajenos(cliente, mp4):
    a = await _club(cliente, "a")
    b = await _club(cliente, "b")
    v = (await _iniciar(cliente, a, tamano=len(mp4))).json()

    assert (await cliente.get(f"/api/vision/videos/{v['id']}", headers=b["auth"])).status_code == 404
    r = await _trozo(cliente, b, v["id"], mp4[:100], 0, len(mp4))
    assert r.status_code == 404
    r = await cliente.get(f"/api/vision/partidos/{a['partido_id']}/videos", headers=b["auth"])
    assert r.status_code == 404
    r = await cliente.post(f"/api/vision/partidos/{a['partido_id']}/videos", headers=b["auth"],
                           json={"nombre": "x.mp4", "tipo": "video/mp4", "tamano_bytes": 10})
    assert r.status_code == 404


@pytest.mark.parametrize(("rol", "puede"), [("ANALISTA", True), ("ASISTENTE", True), ("DT", False)])
async def test_quien_puede_subir_video(cliente, rol, puede):
    club = await _club(cliente, "a")
    auth = await _con_rol(cliente, club, rol)
    r = await _iniciar(cliente, club, auth=auth)
    assert r.status_code == (201 if puede else 403)


async def test_el_dt_puede_ver_los_videos(cliente):
    club = await _club(cliente, "a")
    await _iniciar(cliente, club)
    auth = await _con_rol(cliente, club, "DT")
    r = await cliente.get(f"/api/vision/partidos/{club['partido_id']}/videos", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_sin_token_no_se_sube_nada(cliente):
    club = await _club(cliente, "a")
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/videos",
                           json={"nombre": "x.mp4", "tipo": "video/mp4", "tamano_bytes": 10})
    assert r.status_code == 401


async def test_obtener_muestras_video(cliente):
    club = await _club(cliente, "a")
    ini = await _iniciar(cliente, club)
    vid_id = ini.json()["id"]
    r = await cliente.get(f"/api/vision/videos/{vid_id}/muestras", headers=club["auth"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)

