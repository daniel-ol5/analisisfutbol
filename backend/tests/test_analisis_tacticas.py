"""Métricas tácticas colectivas por fase  —  T-102 (CU-45).

Altura de línea, amplitud y compacidad separadas en «con balón» y «sin balón».
Criterio de aceptación: el arquero queda excluido del cálculo de la línea defensiva.
"""

from collections.abc import AsyncIterator
from dataclasses import replace

import pytest
from escenarios_analisis import muestra, partido_sintetico
from httpx import ASGITransport, AsyncClient
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, SesionesPrueba, sembrar_partidos

from app.analisis.motor.motor import ContextoPartido, MotorPartido, TramoArquero, sumar_intervalos
from app.analisis.motor.muestras import muestra_de_mensaje
from app.analisis.parametros import PARAMETROS
from app.analisis.vivo import AnalisisEnVivo, reiniciar_analisis_en_vivo
from app.core.security import token_acceso
from app.deportivo.models import Posicion
from app.deportivo.schemas import EstadoPartido
from app.main import app
from app.partido import service as partido_service
from app.partido.service import AnalisisDelProceso, PosicionesEnLote

BASE = "/api/analisis/partidos"

# Local: arquero (tid 1) + 4 defensas en x=20 + 3 medios en x=40.
LOCAL = [(1, "LOCAL", 3.0, 34.0),
         (2, "LOCAL", 20.0, 10.0), (3, "LOCAL", 20.0, 25.0),
         (4, "LOCAL", 20.0, 43.0), (5, "LOCAL", 20.0, 58.0),
         (6, "LOCAL", 40.0, 15.0), (7, "LOCAL", 40.0, 34.0), (8, "LOCAL", 40.0, 53.0)]
# Visitante, en coordenadas crudas (ataca hacia -x): su línea está en x=85.
VISITANTE = [(21, "VISITANTE", 102.0, 34.0),
             (22, "VISITANTE", 85.0, 10.0), (23, "VISITANTE", 85.0, 25.0),
             (24, "VISITANTE", 85.0, 43.0), (25, "VISITANTE", 85.0, 58.0),
             (26, "VISITANTE", 65.0, 15.0), (27, "VISITANTE", 65.0, 34.0),
             (28, "VISITANTE", 65.0, 53.0)]

BALON_CON_LOCAL = (20.5, 25.0)    # a 0,5 m del 3: posee el local
BALON_CON_VISITANTE = (85.5, 25.0)
BALON_LEJOS = (52.5, 66.0)        # a más de 2 m de todos: disputa


def _motor(**kw) -> MotorPartido:
    return MotorPartido(ContextoPartido(partido_id=1), **kw)


def _jugar(motor: MotorPartido, balon, desde: int, hasta: int, jugadores=None) -> None:
    for t in range(desde, hasta):
        motor.procesar(muestra(float(t), jugadores or LOCAL + VISITANTE, balon))


def test_con_balon_y_sin_balon_se_separan_segun_quien_posee():
    motor = _motor()
    _jugar(motor, BALON_CON_LOCAL, 0, 10)           # 10 s: posee el local
    _jugar(motor, BALON_CON_VISITANTE, 10, 14)      # 4 s: posee el visitante
    local = motor.total.equipos["LOCAL"]
    visitante = motor.total.equipos["VISITANTE"]

    assert local.bloque("cb")[3] == 10 and local.bloque("sb")[3] == 4
    assert visitante.bloque("cb")[3] == 4 and visitante.bloque("sb")[3] == 10
    assert local.n_altura == local.n_altura_cb + local.n_altura_sb == 14


def test_disputa_y_balon_no_visible_solo_entran_en_el_total():
    motor = _motor()
    _jugar(motor, BALON_LEJOS, 0, 5)     # disputa
    _jugar(motor, None, 5, 8)            # balón no visible
    local = motor.total.equipos["LOCAL"]
    assert local.n_altura == 8
    assert local.bloque("cb") == (None, None, None, 0)
    assert local.bloque("sb") == (None, None, None, 0)


def test_el_arquero_asignado_se_excluye_en_las_dos_fases():
    motor = _motor(arqueros=[TramoArquero(1, 0.0, None)])
    _jugar(motor, BALON_CON_LOCAL, 0, 5)
    _jugar(motor, BALON_CON_VISITANTE, 5, 10)
    local = motor.total.equipos["LOCAL"]
    # Con el arquero (x=3) la línea sería (3 + 20*3) / 4 = 15,75; sin él, 20.
    assert local.bloque("cb")[0] == pytest.approx(20.0)
    assert local.bloque("sb")[0] == pytest.approx(20.0)
    assert local.bloque("cb")[1] == pytest.approx(58.0 - 10.0)


