"""CU-54 (T-092): catálogo de reglas del club.

Criterio de T-092: activar o desactivar una regla surte efecto en el siguiente
partido sin desplegar. Una regla global se activa/desactiva por club: apagarla
en un club no la apaga en los demás.
"""

from datetime import UTC, datetime

import pytest
from escenarios_analisis import BASE_LOCAL, BASE_VISITANTE, mensaje, punto
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, PARTIDO_B, SesionesPrueba, sembrar_partidos
from sqlalchemy import select
from starlette.testclient import TestClient

from app.asistencia import models, service
from app.asistencia.motor import METRICAS_DISPONIBLES, ReglaInvalida, validar_regla
from app.core.security import token_acceso
from app.deportivo.models import Partido, Posicion
from app.main import app
from app.partido import service as partido_service
from app.partido.models import EventoManual, RelojPartido

URL = "/api/asistencia/reglas"

REGLA_NUEVA = {
    "nombre": "Línea muy baja con poca posesión",
    "condicion": {"y": [{"<": ["altura_linea_m", 20]}, {"<": ["posesion_propia_pct", 40]}]},
    "plantilla_mensaje": "Adelantar la línea cuando recuperemos.",
    "plantilla_justificacion": "Línea a {altura_linea_m:.1f} m con {posesion_propia_pct:.0f} % de posesión.",
    "prioridad": "ALTA",
    "cooldown_s": 120,
}


def _auth(club: int = CLUB_A, rol: str = "DT") -> dict[str, str]:
    # En partidos_prueba el usuario `n` es del club `n`.
    return {"Authorization": f"Bearer {token_acceso(club, club, rol)}"}


def _regla(nombre: str, club_id: int | None = None, activa: bool = True) -> models.ReglaTactica:
    return models.ReglaTactica(
        club_id=club_id, nombre=nombre, condicion={">=": ["minuto", 1]},
        plantilla_mensaje=nombre, plantilla_justificacion="Minuto {minuto:.0f}",
        prioridad="MEDIA", cooldown_s=30, activa=activa,
    )


@pytest.fixture
async def catalogo() -> dict[str, int]:
    """Una global, una propia de cada club. Devuelve nombre -> id."""
    await sembrar_partidos()
    reglas = [_regla("Global"), _regla("Propia A", CLUB_A), _regla("Propia B", CLUB_B)]
    async with SesionesPrueba() as db:
        db.add_all(reglas)
        await db.commit()
    return {r.nombre: r.id for r in reglas}


def _por_nombre(respuesta) -> dict[str, dict]:
    return {r["nombre"]: r for r in respuesta.json()}


# ---------- validación de la regla (sin base) ----------

def test_las_reglas_del_catalogo_inicial_usan_solo_metricas_disponibles():
    import json
    from pathlib import Path

    semillas = json.loads((Path(__file__).parents[1] / "alembic/versions/"
                           "c4b7f29a6d10_reglas_iniciales.json").read_text(encoding="utf-8"))
    for s in semillas:
        validar_regla(s["condicion"], s["plantilla_mensaje"], s["plantilla_justificacion"])


@pytest.mark.parametrize(("condicion", "plantilla", "esperado"), [
    ({"<": ["altura_linea", 20]}, "", "altura_linea"),                 # mal escrita
    ({">=": ["minuto", 5]}, "Valor {velocidad_max:.1f}", "velocidad_max"),  # en la plantilla
    ({"entre": ["minuto", 5]}, "", "no soportada"),                    # operador
    ({"<": [1, 2]}, "", "no soportada"),                               # sin métrica
])
def test_validar_regla_rechaza_lo_que_el_motor_no_podria_evaluar(condicion, plantilla, esperado):
    with pytest.raises(ReglaInvalida, match=esperado):
        validar_regla(condicion, "Mensaje", plantilla)


def test_validar_regla_informa_todas_las_metricas_desconocidas_juntas():
    with pytest.raises(ReglaInvalida) as error:
        validar_regla({"o": [{"<": ["uno", 1]}, {"<": ["dos", 2]}]}, "{tres}", "")
    assert "dos, tres, uno" in str(error.value)
    assert "altura_linea_m" in str(error.value)  # lista las disponibles
    assert "minuto" in METRICAS_DISPONIBLES


# ---------- API ----------

def test_listar_muestra_globales_y_propias_del_club(catalogo):
    with TestClient(app) as cliente:
        reglas = _por_nombre(cliente.get(URL, headers=_auth()))
    assert set(reglas) == {"Global", "Propia A"}
    assert reglas["Global"]["club_id"] is None
    assert reglas["Propia A"]["club_id"] == CLUB_A


