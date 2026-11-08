"""Pruebas del procesamiento diferido de video  —  CU-27 (T-061).

Criterio de aceptación: un video procesado genera las mismas entidades que un
partido en vivo. Se verifica que los lotes del worker entran por el mismo
`AlmacenPosiciones` que usa /partido/{id}/ingesta. Además: cola, cancelación,
retomar un trabajo abandonado, descarga y roles.
"""

from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from datos_calibracion import cuerpo_valido
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.core.database import SessionLocal
from app.main import app
from app.partido.schemas import MensajeWorker
from app.partido.service import obtener_almacen_posiciones
from app.vision import procesamiento
from app.vision.almacen import AlmacenEnDisco, obtener_almacen_videos
from app.vision.models import Video

BASE = "http://test"


class PosicionesEnMemoria:
    """Hace de `AlmacenPosiciones`: registra lo que se guardaría."""

    def __init__(self) -> None:
        self.guardadas: list[MensajeWorker] = []
        self.vaciados = 0

    async def agregar(self, mensaje: MensajeWorker) -> None:
        self.guardadas.append(mensaje)

    async def vaciar(self) -> None:
        self.vaciados += 1


@pytest.fixture
def posiciones():
    almacen = PosicionesEnMemoria()
    app.dependency_overrides[obtener_almacen_posiciones] = lambda: almacen
    yield almacen
    app.dependency_overrides.pop(obtener_almacen_posiciones, None)


@pytest.fixture
def almacen(tmp_path):
    almacen = AlmacenEnDisco(tmp_path / "videos")
    app.dependency_overrides[obtener_almacen_videos] = lambda: almacen
    yield almacen
    app.dependency_overrides.pop(obtener_almacen_videos, None)


@pytest.fixture
async def cliente(almacen, posiciones):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


@pytest.fixture(scope="module")
def mp4(tmp_path_factory) -> bytes:
    ruta = tmp_path_factory.mktemp("clip") / "clip.mp4"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), 25, (64, 48))
    rng = np.random.default_rng(3)
    for _ in range(50):
        escritor.write(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8))
    escritor.release()
    return ruta.read_bytes()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _club(cliente, sufijo: str, calibrar: bool = True, es_local: bool = True) -> dict:
    """Club con equipo (camisetas registradas), partido y, si se pide, calibración."""
    r = await cliente.post("/api/seguridad/registro", json={
        "nombre_club": f"Club {sufijo}", "email": f"admin_{sufijo}@test.com",
        "password": "password123",
    })
    assert r.status_code == 201, r.text
    auth = _auth(r.json()["access_token"])
    r = await cliente.post("/api/deportivo/equipos", headers=auth, json={
        "nombre": f"Eq {sufijo}", "color_local": "#1E5AA8", "color_visitante": "#FFFFFF",
    })
    assert r.status_code == 201, r.text
    fecha = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0).isoformat()
    r = await cliente.post("/api/deportivo/partidos", headers=auth, json={
        "equipo_id": r.json()["id"], "rival": "Rival", "es_local": es_local,
        "fecha_hora": fecha, "sede": "Cancha",
    })
    assert r.status_code == 201, r.text
    partido_id = r.json()["id"]
    if calibrar:
        r = await cliente.post(f"/api/vision/partidos/{partido_id}/calibracion",
                               headers=auth, json=cuerpo_valido())
        assert r.status_code == 201, r.text
    return {"auth": auth, "partido_id": partido_id}


async def _video_subido(cliente, club, datos: bytes) -> dict:
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/videos",
                           headers=club["auth"],
                           json={"nombre": "p.mp4", "tipo": "video/mp4",
                                 "tamano_bytes": len(datos)})
    assert r.status_code == 201, r.text
    video = r.json()
    r = await cliente.put(f"/api/vision/videos/{video['id']}/contenido",
                          headers={**club["auth"],
                                   "Content-Range": f"bytes 0-{len(datos) - 1}/{len(datos)}"},
                          content=datos)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "SUBIDO"
    return r.json()


async def _con_rol(cliente, club: dict, rol: str) -> dict[str, str]:
    email = f"{rol.lower()}@test.com"
    r = await cliente.post("/api/seguridad/usuarios", headers=club["auth"],
                           json={"email": email, "password": "password123", "rol": rol})
    assert r.status_code == 201, r.text
    r = await cliente.post("/api/seguridad/login",
                           json={"email": email, "password": "password123"})
    return _auth(r.json()["access_token"])


