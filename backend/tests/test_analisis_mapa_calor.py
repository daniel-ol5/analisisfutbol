"""Pruebas del mapa de calor táctico  —  CU-44 · T-079."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import SessionLocal
from app.deportivo.models import Partido
from app.main import app


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
        assert len(data["celdas"]) > 0

        # Verificar rango de valores [0, 1] y coordenadas
        for c_data in data["celdas"]:
            assert 0.0 <= c_data["valor"] <= 1.0
            assert 0.0 <= c_data["x"] <= 105.0
            assert 0.0 <= c_data["y"] <= 68.0


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

        # Por jugador delantero
        res_jugador = await c.get(
            f"/api/analisis/partidos/{partido_id}/mapa-calor?alcance=jugador&referencia_id={jugador_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_jugador.status_code == 200
        assert res_jugador.json()["alcance"] == "jugador"
        assert res_jugador.json()["referencia_id"] == jugador_id


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