def test_el_arquero_sin_asignar_se_excluye_por_estar_en_su_area():
    motor = _motor()   # nadie asignado como ARQ: el más retrasado dentro del área
    _jugar(motor, BALON_CON_LOCAL, 0, 5)
    assert motor.total.equipos["LOCAL"].bloque("cb")[0] == pytest.approx(20.0)


def test_el_bloque_se_mide_distinto_con_y_sin_balon():
    motor = _motor(arqueros=[TramoArquero(1, 0.0, None)])
    adelantado = [(t, e, x if t == 1 else x + 15, y) for t, e, x, y in LOCAL]
    _jugar(motor, (35.5, 25.0), 0, 5, adelantado + VISITANTE)   # balón junto al jugador 3
    _jugar(motor, BALON_CON_VISITANTE, 5, 10)
    local = motor.total.equipos["LOCAL"]
    assert local.bloque("cb")[0] == pytest.approx(35.0)
    assert local.bloque("sb")[0] == pytest.approx(20.0)


def _alturas_por_segundo(motor: MotorPartido, segundos: list[list]) -> list[float]:
    """Altura de línea del local en cada segundo (una muestra de bloque por segundo)."""
    local = motor.total.equipos["LOCAL"]
    alturas = []
    for t, jugadores in enumerate(segundos):
        antes = local.suma_altura_m
        motor.procesar(muestra(float(t), jugadores, None))
        alturas.append(local.suma_altura_m - antes)
    return alturas


def _con_defensa_perdido() -> list[list]:
    """Segundos 0-2 con todos a la vista; del 3 al 9 la cámara pierde al defensa 2 (x = 20)."""
    sin_el_2 = [j for j in LOCAL + VISITANTE if j[0] != 2]
    return [LOCAL + VISITANTE] * 3 + [sin_el_2] * 7


def test_la_perdida_transitoria_de_un_defensor_no_hace_saltar_la_linea():
    """CU-45 criterio 3: la línea (4 más retrasados sin arquero) no cambia mientras lo retiene."""
    alturas = _alturas_por_segundo(_motor(arqueros=[TramoArquero(1, 0.0, None)]),
                                   _con_defensa_perdido())
    assert alturas[:6] == [pytest.approx(20.0)] * 6   # visto hasta el 2; retenido hasta el 5


def test_pasada_la_retencion_el_defensor_perdido_deja_de_contar():
    alturas = _alturas_por_segundo(_motor(arqueros=[TramoArquero(1, 0.0, None)]),
                                   _con_defensa_perdido())
    # Sin el 2, los 4 más retrasados son 3, 4, 5 (x = 20) y un medio (x = 40): (60 + 40) / 4.
    assert alturas[6:] == [pytest.approx(25.0)] * 4


def test_sin_suavizado_la_linea_salta_al_perder_al_defensor():
    """Control: con la retención en cero el comportamiento anterior (salto inmediato)."""
    sin_suavizado = replace(PARAMETROS, bloque_retencion_s=0.0)
    alturas = _alturas_por_segundo(
        _motor(p=sin_suavizado, arqueros=[TramoArquero(1, 0.0, None)]), _con_defensa_perdido())
    assert alturas[2] == pytest.approx(20.0) and alturas[3] == pytest.approx(25.0)


def test_el_defensor_retenido_tambien_cuenta_para_amplitud_y_compacidad():
    motor = _motor(arqueros=[TramoArquero(1, 0.0, None)])
    jugadores = _con_defensa_perdido()
    local = motor.total.equipos["LOCAL"]
    areas = []
    for t, js in enumerate(jugadores[:5]):
        antes = local.suma_compacidad_m
        motor.procesar(muestra(float(t), js, None))
        areas.append(local.suma_compacidad_m - antes)
    # El 2 es el defensa de y = 10 (el más abierto): perderlo no encoge el polígono.
    assert areas[4] == pytest.approx(areas[0]) and areas[0] > 0


def test_las_fases_de_los_intervalos_suman_las_del_total():
    motor = _motor()
    for m in partido_sintetico(1, 0, 320):
        motor.procesar(muestra_de_mensaje(m))
    suma = sumar_intervalos(motor.intervalos.values())
    for lado in ("LOCAL", "VISITANTE"):
        assert suma.equipos[lado].n_altura_cb == motor.total.equipos[lado].n_altura_cb
        assert suma.equipos[lado].n_forma_sb == motor.total.equipos[lado].n_forma_sb
    assert motor.total.equipos["LOCAL"].n_altura_cb > 0
    assert motor.total.equipos["LOCAL"].n_altura_sb > 0


# ---------------- Endpoint ----------------

