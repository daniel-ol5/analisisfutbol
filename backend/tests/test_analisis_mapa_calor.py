"""Pruebas del mapa de calor táctico  —  CU-44 · T-079."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import SessionLocal
from app.deportivo.models import Partido, Posicion
from app.main import app
from app.partido.models import AsignacionTrack
from app.vision import procesamiento
from app.vision.models import Video


@pytest.fixture
async def datos_prueba():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Registrar Club 1
        reg1 = await c.post(
            "/api/seguridad/registro",
            json={
                "nombre_club": "Club Uno",
                "email": "admin1@test.com",
                "password": "password123",
            },
        )
        assert reg1.status_code == 201
        token1 = reg1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Equipo 1
        eq1 = await c.post(
            "/api/deportivo/equipos",
            headers=headers1,
            json={"nombre": "Equipo Uno", "categoria": "Primera", "temporada": "2026"},
        )
        equipo_id1 = eq1.json()["id"]

        # Jugador 1 (Delantero)
        jug1 = await c.post(
            "/api/deportivo/jugadores",
            headers=headers1,
            json={
                "equipo_id": equipo_id1,
                "nombre": "Delantero",
                "apellido": "Estrella",
                "dorsal": 9,
                "posicion": "DEL",
                "altura_cm": 180,
            },
        )
        assert jug1.status_code == 201, jug1.text
        jugador_id1 = jug1.json()["id"]

        # Competicion 1
        comp1 = await c.post(
            "/api/deportivo/competiciones",
            headers=headers1,
            json={"nombre": "Liga 1", "temporada": "2026"},
        )
        comp_id1 = comp1.json()["id"]

        # Partido 1
        partido1 = await c.post(
            "/api/deportivo/partidos",
            headers=headers1,
            json={
                "equipo_id": equipo_id1,
                "rival": "Club Rival",
                "es_local": True,
                "fecha_hora": "2026-12-01T15:00:00Z",
                "sede": "Estadio Uno",
                "competicion_id": comp_id1,
            },
        )
        partido_id1 = partido1.json()["id"]

        # Establecer ataca_hacia = 'DER'
        async with SessionLocal() as db:
            p = await db.get(Partido, partido_id1)
            p.ataca_hacia = "DER"
            db.add_all([
                AsignacionTrack(club_id=p.club_id, partido_id=p.id, track_id=21,
                                equipo_detectado="LOCAL", jugador_id=jugador_id1),
                AsignacionTrack(club_id=p.club_id, partido_id=p.id, track_id=22,
                                equipo_detectado="VISITANTE"),
                Posicion(partido_id=p.id, track_id=21, t=12, x_m=82, y_m=16),
                Posicion(partido_id=p.id, track_id=21, t=2700, x_m=23, y_m=52),
                Posicion(partido_id=p.id, track_id=22, t=12, x_m=25, y_m=30),
                Posicion(partido_id=p.id, track_id=0, t=12, x_m=50, y_m=40, es_balon=True),
            ])
            await db.commit()

        # Registrar Club 2 (para probar aislamiento multi-tenant)
        reg2 = await c.post(
            "/api/seguridad/registro",
            json={
                "nombre_club": "Club Dos",
                "email": "admin2@test.com",
                "password": "password123",
            },
        )
        token2 = reg2.json()["access_token"]

        return {
            "token1": token1,
            "token2": token2,
            "partido_id": partido_id1,
            "jugador_id": jugador_id1,
        }


@pytest.mark.asyncio
async def test_mapa_calor_equipo_completo(datos_prueba):
    """CU-44: Genera mapa de calor para equipo completo."""
    transport = ASGITransport(app=app)
    token = datos_prueba["token1"]
    partido_id = datos_prueba["partido_id"]

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?alcance=equipo&desde_minuto=0&hasta_minuto=90",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["partido_id"] == partido_id
        assert data["alcance"] == "equipo"
        assert data["largo_m"] == 105.0
        assert data["ancho_m"] == 68.0
        assert data["celdas"] == [{"x": 82.5, "y": 17.0, "valor": 1.0}]

        vacio = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?desde_minuto=50&hasta_minuto=90",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert vacio.status_code == 200
        assert vacio.json()["celdas"] == []

        # Verificar rango de valores [0, 1] y coordenadas
        for c_data in data["celdas"]:
            assert 0.0 <= c_data["valor"] <= 1.0
            assert 0.0 <= c_data["x"] <= 105.0
            assert 0.0 <= c_data["y"] <= 68.0


@pytest.mark.asyncio
async def test_mapa_de_grabacion_usa_solo_sus_muestras_validas(datos_prueba, tmp_path, monkeypatch):
    partido_id = datos_prueba["partido_id"]
    async with SessionLocal() as db:
        partido = await db.get(Partido, partido_id)
        db.add(Video(club_id=partido.club_id, partido_id=partido_id, archivo_url="clip.mp4",
                     nombre="clip.mp4", tipo="video/mp4", tamano_bytes=100, estado="PROCESADO"))
        await db.commit()

    ruta = tmp_path / "muestras.json"
    calidad = {"worker_conectado": True, "fps": 5, "jugadores_detectados": 1,
               "balon_visible": False, "retraso_s": 0, "degradado": False}
    ruta.write_text(json.dumps([
        {"partido": partido_id, "t": t, "jugadores": [
            {"tid": 21, "equipo": "LOCAL", "x": x, "y": 32, "conf": .9},
        ], "calidad": {**calidad, "calibracion_valida": valida}}
        for t, x, valida in [(0, 43, True), (1, 55, False)]
    ]), encoding="utf-8")
    monkeypatch.setattr(procesamiento, "_ruta_muestras_video", lambda _: ruta)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/api/analisis/partidos/{partido_id}/mapa-calor",
                          headers={"Authorization": f"Bearer {datos_prueba['token1']}"})
    assert res.status_code == 200, res.text
    assert res.json()["celdas"] == [{"x": 42.5, "y": 31.57, "valor": 1.0}]


@pytest.mark.asyncio
async def test_jugador_inexistente_y_de_otro_club_responden_igual_404(datos_prueba):
    """T-105: no se revela si un jugador existe en otro club."""
    partido_id = datos_prueba["partido_id"]
    club1 = {"Authorization": f"Bearer {datos_prueba['token1']}"}
    club2 = {"Authorization": f"Bearer {datos_prueba['token2']}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        equipo = await c.post("/api/deportivo/equipos", headers=club2, json={
            "nombre": "Equipo Dos", "categoria": "Primera", "temporada": "2026"})
        ajeno = await c.post("/api/deportivo/jugadores", headers=club2, json={
            "equipo_id": equipo.json()["id"], "nombre": "Otro", "apellido": "Club",
            "dorsal": 7, "posicion": "DEL", "altura_cm": 180})
        assert ajeno.status_code == 201, ajeno.text

        def url(jugador_id: int) -> str:
            return (f"/api/analisis/partidos/{partido_id}/mapa-calor"
                    f"?alcance=jugador&referencia_id={jugador_id}")

        inexistente = await c.get(url(999999), headers=club1)
        de_otro_club = await c.get(url(ajeno.json()["id"]), headers=club1)
    assert inexistente.status_code == de_otro_club.status_code == 404
    assert inexistente.json() == de_otro_club.json()


@pytest.mark.asyncio
async def test_mapa_calor_linea_y_jugador(datos_prueba):
    """CU-44: Genera mapa de calor filtrado por línea o jugador individual."""
    transport = ASGITransport(app=app)
    token = datos_prueba["token1"]
    partido_id = datos_prueba["partido_id"]
    jugador_id = datos_prueba["jugador_id"]

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Por línea ofensiva (3)
        res_linea = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?alcance=linea&referencia_id=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_linea.status_code == 200
        assert res_linea.json()["alcance"] == "linea"
        assert len(res_linea.json()["celdas"]) == 1

        # Por jugador delantero
        res_jugador = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?alcance=jugador&referencia_id={jugador_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_jugador.status_code == 200
        assert res_jugador.json()["alcance"] == "jugador"
        assert res_jugador.json()["referencia_id"] == jugador_id
        assert res_jugador.json()["celdas"] == res_linea.json()["celdas"]


@pytest.mark.asyncio
async def test_mapa_calor_criterio_no_simetrico(datos_prueba):
    """CU-44 / T-079 Criterio de aceptación:

    Un partido completo no queda simétrico por el cambio de lado en el entretiempo,
    ya que las coordenadas se normalizan por 'ataca_hacia'.
    """
    transport = ASGITransport(app=app)
    token = datos_prueba["token1"]
    partido_id = datos_prueba["partido_id"]

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?alcance=equipo&desde_minuto=0&hasta_minuto=90",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        celdas = res.json()["celdas"]

        # Sumar densidad en la mitad izquierda (x < 52.5) vs mitad derecha (x >= 52.5)
        densidad_propia = sum(c["valor"] for c in celdas if c["x"] < 52.5)
        densidad_ataque = sum(c["valor"] for c in celdas if c["x"] >= 52.5)

        # La normalización ofensiva garantiza que el ataque esté orientado a la derecha,
        # por lo que ambas mitades no son idénticas / simétricas
        assert abs(densidad_ataque - densidad_propia) > 0.01


@pytest.mark.asyncio
async def test_mapa_calor_aislamiento_clubes(datos_prueba):
    """CU-44: Acceso a partido de otro club devuelve 404."""
    transport = ASGITransport(app=app)
    token_club2 = datos_prueba["token2"]
    partido_id = datos_prueba["partido_id"]

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor",
            headers={"Authorization": f"Bearer {token_club2}"},
        )
        assert res.status_code == 404