def _muestra(partido_id: int, t: float) -> dict:
    """Una muestra con el mismo contrato que manda el worker en vivo."""
    return {
        "partido": partido_id, "t": t,
        "jugadores": [
            {"tid": 7, "equipo": "LOCAL", "x": 30.0 + t, "y": 20.0, "conf": 0.9},
            {"tid": 9, "equipo": "VISITANTE", "x": 70.0, "y": 40.0, "conf": 0.8},
        ],
        "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 52.0, "y": 34.0, "conf": 0.6},
        "calidad": {"worker_conectado": True, "fps": 5.0, "jugadores_detectados": 2,
                    "balon_visible": True, "retraso_s": 0, "degradado": True,
                    "motivo": "Menos de 16 jugadores"},
    }


async def _lanzar(cliente, club, video, **datos):
    return await cliente.post(f"/api/vision/videos/{video['id']}/procesar",
                              headers=club["auth"], json=datos)


async def _tomar(cliente, auth):
    return await cliente.post("/api/vision/trabajos/tomar", headers=auth)


async def _lote(cliente, club, video, progreso, muestras):
    return await cliente.post(f"/api/vision/videos/{video['id']}/resultados",
                              headers=club["auth"],
                              json={"progreso_pct": progreso, "muestras": muestras})


# ---------- Flujo completo y criterio de aceptación ----------

async def test_flujo_completo_con_las_mismas_entidades_que_en_vivo(cliente, posiciones, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)

    r = await _lanzar(cliente, club, video, color_rival="#C8102E")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "PROCESANDO"
    assert r.json()["progreso_pct"] == 0

    # El worker toma el trabajo con todo lo necesario.
    r = await _tomar(cliente, club["auth"])
    assert r.status_code == 200, r.text
    trabajo = r.json()
    assert trabajo["video_id"] == video["id"]
    assert trabajo["partido_id"] == club["partido_id"]
    assert len(trabajo["matriz_h"]) == 3
    assert trabajo["color_propio"] == "#1E5AA8"  # de local, camiseta titular
    assert trabajo["color_rival"] == "#C8102E"
    assert trabajo["modelo"] is None  # sin modelo activo: YOLO preentrenado
    assert trabajo["fps"] == 25

    # Descarga el video tal cual se subió.
    r = await cliente.get(trabajo["archivo"], headers=club["auth"])
    assert r.status_code == 200
    assert r.content == mp4

    # Manda dos lotes y el progreso avanza.
    r = await _lote(cliente, club, video, 40, [_muestra(club["partido_id"], t) for t in (0, 0.2)])
    assert r.status_code == 200, r.text
    assert r.json()["progreso_pct"] == 40
    r = await _lote(cliente, club, video, 90, [_muestra(club["partido_id"], 0.4)])
    assert r.json()["progreso_pct"] == 90

    r = await cliente.post(f"/api/vision/videos/{video['id']}/terminar", headers=club["auth"],
                           json={"ok": True})
    final = r.json()
    assert final["estado"] == "PROCESADO"
    assert final["progreso_pct"] == 100
    assert final["procesado_en"] is not None

    # Mismas entidades que en vivo: MensajeWorker por el mismo AlmacenPosiciones.
    assert [m.t for m in posiciones.guardadas] == [0, 0.2, 0.4]
    assert all(isinstance(m, MensajeWorker) for m in posiciones.guardadas)
    assert posiciones.guardadas[0].jugadores[0].equipo == "LOCAL"
    assert posiciones.vaciados == 2  # cada lote se guarda entero


async def test_la_ingesta_en_vivo_usa_el_mismo_almacen():
    # Si alguien cambia el almacén de la ingesta, el procesamiento debe cambiar con él.
    from app.partido import router as partido_router

    assert partido_router.obtener_almacen_posiciones is obtener_almacen_posiciones


async def test_de_visitante_el_color_propio_es_la_alternativa(cliente, mp4):
    club = await _club(cliente, "a", es_local=False)
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    trabajo = (await _tomar(cliente, club["auth"])).json()
    assert trabajo["es_local"] is False
    assert trabajo["color_propio"] == "#FFFFFF"
    assert trabajo["color_rival"] is None