@pytest.fixture(autouse=True)
async def entorno() -> AsyncIterator[None]:
    await sembrar_partidos(EstadoPartido.EN_CURSO)
    partido_service.limpiar_memoria_tracks()
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba))
    yield
    reiniciar_analisis_en_vivo()
    partido_service.limpiar_memoria_tracks()


@pytest.fixture
async def cliente() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(club: int = CLUB_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, club, 'ADMIN')}"}


async def test_endpoint_devuelve_total_con_balon_y_sin_balon(cliente):
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    for m in partido_sintetico(PARTIDO_A, 0, 400):
        await almacen.agregar(m)
        await partido_service.registrar_tracks_ingesta(CLUB_A, m, SesionesPrueba)
    await almacen.vaciar()

    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/tacticas", headers=_auth())
    assert r.status_code == 200, r.text
    datos = r.json()
    local = datos["local"]
    assert local["equipo"] == "LOCAL"
    assert local["con_balon"]["muestras"] > 0 and local["sin_balon"]["muestras"] > 0
    assert local["total"]["muestras"] >= local["con_balon"]["muestras"]
    assert local["con_balon"]["altura_linea_m"] is not None
    assert datos["intervalos"][0]["minuto_desde"] == 0
    assert datos["intervalos"][0]["local"]["con_balon"]["muestras"] > 0

    # Las mismas fases aparecen en CU-42.
    metricas = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas", headers=_auth())).json()
    assert metricas["acumulado_local"]["con_balon"]["muestras"] == local["con_balon"]["muestras"]


async def test_endpoint_sin_datos_devuelve_fases_vacias(cliente):
    datos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/tacticas", headers=_auth())).json()
    assert datos["local"]["con_balon"] == {
        "altura_linea_m": None, "amplitud_m": None, "compacidad_m2": None, "muestras": 0}
    assert datos["intervalos"] == []


# ---------------- Métricas de un minuto exacto (CU-47) ----------------

async def _jugar_partido(hasta: float = 400) -> None:
    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    for m in partido_sintetico(PARTIDO_A, 0, hasta):
        await almacen.agregar(m)
        await partido_service.registrar_tracks_ingesta(CLUB_A, m, SesionesPrueba)
    await almacen.vaciar()


async def test_endpoint_devuelve_las_metricas_del_minuto_pedido(cliente):
    await _jugar_partido()
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/minuto/1", headers=_auth())
    assert r.status_code == 200, r.text
    datos = r.json()
    assert (datos["minuto_desde"], datos["minuto_hasta"]) == (1, 2)
    local, visitante = datos["local"], datos["visitante"]
    assert local["altura_linea_m"] is not None and local["amplitud_m"] > 0
    assert 0 < local["compacidad_m2"] <= 105 * 68          # un área de cancha, en m²
    assert local["con_balon"]["muestras"] + local["sin_balon"]["muestras"] <= 60
    assert round(local["posesion_pct"] + visitante["posesion_pct"]
                 + datos["posesion_disputa_pct"]) == 100


async def test_el_minuto_se_mide_solo_con_sus_posiciones(cliente):
    await _jugar_partido()
    por_minuto = [(await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/minuto/{m}",
                                     headers=_auth())).json() for m in (0, 1, 2)]
    # Cada minuto sale de sus propios 60 s, así que las alturas no son una copia de otra.
    alturas = {round(m["local"]["altura_linea_m"], 2) for m in por_minuto}
    assert len(alturas) > 1
    total = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/tacticas", headers=_auth())).json()
    assert total["local"]["total"]["muestras"] > por_minuto[1]["local"]["con_balon"]["muestras"]


async def test_un_minuto_sin_posiciones_devuelve_vacio(cliente):
    await _jugar_partido(120)
    datos = (await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/minuto/50", headers=_auth())).json()
    assert datos["local"]["altura_linea_m"] is None and datos["local"]["compacidad_m2"] is None
    assert datos["local"]["posesion_pct"] == 0 and datos["posesion_disputa_pct"] == 0


async def test_minuto_invalido_422_y_de_otro_club_404(cliente):
    url = f"{BASE}/{PARTIDO_A}/metricas/minuto"
    assert (await cliente.get(f"{url}/-1", headers=_auth())).status_code == 422
    assert (await cliente.get(f"{url}/999", headers=_auth())).status_code == 422
    assert (await cliente.get(f"{url}/1", headers=_auth(CLUB_B))).status_code == 404


async def test_endpoint_de_otro_club_es_404(cliente):
    r = await cliente.get(f"{BASE}/{PARTIDO_A}/metricas/tacticas", headers=_auth(CLUB_B))
    assert r.status_code == 404