def test_crear_regla_propia(catalogo):
    with TestClient(app) as cliente:
        respuesta = cliente.post(URL, headers=_auth(rol="ADMIN"), json=REGLA_NUEVA)
        assert respuesta.status_code == 201, respuesta.text
        creada = respuesta.json()
        assert creada["club_id"] == CLUB_A
        assert creada["activa"] is True
        assert creada["prioridad"] == "ALTA"
        assert REGLA_NUEVA["nombre"] in _por_nombre(cliente.get(URL, headers=_auth()))
        # El otro club no la ve.
        assert REGLA_NUEVA["nombre"] not in _por_nombre(cliente.get(URL, headers=_auth(CLUB_B)))


@pytest.mark.parametrize("rol", ["ANALISTA", "ASISTENTE"])
def test_solo_admin_y_dt_gestionan_reglas(catalogo, rol):
    with TestClient(app) as cliente:
        assert cliente.post(URL, headers=_auth(rol=rol), json=REGLA_NUEVA).status_code == 403
        assert cliente.patch(f"{URL}/{catalogo['Global']}", headers=_auth(rol=rol),
                             json={"activa": False}).status_code == 403
        # Ver el catálogo sí puede cualquiera del club.
        assert cliente.get(URL, headers=_auth(rol=rol)).status_code == 200


@pytest.mark.parametrize(("cambio", "fragmento"), [
    ({"condicion": {"<": ["altura_linea", 20]}}, "altura_linea"),
    ({"plantilla_justificacion": "Valor {inexistente:.1f}"}, "inexistente"),
    ({"cooldown_s": 10}, "cooldown_s"),
    ({"nombre": ""}, "nombre"),
    ({"club_id": CLUB_B}, "club_id"),  # no se puede elegir el club
])
def test_crear_regla_invalida_da_422(catalogo, cambio, fragmento):
    with TestClient(app) as cliente:
        respuesta = cliente.post(URL, headers=_auth(), json={**REGLA_NUEVA, **cambio})
    assert respuesta.status_code == 422
    assert fragmento in respuesta.text


def test_editar_regla_propia(catalogo):
    url = f"{URL}/{catalogo['Propia A']}"
    with TestClient(app) as cliente:
        editada = cliente.patch(url, headers=_auth(), json={
            "nombre": "Propia A v2", "prioridad": "CRITICA", "cooldown_s": 600,
        })
        assert editada.status_code == 200, editada.text
        assert editada.json()["nombre"] == "Propia A v2"
        assert editada.json()["prioridad"] == "CRITICA"
        assert editada.json()["condicion"] == {">=": ["minuto", 1]}  # lo no enviado no cambia

        # La validación mira la regla resultante: la plantilla vieja con la condición nueva.
        mala = cliente.patch(url, headers=_auth(), json={"condicion": {"<": ["no_existe", 1]}})
        assert mala.status_code == 422
        assert "no_existe" in mala.text


def test_regla_de_otro_club_o_inexistente_da_404(catalogo):
    with TestClient(app) as cliente:
        assert cliente.patch(f"{URL}/{catalogo['Propia B']}", headers=_auth(),
                             json={"activa": False}).status_code == 404
        assert cliente.patch(f"{URL}/99999", headers=_auth(),
                             json={"activa": False}).status_code == 404


def test_de_una_global_solo_se_cambia_la_activacion(catalogo):
    with TestClient(app) as cliente:
        respuesta = cliente.patch(f"{URL}/{catalogo['Global']}", headers=_auth(),
                                  json={"nombre": "Renombrada"})
    assert respuesta.status_code == 403
    assert "crea una regla propia" in respuesta.json()["detail"]


def test_desactivar_una_global_solo_afecta_al_club(catalogo):
    url = f"{URL}/{catalogo['Global']}"

    async def fila_global():
        async with SesionesPrueba() as db:
            return await db.get(models.ReglaTactica, catalogo["Global"])

    with TestClient(app) as cliente:
        respuesta = cliente.patch(url, headers=_auth(), json={"activa": False})
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["activa"] is False

        assert _por_nombre(cliente.get(URL, headers=_auth()))["Global"]["activa"] is False
        assert _por_nombre(cliente.get(URL, headers=_auth(CLUB_B)))["Global"]["activa"] is True
        # El filtro `activas` usa la activación del club.
        assert "Global" not in _por_nombre(cliente.get(URL + "?activas=true", headers=_auth()))
        assert "Global" in _por_nombre(cliente.get(URL + "?activas=false", headers=_auth()))
        # La fila compartida no se tocó.
        assert cliente.portal.call(fila_global).activa is True

        # Volver a activarla (repite el upsert sobre la misma fila de regla_club).
        assert cliente.patch(url, headers=_auth(), json={"activa": True}).json()["activa"] is True
        assert cliente.patch(url, headers=_auth(), json={"activa": True}).status_code == 200