async def test_usa_el_modelo_activo_del_club(cliente, mp4):
    club = await _club(cliente, "a")
    r = await cliente.post("/api/vision/modelos", headers=club["auth"], json={
        "nombre": "propio", "version": "v2", "tipo": "DETECCION",
        "archivo_url": "https://cdn.club.com/propio-v2.pt",
    })
    modelo = r.json()
    await cliente.post(f"/api/vision/modelos/{modelo['id']}/activar", headers=club["auth"])
    video = await _video_subido(cliente, club, mp4)

    assert (await _lanzar(cliente, club, video)).json()["modelo_id"] == modelo["id"]
    trabajo = (await _tomar(cliente, club["auth"])).json()
    assert trabajo["modelo"]["archivo_url"] == "https://cdn.club.com/propio-v2.pt"


async def test_un_error_del_worker_queda_con_su_motivo_y_se_puede_reintentar(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    await _tomar(cliente, club["auth"])

    r = await cliente.post(f"/api/vision/videos/{video['id']}/terminar", headers=club["auth"],
                           json={"ok": False, "mensaje_error": "CUDA sin memoria"})
    assert r.json()["estado"] == "ERROR"
    assert r.json()["mensaje_error"] == "CUDA sin memoria"

    r = await _lanzar(cliente, club, video)
    assert r.status_code == 200
    assert r.json()["mensaje_error"] is None


async def test_un_fallo_sin_motivo_es_invalido(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    r = await cliente.post(f"/api/vision/videos/{video['id']}/terminar", headers=club["auth"],
                           json={"ok": False})
    assert r.status_code == 422


# ---------- Reglas al lanzar ----------

async def test_sin_calibracion_valida_no_se_procesa(cliente, mp4):
    club = await _club(cliente, "a", calibrar=False)
    video = await _video_subido(cliente, club, mp4)
    r = await _lanzar(cliente, club, video)
    assert r.status_code == 409
    assert "calibración" in r.json()["detail"]


async def test_una_carga_sin_terminar_no_se_procesa(cliente):
    club = await _club(cliente, "a")
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/videos",
                           headers=club["auth"],
                           json={"nombre": "p.mp4", "tipo": "video/mp4", "tamano_bytes": 999})
    assert (await _lanzar(cliente, club, r.json())).status_code == 409


async def test_no_se_lanza_dos_veces(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    r = await _lanzar(cliente, club, video)
    assert r.status_code == 409
    assert "ya se está procesando" in r.json()["detail"]


async def test_color_rival_invalido(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    assert (await _lanzar(cliente, club, video, color_rival="rojo")).status_code == 422


async def test_modelo_de_otro_club(cliente, mp4):
    a = await _club(cliente, "a")
    b = await _club(cliente, "b")
    r = await cliente.post("/api/vision/modelos", headers=b["auth"], json={
        "nombre": "ajeno", "version": "v1", "tipo": "DETECCION",
        "archivo_url": "https://cdn.otro.com/m.pt",
    })
    video = await _video_subido(cliente, a, mp4)
    assert (await _lanzar(cliente, a, video, modelo_id=r.json()["id"])).status_code == 404


# ---------- Cola: tomar, cancelar, retomar ----------

async def test_sin_trabajos_responde_204(cliente):
    club = await _club(cliente, "a")
    assert (await _tomar(cliente, club["auth"])).status_code == 204


async def test_un_trabajo_tomado_no_lo_toma_otro_worker(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    assert (await _tomar(cliente, club["auth"])).status_code == 200
    assert (await _tomar(cliente, club["auth"])).status_code == 204


async def test_los_trabajos_se_toman_por_orden_de_llegada(cliente, mp4):
    club = await _club(cliente, "a")
    primero = await _video_subido(cliente, club, mp4)
    segundo = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, segundo)
    await _lanzar(cliente, club, primero)
    assert (await _tomar(cliente, club["auth"])).json()["video_id"] == primero["id"]
    assert (await _tomar(cliente, club["auth"])).json()["video_id"] == segundo["id"]


async def test_un_trabajo_abandonado_se_puede_retomar(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    await _tomar(cliente, club["auth"])

    # El worker se cayó: pasó el plazo sin lotes.
    viejo = datetime.now(UTC) - procesamiento.PLAZO_SIN_NOTICIAS - timedelta(minutes=1)
    async with SessionLocal() as db:
        await db.execute(update(Video).where(Video.id == video["id"]).values(tomado_en=viejo))
        await db.commit()

    assert (await _tomar(cliente, club["auth"])).json()["video_id"] == video["id"]


async def test_cancelar_detiene_al_worker_en_su_proximo_lote(cliente, posiciones, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    await _tomar(cliente, club["auth"])

    r = await cliente.delete(f"/api/vision/videos/{video['id']}/procesar", headers=club["auth"])
    assert r.status_code == 204
    estado = (await cliente.get(f"/api/vision/videos/{video['id']}", headers=club["auth"])).json()
    assert estado["estado"] == "SUBIDO"
    assert estado["progreso_pct"] == 0

    r = await _lote(cliente, club, video, 50, [_muestra(club["partido_id"], 1)])
    assert r.status_code == 409
    assert posiciones.guardadas == []
    assert (await _tomar(cliente, club["auth"])).status_code == 204


async def test_cancelar_algo_que_no_se_procesa(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    r = await cliente.delete(f"/api/vision/videos/{video['id']}/procesar", headers=club["auth"])
    assert r.status_code == 409


async def test_el_progreso_no_retrocede(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    await _lote(cliente, club, video, 60, [])
    assert (await _lote(cliente, club, video, 30, [])).json()["progreso_pct"] == 60


async def test_muestras_de_otro_partido_se_rechazan(cliente, posiciones, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    r = await _lote(cliente, club, video, 10, [_muestra(club["partido_id"] + 99, 0)])
    assert r.status_code == 422
    assert posiciones.guardadas == []


async def test_un_lote_mayor_a_500_muestras_es_invalido(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    muestras = [_muestra(club["partido_id"], i / 5) for i in range(501)]
    assert (await _lote(cliente, club, video, 10, muestras)).status_code == 422


async def test_progreso_100_lo_pone_solo_el_backend(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    await _lanzar(cliente, club, video)
    assert (await _lote(cliente, club, video, 100, [])).status_code == 422


# ---------- Aislamiento y roles ----------

async def test_un_worker_solo_toma_trabajos_de_su_club(cliente, mp4):
    a = await _club(cliente, "a")
    b = await _club(cliente, "b")
    video = await _video_subido(cliente, a, mp4)
    await _lanzar(cliente, a, video)

    assert (await _tomar(cliente, b["auth"])).status_code == 204
    r = await cliente.get(f"/api/vision/videos/{video['id']}/archivo", headers=b["auth"])
    assert r.status_code == 404
    r = await cliente.post(f"/api/vision/videos/{video['id']}/resultados", headers=b["auth"],
                           json={"progreso_pct": 1, "muestras": []})
    assert r.status_code == 404


@pytest.mark.parametrize(("rol", "puede"), [("ANALISTA", True), ("DT", False), ("ASISTENTE", False)])
async def test_quien_lanza_y_quien_hace_de_worker(cliente, mp4, rol, puede):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    auth = await _con_rol(cliente, club, rol)
    r = await cliente.post(f"/api/vision/videos/{video['id']}/procesar", headers=auth, json={})
    assert r.status_code == (200 if puede else 403)
    r = await cliente.post("/api/vision/trabajos/tomar", headers=auth)
    assert r.status_code == (200 if puede else 403)


async def test_no_se_descarga_un_video_a_medio_subir(cliente):
    club = await _club(cliente, "a")
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/videos",
                           headers=club["auth"],
                           json={"nombre": "p.mp4", "tipo": "video/mp4", "tamano_bytes": 99})
    r = await cliente.get(f"/api/vision/videos/{r.json()['id']}/archivo", headers=club["auth"])
    assert r.status_code == 409


async def test_la_descarga_admite_range_para_reanudar(cliente, mp4):
    club = await _club(cliente, "a")
    video = await _video_subido(cliente, club, mp4)
    r = await cliente.get(f"/api/vision/videos/{video['id']}/archivo",
                          headers={**club["auth"], "Range": "bytes=100-199"})
    assert r.status_code == 206
    assert r.content == mp4[100:200]
