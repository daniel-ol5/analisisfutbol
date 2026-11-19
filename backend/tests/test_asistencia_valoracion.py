"""Valoración, vista y envío en vivo de recomendaciones  —  T-090, T-091 (CU-50, CU-51)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from escenarios_analisis import BASE_LOCAL, BASE_VISITANTE, mensaje, punto
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, SesionesPrueba, sembrar_partidos

from app.analisis.vivo import AnalisisEnVivo, reiniciar_analisis_en_vivo
from app.asistencia import models
from app.asistencia.valoracion import recomendaciones_utiles_pct
from app.core.security import token_acceso
from app.deportivo.models import Posicion
from app.main import app
from app.partido.models import EventoManual, RelojPartido
from app.partido.service import AnalisisDelProceso, PosicionesEnLote, limpiar_memoria_tracks


def _auth(club: int = CLUB_A, rol: str = "DT") -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, club, rol)}"}


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _regla(**kw: Any) -> int:
    async with SesionesPrueba() as db:
        regla = models.ReglaTactica(
            nombre=kw.get("nombre", "Expulsión"), condicion={">=": ["rojas_propias", 1]},
            plantilla_mensaje=kw.get("mensaje", "Reorganiza el bloque"),
            plantilla_justificacion="Rojas: {rojas_propias:.0f}",
            prioridad=kw.get("prioridad", "CRITICA"), cooldown_s=kw.get("cooldown_s", 300),
        )
        db.add(regla)
        await db.commit()
        return regla.id


async def _recomendacion(partido_id: int = PARTIDO_A, t: float = 100.0, **kw: Any) -> int:
    regla_id = kw.pop("regla_id", None) or await _regla()
    async with SesionesPrueba() as db:
        rec = models.Recomendacion(
            partido_id=partido_id, regla_id=regla_id, t=t, minuto=int(t // 60),
            mensaje="Reorganiza el bloque", justificacion="Rojas: 1", prioridad="CRITICA",
            datos_soporte=[{"metrica": "rojas_propias", "valor": 1, "umbral": 1}], **kw,
        )
        db.add(rec)
        await db.commit()
        return rec.id


@pytest.fixture(autouse=True)
async def partidos() -> None:
    await sembrar_partidos()


# ---------------- T-091 · Valorar ----------------

async def test_util_queda_vista_y_activa(cliente):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/valorar",
                           json={"util": True, "comentario": "  Sirvió para cerrar el medio  "},
                           headers=_auth())
    assert r.status_code == 200, r.text
    datos = r.json()
    assert (datos["estado"], datos["util"]) == ("VISTA", True)
    assert datos["comentario"] == "Sirvió para cerrar el medio"
    assert datos["vista_en"] is not None
    activas = (await cliente.get(f"/api/asistencia/partidos/{PARTIDO_A}/recomendaciones",
                                 headers=_auth())).json()
    assert [a["id"] for a in activas] == [rec]


async def test_no_util_queda_descartada_y_sale_de_las_activas(cliente):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/valorar",
                           json={"util": False}, headers=_auth())
    assert (r.json()["estado"], r.json()["util"], r.json()["comentario"]) == (
        "DESCARTADA", False, None)
    activas = (await cliente.get(f"/api/asistencia/partidos/{PARTIDO_A}/recomendaciones",
                                 headers=_auth())).json()
    assert activas == []


@pytest.mark.parametrize(("cuerpo", "util"), [
    ({"aplicada": True}, True),                    # aplicada sin indicar: útil
    ({"aplicada": True, "util": False}, False),   # aplicada, pero no sirvió
])
async def test_aplicada_sale_de_las_activas(cliente, cuerpo, util):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/valorar",
                           json=cuerpo, headers=_auth(rol="ANALISTA"))
    assert (r.json()["estado"], r.json()["util"]) == ("APLICADA", util)
    activas = (await cliente.get(f"/api/asistencia/partidos/{PARTIDO_A}/recomendaciones",
                                 headers=_auth())).json()
    assert activas == []


async def test_la_segunda_valoracion_responde_409(cliente):
    rec = await _recomendacion()
    url = f"/api/asistencia/recomendaciones/{rec}/valorar"
    assert (await cliente.post(url, json={"util": True}, headers=_auth())).status_code == 200
    r = await cliente.post(url, json={"util": False}, headers=_auth())
    assert r.status_code == 409
    async with SesionesPrueba() as db:
        assert (await db.get(models.Recomendacion, rec)).util is True


async def test_sin_util_ni_aplicada_responde_422(cliente):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/valorar",
                           json={"comentario": "?"}, headers=_auth())
    assert r.status_code == 422


async def test_comentario_de_mas_de_400_caracteres_responde_422(cliente):
    rec = await _recomendacion()
    url = f"/api/asistencia/recomendaciones/{rec}/valorar"
    r = await cliente.post(url, json={"util": True, "comentario": "x" * 401}, headers=_auth())
    assert r.status_code == 422
    r = await cliente.post(url, json={"util": True, "comentario": "x" * 400}, headers=_auth())
    assert r.status_code == 200


@pytest.mark.parametrize("ruta", ["valorar", "vista"])
async def test_otro_club_recibe_404(cliente, ruta):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/{ruta}",
                           json={"util": True}, headers=_auth(CLUB_B))
    assert r.status_code == 404
    r = await cliente.post(f"/api/asistencia/recomendaciones/999999/{ruta}",
                           json={"util": True}, headers=_auth())
    assert r.status_code == 404


@pytest.mark.parametrize("ruta", ["valorar", "vista"])
async def test_el_asistente_no_puede_valorar_ni_marcar(cliente, ruta):
    rec = await _recomendacion()
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/{ruta}",
                           json={"util": True}, headers=_auth(rol="ASISTENTE"))
    assert r.status_code == 403


# ---------------- T-091 · Porcentaje de útiles (para el informe) ----------------

async def test_porcentaje_de_utiles_sobre_las_valoradas():
    regla = await _regla()
    for t, util in ((10, True), (20, True), (30, False), (40, None), (50, None)):
        await _recomendacion(t=t, util=util, regla_id=regla)
    await _recomendacion(partido_id=20, t=10, util=False, regla_id=regla)   # otro partido
    async with SesionesPrueba() as db:
        assert await recomendaciones_utiles_pct(db, PARTIDO_A) == pytest.approx(66.7)
        assert await recomendaciones_utiles_pct(db, 20) == 0.0


async def test_porcentaje_sin_valoradas_es_none():
    await _recomendacion(util=None)
    async with SesionesPrueba() as db:
        assert await recomendaciones_utiles_pct(db, PARTIDO_A) is None
        assert await recomendaciones_utiles_pct(db, 999) is None


# ---------------- T-090 · Marcar vista ----------------

async def test_marcar_vista_es_idempotente(cliente):
    rec = await _recomendacion()
    url = f"/api/asistencia/recomendaciones/{rec}/vista"
    primera = (await cliente.post(url, headers=_auth())).json()
    assert primera["estado"] == "VISTA" and primera["vista_en"] is not None
    segunda = (await cliente.post(url, headers=_auth())).json()
    assert segunda["vista_en"] == primera["vista_en"]


async def test_marcar_vista_no_reabre_una_valorada(cliente):
    rec = await _recomendacion()
    await cliente.post(f"/api/asistencia/recomendaciones/{rec}/valorar",
                       json={"util": False}, headers=_auth())
    r = await cliente.post(f"/api/asistencia/recomendaciones/{rec}/vista", headers=_auth())
    assert r.json()["estado"] == "DESCARTADA"


# ---------------- T-090 · Envío por /vivo ----------------

class HubGrabador:
    def __init__(self) -> None:
        self.mensajes: list[tuple[str, dict[str, Any]]] = []

    async def suscribir(self, canal, ws) -> None: ...

    async def desuscribir(self, canal, ws) -> None: ...

    async def difundir(self, canal: str, mensaje: dict[str, Any]) -> None:
        self.mensajes.append((canal, mensaje))

    async def conectados(self, canal: str) -> int:
        return 1

    def recomendaciones(self) -> list[dict[str, Any]]:
        return [m["datos"] for _, m in self.mensajes if m["tipo"] == "recomendacion"]


def _muestra(t: float):
    jugadores = [punto(i, "LOCAL", x * 0.65, y) for i, (x, y) in enumerate(BASE_LOCAL, 1)]
    jugadores += [punto(i, "VISITANTE", x, y) for i, (x, y) in enumerate(BASE_VISITANTE, 12)]
    datos = mensaje(PARTIDO_A, t, jugadores, (63, 28))
    datos.calidad.calibracion_valida = True
    return datos


async def test_una_recomendacion_nueva_sale_por_vivo():
    """Una roja propia dispara la regla CRITICA y la recomendación se difunde en el acto."""
    hub = HubGrabador()
    ahora = datetime.now(UTC)
    critica = await _regla()
    baja = await _regla(nombre="Otra", mensaje="Mantén la calma", prioridad="BAJA")
    async with SesionesPrueba() as db:
        db.add(RelojPartido(club_id=CLUB_A, partido_id=PARTIDO_A, parte=1,
                            en_curso=True, inicio_utc=ahora))
        db.add(EventoManual(club_id=CLUB_A, partido_id=PARTIDO_A, uuid="roja", tipo="ROJA",
                            equipo="LOCAL", minuto=1, capturado_en=ahora, creado_por_id=1))
        await db.commit()
    analisis = AnalisisEnVivo(sesiones=SesionesPrueba, hub=hub)
    reiniciar_analisis_en_vivo(analisis)
    limpiar_memoria_tracks()
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    try:
        for t in (100.0, 100.2, 106.0):
            datos = _muestra(t)
            await almacen.agregar(datos)
            await analisis.evaluar_reglas(CLUB_A, datos)
    finally:
        await almacen.vaciar()
        reiniciar_analisis_en_vivo()

    enviadas = hub.recomendaciones()
    # La primera evaluación crea las dos; la de t=106 queda dentro del cooldown (300 s).
    assert [r["regla_id"] for r in enviadas] == [critica, baja]   # por prioridad
    assert enviadas[0]["prioridad"] == "CRITICA"
    assert enviadas[0]["mensaje"] == "Reorganiza el bloque"
    assert enviadas[0]["datos_soporte"] == [{"metrica": "rojas_propias", "valor": 1.0,
                                            "umbral": 1.0}]
    assert {c for c, m in hub.mensajes if m["tipo"] == "recomendacion"} == {
        f"club:{CLUB_A}:partido:{PARTIDO_A}"}
    async with SesionesPrueba() as db:
        assert len((await db.execute(
            models.Recomendacion.__table__.select())).all()) == 2
