"""Pruebas de asignación de jugadores a identificadores  —  CU-34, CU-35 (T-067)."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta

import pytest
from datos_calibracion import cuerpo_valido
from httpx import ASGITransport, AsyncClient
from modelos_falsos import SesionesPrueba
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient

from app.core.database import SessionLocal, get_db
from app.core.realtime import HubMemoria, obtener_hub
from app.core.security import token_ingesta
from app.deportivo.models import Partido
from app.main import app
from app.partido.models import AsignacionTrack
from app.partido.schemas import MensajeWorker
from app.partido.service import (
    PartidosEnTabla,
    PosicionesDescartadas,
    _motor_ingesta,
    limpiar_memoria_tracks,
    obtener_almacen_posiciones,
    obtener_reloj,
    obtener_repositorio_partidos,
    registrar_t_ingesta,
    registrar_tracks_ingesta,
)

BASE = "http://test"


class RelojFalso:
    """Reloj controlable para probar tiempos de corte sin usar sleep."""

    def __init__(self, inicial: datetime | None = None) -> None:
        self.actual = inicial or datetime(2026, 11, 8, 16, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.actual

    def avanzar(self, segundos: float) -> datetime:
        self.actual = self.actual + timedelta(seconds=segundos)
        return self.actual


@pytest.fixture(autouse=True)
def _limpiar_cache_tracks():
    limpiar_memoria_tracks()
    yield
    limpiar_memoria_tracks()


@pytest.fixture
def reloj() -> RelojFalso:
    r = RelojFalso()
    app.dependency_overrides[obtener_reloj] = lambda: r
    yield r
    app.dependency_overrides.pop(obtener_reloj, None)


@pytest.fixture
async def cliente(reloj):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fecha_futura(dias: int = 5) -> str:
    return (datetime.now(UTC) + timedelta(days=dias)).replace(microsecond=0).isoformat()


async def _crear_escenario(cliente: AsyncClient, sufijo: str = "a") -> dict:
    """Crea un club, dos equipos, jugadores en ambos equipos y un partido iniciado."""
    reg = await cliente.post(
        "/api/seguridad/registro",
        json={
            "nombre_club": f"Club Tracks {sufijo}",
            "email": f"admin_tracks_{sufijo}@test.com",
            "password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    sesion = reg.json()
    auth = _auth(sesion["access_token"])
    club_id = sesion["usuario"]["club_id"]

    eq1 = await cliente.post(
        "/api/deportivo/equipos",
        headers=auth,
        json={"nombre": f"Equipo A {sufijo}", "categoria": "Primera", "temporada": "2026"},
    )
    assert eq1.status_code == 201
    equipo_id = eq1.json()["id"]

    eq2 = await cliente.post(
        "/api/deportivo/equipos",
        headers=auth,
        json={"nombre": f"Equipo Reserva {sufijo}", "categoria": "Sub-20", "temporada": "2026"},
    )
    assert eq2.status_code == 201
    otro_equipo_id = eq2.json()["id"]

    jugadores_ids: list[int] = []
    for dorsal in (9, 10, 11):
        j = await cliente.post(
            "/api/deportivo/jugadores",
            headers=auth,
            json={
                "equipo_id": equipo_id,
                "nombre": f"Jugador{dorsal}",
                "apellido": f"Club{sufijo}",
                "dorsal": dorsal,
                "posicion": "DEL",
                "pie_habil": "DER",
                "altura_cm": 178,
            },
        )
        assert j.status_code == 201, j.text
        jugadores_ids.append(j.json()["id"])

    j_otro_eq = await cliente.post(
        "/api/deportivo/jugadores",
        headers=auth,
        json={
            "equipo_id": otro_equipo_id,
            "nombre": "Juvenil",
            "apellido": "Reserva",
            "dorsal": 7,
            "posicion": "MED",
            "pie_habil": "IZQ",
            "altura_cm": 175,
        },
    )
    assert j_otro_eq.status_code == 201, j_otro_eq.text

    part = await cliente.post(
        "/api/deportivo/partidos",
        headers=auth,
        json={
            "equipo_id": equipo_id,
            "rival": "Rival FC",
            "es_local": True,
            "fecha_hora": _fecha_futura(),
            "sede": "Estadio Hernando Siles",
        },
    )
    assert part.status_code == 201
    partido_id = part.json()["id"]

    cal = await cliente.post(
        f"/api/vision/partidos/{partido_id}/calibracion",
        headers=auth,
        json=cuerpo_valido(),
    )
    assert cal.status_code == 201

    ini = await cliente.post(
        f"/api/partido/{partido_id}/iniciar",
        headers=auth,
        json={"ataca_hacia": "DER"},
    )
    assert ini.status_code == 200

    return {
        "auth": auth,
        "club_id": club_id,
        "equipo_id": equipo_id,
        "otro_equipo_id": otro_equipo_id,
        "jugadores": jugadores_ids,
        "jugador_otro_equipo_id": j_otro_eq.json()["id"],
        "partido_id": partido_id,
    }


async def _auth_rol(cliente: AsyncClient, ctx: dict, rol: str, sufijo: str) -> dict[str, str]:
    email = f"{rol.lower()}_{sufijo}@test.com"
    r = await cliente.post(
        "/api/seguridad/usuarios",
        headers=ctx["auth"],
        json={"email": email, "password": "password123", "rol": rol},
    )
    assert r.status_code == 201, r.text
    login = await cliente.post(
        "/api/seguridad/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _mensaje_worker(
    partido_id: int,
    t: float,
    jugadores: list[tuple[int, str, float]] | None = None,
) -> dict:
    if jugadores is None:
        jugadores = [(i, "LOCAL" if i <= 11 else "VISITANTE", 0.91) for i in range(1, 23)]
    return {
        "partido": partido_id,
        "t": t,
        "jugadores": [
            {"tid": tid, "equipo": eq, "x": 20.0 + tid, "y": 15.0, "conf": conf}
            for tid, eq, conf in jugadores
        ],
        "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 52.5, "y": 34.0, "conf": 0.8},
        "calidad": {
            "worker_conectado": True,
            "fps": 5.0,
            "jugadores_detectados": len(jugadores),
            "balon_visible": True,
            "retraso_s": 0.2,
            "degradado": False,
        },
    }


# ---------------- Asignación, reasignación, oclusión y desasignación ----------------


async def test_primera_asignacion_conserva_desde_t_original(cliente: AsyncClient):
    ctx = await _crear_escenario(cliente, "primera")
    pid = ctx["partido_id"]
    j9 = ctx["jugadores"][0]

    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid, 12.5, [(7, "LOCAL", 0.93)])),
    )

    resp = await cliente.put(
        f"/api/partido/{pid}/tracks/7",
        headers=ctx["auth"],
        json={"jugador_id": j9},
    )
    assert resp.status_code == 200, resp.text
    datos = resp.json()
    assert datos == {
        "track_id": 7,
        "equipo_detectado": "LOCAL",
        "jugador_id": j9,
        "desde_t": 12.5,
        "hasta_t": None,
        "confianza": 0.93,
    }


async def test_reasignacion_a_otro_jugador_cierra_tramo_y_abre_nuevo(cliente: AsyncClient):
    ctx = await _crear_escenario(cliente, "reasig")
    pid = ctx["partido_id"]
    j9, j10, _ = ctx["jugadores"]

    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid, 5.0, [(7, "LOCAL", 0.90)])),
    )

    r1 = await cliente.put(
        f"/api/partido/{pid}/tracks/7",
        headers=ctx["auth"],
        json={"jugador_id": j9},
    )
    assert r1.status_code == 200

    # El worker avanza hasta t = 180.0 s y el analista corrige/reasigna el track 7 a j10
    registrar_t_ingesta(ctx["club_id"], pid, 180.0)
    r2 = await cliente.put(
        f"/api/partido/{pid}/tracks/7",
        headers=ctx["auth"],
        json={"jugador_id": j10},
    )
    assert r2.status_code == 200, r2.text
    nuevo = r2.json()
    assert nuevo["track_id"] == 7
    assert nuevo["jugador_id"] == j10
    assert nuevo["desde_t"] == 180.0
    assert nuevo["hasta_t"] is None

    # Activos: solo el tramo nuevo de j10
    activos = (await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=true", headers=ctx["auth"])).json()
    assert len(activos) == 1
    assert activos[0]["jugador_id"] == j10
    assert activos[0]["desde_t"] == 180.0
    assert activos[0]["hasta_t"] is None

    # Historial completo: tramo cerrado [5.0, 180.0] de j9 y tramo abierto [180.0, None] de j10
    historial = (await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=false", headers=ctx["auth"])).json()
    assert len(historial) == 2
    assert historial[0]["jugador_id"] == j9
    assert historial[0]["desde_t"] == 5.0
    assert historial[0]["hasta_t"] == 180.0
    assert historial[1]["jugador_id"] == j10
    assert historial[1]["desde_t"] == 180.0
    assert historial[1]["hasta_t"] is None


async def test_oclusion_jugador_pasa_del_track_4_al_19_y_conserva_ambos_tramos(
    cliente: AsyncClient,
):
    ctx = await _crear_escenario(cliente, "oclusion")
    pid = ctx["partido_id"]
    j9 = ctx["jugadores"][0]

    # En t = 10.0 aparece el track 4 y se asigna a j9
    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid, 10.0, [(4, "LOCAL", 0.95)])),
    )
    r_inicial = await cliente.put(
        f"/api/partido/{pid}/tracks/4",
        headers=ctx["auth"],
        json={"jugador_id": j9},
    )
    assert r_inicial.status_code == 200

    # Tras una oclusión en t = 240.0, ByteTrack asigna el nuevo track 19 al mismo jugador
    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(
            _mensaje_worker(pid, 240.0, [(4, "LOCAL", 0.95), (19, "LOCAL", 0.89)])
        ),
    )

    # El analista asigna j9 al track 19 en t = 245.0
    registrar_t_ingesta(ctx["club_id"], pid, 245.0)
    r_oclusion = await cliente.put(
        f"/api/partido/{pid}/tracks/19",
        headers=ctx["auth"],
        json={"jugador_id": j9},
    )
    assert r_oclusion.status_code == 200, r_oclusion.text
    tramo_19 = r_oclusion.json()
    assert tramo_19["track_id"] == 19
    assert tramo_19["jugador_id"] == j9
    assert tramo_19["desde_t"] == 240.0
    assert tramo_19["hasta_t"] is None

    # El tramo del track 4 se cerró automáticamente en t = 245.0 y el 19 sigue vigente:
    # j9 conserva sus dos intervalos ([10.0, 245.0] en track 4 y [240.0, None] en track 19)
    historial = (
        await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=false", headers=ctx["auth"])
    ).json()
    assert len(historial) == 2
    assert historial[0] == {
        "track_id": 4,
        "equipo_detectado": "LOCAL",
        "jugador_id": j9,
        "desde_t": 10.0,
        "hasta_t": 245.0,
        "confianza": 0.95,
    }
    assert historial[1] == {
        "track_id": 19,
        "equipo_detectado": "LOCAL",
        "jugador_id": j9,
        "desde_t": 240.0,
        "hasta_t": None,
        "confianza": 0.89,
    }


async def test_desasignar_cierra_tramo_vigente_en_t_actual(
    cliente: AsyncClient, reloj: RelojFalso
):
    ctx = await _crear_escenario(cliente, "desasig")
    pid = ctx["partido_id"]
    j9 = ctx["jugadores"][0]

    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid, 15.0, [(8, "LOCAL", 0.88)])),
    )
    await cliente.put(
        f"/api/partido/{pid}/tracks/8",
        headers=ctx["auth"],
        json={"jugador_id": j9},
    )

    # Sin nuevo mensaje de ingesta pero o con t_ingesta en 95.0, desasignar cierra en 95.0
    registrar_t_ingesta(ctx["club_id"], pid, 95.0)
    resp = await cliente.put(
        f"/api/partido/{pid}/tracks/8",
        headers=ctx["auth"],
        json={"jugador_id": None},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["hasta_t"] == 95.0

    # Ya no aparece entre los tramos activos
    activos = (
        await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=true", headers=ctx["auth"])
    ).json()
    assert activos == []

    # Y en el historial figura cerrado en 95.0
    historial = (
        await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=false", headers=ctx["auth"])
    ).json()
    assert len(historial) == 1
    assert historial[0]["track_id"] == 8
    assert historial[0]["desde_t"] == 15.0
    assert historial[0]["hasta_t"] == 95.0


# ---------------- Validaciones 422, 404, 403 y aislamiento entre clubes ----------------


async def test_jugador_de_otro_equipo_o_de_otro_club_devuelve_422(cliente: AsyncClient):
    ctx_a = await _crear_escenario(cliente, "val_a")
    ctx_b = await _crear_escenario(cliente, "val_b")
    pid_a = ctx_a["partido_id"]

    await registrar_tracks_ingesta(
        ctx_a["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid_a, 1.0, [(3, "LOCAL", 0.9)])),
    )

    # Jugador de otro equipo del mismo club -> 422
    r_otro_eq = await cliente.put(
        f"/api/partido/{pid_a}/tracks/3",
        headers=ctx_a["auth"],
        json={"jugador_id": ctx_a["jugador_otro_equipo_id"]},
    )
    assert r_otro_eq.status_code == 422
    assert "equipo" in r_otro_eq.json()["detail"].lower()

    # Jugador de otro club -> 422
    r_otro_club = await cliente.put(
        f"/api/partido/{pid_a}/tracks/3",
        headers=ctx_a["auth"],
        json={"jugador_id": ctx_b["jugadores"][0]},
    )
    assert r_otro_club.status_code == 422
    assert "club" in r_otro_club.json()["detail"].lower()

    # Jugador inexistente -> 422
    r_inex = await cliente.put(
        f"/api/partido/{pid_a}/tracks/3",
        headers=ctx_a["auth"],
        json={"jugador_id": 999999},
    )
    assert r_inex.status_code == 422


async def test_track_inexistente_en_el_partido_devuelve_404(cliente: AsyncClient):
    ctx = await _crear_escenario(cliente, "no_track")
    pid = ctx["partido_id"]

    r = await cliente.put(
        f"/api/partido/{pid}/tracks/999",
        headers=ctx["auth"],
        json={"jugador_id": ctx["jugadores"][0]},
    )
    assert r.status_code == 404


async def test_roles_put_403_para_dt_y_asistente_y_get_permitido(cliente: AsyncClient):
    ctx = await _crear_escenario(cliente, "roles_trk")
    pid = ctx["partido_id"]
    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid, 2.0, [(5, "LOCAL", 0.91)])),
    )

    auth_analista = await _auth_rol(cliente, ctx, "ANALISTA", "trk")
    auth_dt = await _auth_rol(cliente, ctx, "DT", "trk")
    auth_asistente = await _auth_rol(cliente, ctx, "ASISTENTE", "trk")

    # DT y ASISTENTE reciben 403 en PUT
    for cab in (auth_dt, auth_asistente):
        r_put = await cliente.put(
            f"/api/partido/{pid}/tracks/5",
            headers=cab,
            json={"jugador_id": ctx["jugadores"][0]},
        )
        assert r_put.status_code == 403

        # Pero pueden consultar GET /tracks
        r_get = await cliente.get(f"/api/partido/{pid}/tracks", headers=cab)
        assert r_get.status_code == 200
        assert len(r_get.json()) == 1

    # ANALISTA sí puede ejecutar PUT
    r_ok = await cliente.put(
        f"/api/partido/{pid}/tracks/5",
        headers=auth_analista,
        json={"jugador_id": ctx["jugadores"][0]},
    )
    assert r_ok.status_code == 200


async def test_aislamiento_entre_clubes_devuelve_404(cliente: AsyncClient):
    ctx_a = await _crear_escenario(cliente, "iso_a")
    ctx_b = await _crear_escenario(cliente, "iso_b")
    pid_a = ctx_a["partido_id"]

    await registrar_tracks_ingesta(
        ctx_a["club_id"],
        MensajeWorker.model_validate(_mensaje_worker(pid_a, 3.0, [(6, "LOCAL", 0.9)])),
    )

    r_get = await cliente.get(f"/api/partido/{pid_a}/tracks", headers=ctx_b["auth"])
    assert r_get.status_code == 404

    r_put = await cliente.put(
        f"/api/partido/{pid_a}/tracks/6",
        headers=ctx_b["auth"],
        json={"jugador_id": ctx_b["jugadores"][0]},
    )
    assert r_put.status_code == 404


# ---------------- Restricción de tramo vigente único y cierre al finalizar ----------------


async def test_restriccion_bd_impide_dos_tramos_vigentes_mismo_partido_y_track(
    cliente: AsyncClient,
):
    ctx = await _crear_escenario(cliente, "uq_activo")
    pid = ctx["partido_id"]

    async with SessionLocal() as db:
        t1 = AsignacionTrack(
            club_id=ctx["club_id"],
            partido_id=pid,
            track_id=11,
            jugador_id=None,
            equipo_detectado="LOCAL",
            desde_t=0.0,
            hasta_t=None,
            confianza=0.9,
        )
        db.add(t1)
        await db.commit()

        # Intentar insertar un segundo tramo con hasta_t=None para el mismo (partido_id, track_id)
        t2 = AsignacionTrack(
            club_id=ctx["club_id"],
            partido_id=pid,
            track_id=11,
            jugador_id=None,
            equipo_detectado="LOCAL",
            desde_t=10.0,
            hasta_t=None,
            confianza=0.85,
        )
        db.add(t2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


async def test_finalizar_partido_cierra_tramos_vigentes(
    cliente: AsyncClient, reloj: RelojFalso
):
    ctx = await _crear_escenario(cliente, "fin_trk")
    pid = ctx["partido_id"]

    await registrar_tracks_ingesta(
        ctx["club_id"],
        MensajeWorker.model_validate(
            _mensaje_worker(pid, 20.0, [(1, "LOCAL", 0.92), (2, "VISITANTE", 0.87)])
        ),
    )
    reloj.avanzar(600.0)
    registrar_t_ingesta(ctx["club_id"], pid, 600.0)

    fin = await cliente.post(f"/api/partido/{pid}/finalizar", headers=ctx["auth"])
    assert fin.status_code == 200

    activos = (
        await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=true", headers=ctx["auth"])
    ).json()
    assert activos == []

    historial = (
        await cliente.get(f"/api/partido/{pid}/tracks?solo_activos=false", headers=ctx["auth"])
    ).json()
    assert len(historial) == 2
    assert all(item["hasta_t"] == 600.0 for item in historial)


# ---------------- Gancho en /ingesta, 100 mensajes a 5 Hz y reinicio ----------------


def test_ingesta_100_mensajes_seguidos_con_mismos_tracks_hace_una_sola_escritura(
    reloj: RelojFalso,
):
    """Envía 100 mensajes consecutivos por /ingesta con los mismos 22 tracks y
    verifica que solo el primer mensaje escribe en `asignacion_track` (1 INSERT, no 100).
    """

    async def _db_nullpool():
        async with SesionesPrueba() as session:
            yield session

    hub = HubMemoria()
    app.dependency_overrides[obtener_hub] = lambda: hub
    app.dependency_overrides[get_db] = _db_nullpool
    app.dependency_overrides[obtener_repositorio_partidos] = lambda: PartidosEnTabla(
        Partido, SesionesPrueba
    )
    app.dependency_overrides[obtener_almacen_posiciones] = PosicionesDescartadas

    inserts_tracks: list[int] = []

    def espiar_sql(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO asignacion_track" in statement:
            filas = len(parameters) if executemany else 1
            inserts_tracks.append(filas)

    event.listen(_motor_ingesta.sync_engine, "before_cursor_execute", espiar_sql)

    try:
        with TestClient(app) as tc, ExitStack() as pila:
            reg = tc.post(
                "/api/seguridad/registro",
                json={
                    "nombre_club": "Club Ingesta 100",
                    "email": "admin_ing100@test.com",
                    "password": "password123",
                },
            )
            assert reg.status_code == 201
            sesion = reg.json()
            auth = _auth(sesion["access_token"])
            club_id = sesion["usuario"]["club_id"]

            eq = tc.post(
                "/api/deportivo/equipos",
                headers=auth,
                json={"nombre": "Equipo 100", "categoria": "Primera", "temporada": "2026"},
            )
            part = tc.post(
                "/api/deportivo/partidos",
                headers=auth,
                json={
                    "equipo_id": eq.json()["id"],
                    "rival": "Rival 100",
                    "es_local": True,
                    "fecha_hora": _fecha_futura(),
                    "sede": "Sede 100",
                },
            )
            pid = part.json()["id"]

            # T-033: /ingesta solo acepta partidos EN_CURSO (si no, cierra con 4409)
            cal = tc.post(f"/api/vision/partidos/{pid}/calibracion", headers=auth,
                          json=cuerpo_valido())
            assert cal.status_code == 201, cal.text
            ini = tc.post(f"/api/partido/{pid}/iniciar", headers=auth,
                          json={"ataca_hacia": "IZQ"})
            assert ini.status_code == 200, ini.text

            ws = pila.enter_context(tc.websocket_connect(f"/api/partido/{pid}/ingesta"))
            ws.send_json({"tipo": "auth", "token": token_ingesta(club_id, pid)})
            assert ws.receive_json() == {"tipo": "listo", "partido": pid}

            # 100 mensajes seguidos a 5 Hz con los mismos 22 tracks (incluso si en el
            # mensaje 50 un track cambia de equipo_detectado, no se vuelve a escribir).
            for idx in range(100):
                t = idx * 0.2
                msg = _mensaje_worker(pid, t)
                if idx == 50:
                    msg["jugadores"][0]["equipo"] = "VISITANTE"
                ws.send_json(msg)

            # Verificamos por GET /tracks que los 22 tracks existen y el track 1 conserva LOCAL
            resp_tracks = tc.get(f"/api/partido/{pid}/tracks?solo_activos=true", headers=auth)
            assert resp_tracks.status_code == 200
            lista = resp_tracks.json()
            assert len(lista) == 22
            assert lista[0]["track_id"] == 1
            assert lista[0]["equipo_detectado"] == "LOCAL"
            assert lista[0]["desde_t"] == 0.0

            # Exactamente 1 sentencia INSERT ejecutada (con las 22 filas del mensaje #1), no 100
            assert len(inserts_tracks) == 1
            assert inserts_tracks[0] == 22

            # Si el servidor se reinicia (se pierde el registro en memoria), el siguiente
            # mensaje reconstruye desde la base sin duplicar los 22 existentes y solo inserta el nuevo
            limpiar_memoria_tracks()
            msg_post_reinicio = _mensaje_worker(
                pid, 25.0, [(1, "LOCAL", 0.9), (2, "LOCAL", 0.9), (99, "ARBITRO", 0.85)]
            )
            ws.send_json(msg_post_reinicio)

            resp_post = tc.get(f"/api/partido/{pid}/tracks?solo_activos=false", headers=auth)
            assert resp_post.status_code == 200
            todos = resp_post.json()
            assert len(todos) == 23
            assert len(inserts_tracks) == 2
            assert inserts_tracks[1] == 1
    finally:
        event.remove(_motor_ingesta.sync_engine, "before_cursor_execute", espiar_sql)
        app.dependency_overrides.pop(obtener_hub, None)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(obtener_repositorio_partidos, None)
        app.dependency_overrides.pop(obtener_almacen_posiciones, None)