# ---------- criterio de T-092: efecto en el motor sin desplegar ----------

async def _en_curso() -> None:
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        for partido_id, club_id in ((PARTIDO_A, CLUB_A), (PARTIDO_B, CLUB_B)):
            partido = await db.get(Partido, partido_id)
            partido.es_local = True
            db.add(RelojPartido(club_id=club_id, partido_id=partido_id, parte=1,
                                en_curso=True, inicio_utc=ahora))
        await db.commit()


async def _disparadas(partido_id: int, club_id: int, t: float) -> set[str]:
    async with SesionesPrueba() as db:
        assert await service.evaluar_en_vivo(db, partido_id, club_id, t, {})
        filas = await db.execute(
            select(models.ReglaTactica.nombre).join(models.Recomendacion)
            .where(models.Recomendacion.partido_id == partido_id, models.Recomendacion.t == t))
        return set(filas.scalars())


@pytest.mark.asyncio
async def test_activar_y_desactivar_surte_efecto_en_el_motor_sin_desplegar(catalogo):
    await _en_curso()
    async with SesionesPrueba() as db:
        usuario = service.UsuarioActual(id=CLUB_A, club_id=CLUB_A, rol="DT")
        await service.editar_regla(db, usuario, catalogo["Global"], service.ReglaEditar(activa=False))
        await service.editar_regla(db, usuario, catalogo["Propia A"], service.ReglaEditar(activa=False))

    # Club A: ninguna de sus dos reglas se dispara. Club B sigue con la global.
    assert await _disparadas(PARTIDO_A, CLUB_A, 120) == set()
    assert await _disparadas(PARTIDO_B, CLUB_B, 120) == {"Global", "Propia B"}

    async with SesionesPrueba() as db:
        await service.editar_regla(db, usuario, catalogo["Global"], service.ReglaEditar(activa=True))
    assert await _disparadas(PARTIDO_A, CLUB_A, 180) == {"Global"}


@pytest.mark.asyncio
async def test_recomendaciones_activas_ocultan_las_de_una_global_desactivada_por_el_club(catalogo):
    await _en_curso()
    assert await _disparadas(PARTIDO_A, CLUB_A, 120) == {"Global", "Propia A"}
    usuario = service.UsuarioActual(id=CLUB_A, club_id=CLUB_A, rol="DT")
    async with SesionesPrueba() as db:
        await service.editar_regla(db, usuario, catalogo["Global"], service.ReglaEditar(activa=False))
        activas = await service.listar_recomendaciones(db, usuario, PARTIDO_A, True)
        historial = await service.listar_recomendaciones(db, usuario, PARTIDO_A, False)
    assert [r.mensaje for r in activas] == ["Propia A"]
    assert len(historial) == 2  # el historial no se borra


# ---------- CU-54: probar una regla contra un partido ya registrado ----------

BLOQUE_BAJO = {">=": ["altura_linea_m", 0]}   # se cumple siempre que haya bloque medido
ROJA = {">=": ["rojas_propias", 1]}


def _datos(t: float):
    """Local replegado (línea baja), visitante en su base: 22 jugadores visibles."""
    jugadores = [punto(i, "LOCAL", x * 0.65, y) for i, (x, y) in enumerate(BASE_LOCAL, 1)]
    jugadores += [punto(i, "VISITANTE", x, y) for i, (x, y) in enumerate(BASE_VISITANTE, 12)]
    return mensaje(PARTIDO_A, t, jugadores, (63, 28))


async def _crear(nombre: str, condicion: dict, cooldown_s: int, club_id: int | None = CLUB_A,
                 activa: bool = True) -> int:
    async with SesionesPrueba() as db:
        regla = models.ReglaTactica(
            club_id=club_id, nombre=nombre, condicion=condicion, plantilla_mensaje=nombre,
            prioridad="MEDIA", cooldown_s=cooldown_s, activa=activa)
        db.add(regla)
        await db.commit()
        return regla.id


@pytest.fixture
async def partido_jugado():
    """PARTIDO_A con posiciones guardadas de t=300 a t=420 (minutos 5 y 6) y una roja
    propia en el minuto 6. Una amarilla anulada y una tarjeta del rival no cuentan."""
    await sembrar_partidos()
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        partido = await db.get(Partido, PARTIDO_A)
        partido.es_local = True
        partido.ataca_hacia = "DER"
        for i, (tipo, equipo, minuto, anulado) in enumerate((
            ("ROJA", "LOCAL", 6, False), ("ROJA", "VISITANTE", 5, False),
            ("ROJA", "LOCAL", 5, True),
        )):
            db.add(EventoManual(club_id=CLUB_A, partido_id=PARTIDO_A, uuid=f"t{i}", tipo=tipo,
                                equipo=equipo, minuto=minuto, capturado_en=ahora, creado_por_id=1,
                                anulado_en=ahora if anulado else None))
        await db.commit()

    partido_service.limpiar_memoria_tracks()
    almacen = partido_service.PosicionesEnLote(Posicion, SesionesPrueba)
    for t in range(300, 421):
        datos = _datos(t)
        await almacen.agregar(datos)
        await partido_service.registrar_tracks_ingesta(CLUB_A, datos, SesionesPrueba)
    await almacen.vaciar()
    yield
    partido_service.limpiar_memoria_tracks()


async def _probar(regla_id: int, partido_id: int = PARTIDO_A, club: int = CLUB_A, rol: str = "DT"):
    usuario = service.UsuarioActual(id=club, club_id=club, rol=rol)
    async with SesionesPrueba() as db:
        return await service.probar_regla(db, usuario, regla_id,
                                          service.PruebaRegla(partido_id=partido_id))


@pytest.mark.asyncio
async def test_probar_reproduce_el_partido_y_respeta_el_cooldown(partido_jugado):
    cada_30 = await _probar(await _crear("Bloque cada 30 s", BLOQUE_BAJO, 30))
    una_vez = await _probar(await _crear("Bloque una vez", BLOQUE_BAJO, 3600))

    # 121 s de datos, una evaluación cada 5 s.
    assert 20 <= cada_30.evaluaciones <= 25
    assert una_vez.disparos == 1
    # En ~100 s de bloque medido, con 30 s de espera, se dispara 3 o 4 veces.
    assert 3 <= cada_30.disparos <= 4
    assert cada_30.minutos == sorted(cada_30.minutos)
    assert set(cada_30.minutos) <= {5, 6}


@pytest.mark.asyncio
async def test_probar_cuenta_las_tarjetas_desde_su_minuto(partido_jugado):
    # Solo cuenta la roja propia y vigente del minuto 6: ni la anulada ni la del rival.
    resultado = await _probar(await _crear("Expulsión", ROJA, 3600))
    assert resultado.minutos == [6]


@pytest.mark.asyncio
async def test_se_puede_probar_una_regla_desactivada_y_una_global(partido_jugado):
    desactivada = await _crear("Desactivada", ROJA, 3600, activa=False)
    global_ = await _crear("Global", ROJA, 3600, club_id=None)
    assert (await _probar(desactivada)).minutos == [6]
    assert (await _probar(global_)).minutos == [6]


@pytest.mark.asyncio
async def test_probar_un_partido_sin_posiciones_informa_cero_evaluaciones():
    await sembrar_partidos()
    resultado = await _probar(await _crear("Sin datos", ROJA, 3600))
    assert resultado.disparos == 0 and resultado.evaluaciones == 0


def test_probar_por_api_permisos_y_clubes(catalogo):
    url = f"{URL}/{catalogo['Propia A']}/probar"
    with TestClient(app) as cliente:
        assert cliente.post(url, headers=_auth(), json={"partido_id": PARTIDO_A}).status_code == 200
        assert cliente.post(url, headers=_auth(rol="ANALISTA"),
                            json={"partido_id": PARTIDO_A}).status_code == 403
        # Partido de otro club, regla de otro club o inexistente: 404.
        assert cliente.post(url, headers=_auth(), json={"partido_id": PARTIDO_B}).status_code == 404
        assert cliente.post(f"{URL}/{catalogo['Propia B']}/probar", headers=_auth(),
                            json={"partido_id": PARTIDO_A}).status_code == 404
        assert cliente.post(f"{URL}/99999/probar", headers=_auth(),
                            json={"partido_id": PARTIDO_A}).status_code == 404


def test_contar_disciplina():
    tarjetas = [("AMARILLA", 3), ("AMARILLA", 12), ("ROJA", 20)]
    assert service.contar_disciplina(tarjetas, 2) == {"amarillas_propias_10min": 0, "rojas_propias": 0}
    assert service.contar_disciplina(tarjetas, 12) == {"amarillas_propias_10min": 2, "rojas_propias": 0}
    assert service.contar_disciplina(tarjetas, 13) == {"amarillas_propias_10min": 1, "rojas_propias": 0}
    assert service.contar_disciplina(tarjetas, 20) == {"amarillas_propias_10min": 1, "rojas_propias": 1}
