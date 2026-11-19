"""CU-52 (HU-46, T-095): alertas de fatiga y de riesgo de expulsión.

Criterios:
- HU-46.1: fatiga si el jugador supera el 120 % del promedio de distancia o su
  velocidad máxima desciende un 25 % respecto al primer tiempo.
- HU-46.2: riesgo de expulsión para amonestados si el partido entra en fase de fricción.
- T-095: no se genera alerta de fatiga para jugadores que entraron hace menos de 15 minutos.
"""

from datetime import UTC, datetime

import pytest
from partidos_prueba import CLUB_A, CLUB_B, PARTIDO_A, SesionesPrueba, sembrar_partidos
from starlette.testclient import TestClient

from app.analisis.schemas import MetricasJugadorPorIntervalo
from app.asistencia import service
from app.asistencia.alertas import (
    Bloque,
    Jugador,
    alertas_expulsion,
    alertas_fatiga,
    ordenar,
    tarjetas_recientes,
)
from app.asistencia.schemas import TipoAlerta
from app.core.security import token_acceso
from app.deportivo.models import Jugador as Ficha
from app.deportivo.models import Partido
from app.main import app
from app.partido.models import EventoManual


def _bloque(desde: int, ritmo: float, vmax: float = 28.0, minutos: float = 5.0) -> Bloque:
    return Bloque(desde, desde + 5, ritmo * minutos, vmax, minutos)


def _bloques(ritmos: dict[int, float], desde: int = 20) -> dict[int, list[Bloque]]:
    return {jid: [_bloque(desde, r)] for jid, r in ritmos.items()}


def _ids(alertas) -> list[int]:
    return [a.jugador_id for a in alertas]


# ---------- HU-46.1 · distancia ----------

def test_fatiga_por_superar_el_120_del_promedio_de_distancia():
    # Promedio (100 + 100 + 100 + 140) / 4 = 110; el umbral es 132 m/min.
    alertas = alertas_fatiga(_bloques({1: 100, 2: 100, 3: 100, 4: 140}), {}, minuto=25)
    assert _ids(alertas) == [4]
    alerta = alertas[0]
    assert alerta.tipo == TipoAlerta.FATIGA
    assert "127 % del promedio" in alerta.justificacion
    assert alerta.datos_soporte[0].metrica == "ritmo_m_min"
    assert alerta.datos_soporte[0].umbral == 132.0


def test_por_debajo_del_120_no_hay_alerta():
    # Promedio 106,25; el umbral es 127,5 m/min.
    assert alertas_fatiga(_bloques({1: 100, 2: 100, 3: 100, 4: 125}), {}, minuto=25) == []


def test_se_compara_solo_el_ultimo_bloque_cerrado():
    bloques = {1: [_bloque(15, 200), _bloque(20, 100)], 2: [_bloque(15, 100), _bloque(20, 100)],
               3: [_bloque(15, 100), _bloque(20, 100)]}
    assert alertas_fatiga(bloques, {}, minuto=25) == []


def test_ritmo_en_metros_por_minuto_para_quien_jugo_parte_del_bloque():
    # 3 min en cancha y 420 m: 140 m/min, aunque haya recorrido menos metros que el resto.
    bloques = _bloques({1: 100, 2: 100, 3: 100})
    bloques[4] = [_bloque(20, 140, minutos=3)]
    assert _ids(alertas_fatiga(bloques, {}, minuto=25)) == [4]


def test_sin_suficientes_datos_no_hay_promedio():
    # Menos de 2 minutos en el bloque no da un ritmo fiable; con 2 jugadores no hay promedio.
    corto = _bloques({1: 100, 2: 100, 3: 100})
    corto[4] = [_bloque(20, 300, minutos=1)]
    assert alertas_fatiga(corto, {}, minuto=25) == []
    assert alertas_fatiga(_bloques({1: 100, 2: 200}), {}, minuto=25) == []


# ---------- HU-46.1 · velocidad máxima ----------

def _con_velocidad(vmax_segundo: float) -> dict[int, list[Bloque]]:
    primer_tiempo = [_bloque(30, 100, vmax=30.0), _bloque(40, 100, vmax=26.0)]
    bloques = {jid: [*primer_tiempo, _bloque(60, 100)] for jid in (2, 3, 4)}
    bloques[1] = [*primer_tiempo, _bloque(60, 100, vmax=vmax_segundo)]
    return bloques


def test_fatiga_por_caida_del_25_de_la_velocidad_maxima():
    alertas = alertas_fatiga(_con_velocidad(22.0), {}, minuto=65)   # 26,7 % menos que 30
    assert _ids(alertas) == [1]
    assert "27 % menos que en el primer tiempo (30.0 km/h)" in alertas[0].justificacion
    assert alertas[0].datos_soporte[0].umbral == 22.5


def test_caida_menor_al_25_no_alerta():
    assert alertas_fatiga(_con_velocidad(23.0), {}, minuto=65) == []   # 23,3 %


def test_la_velocidad_solo_se_compara_en_el_segundo_tiempo():
    bloques = {jid: [_bloque(10, 100, vmax=30.0), _bloque(20, 100, vmax=15.0)] for jid in (1, 2, 3)}
    assert alertas_fatiga(bloques, {}, minuto=25) == []


def test_los_dos_motivos_van_en_una_sola_alerta():
    bloques = _con_velocidad(20.0)
    bloques[1][-1] = _bloque(60, 160, vmax=20.0)
    (alerta,) = alertas_fatiga(bloques, {}, minuto=65)
    assert " y su velocidad máxima bajó" in alerta.justificacion
    assert len(alerta.datos_soporte) == 2


# ---------- T-095 · menos de 15 minutos en cancha ----------

@pytest.mark.parametrize(("minuto", "alerta"), [(74, False), (75, True)])
def test_no_hay_alerta_de_fatiga_para_quien_entro_hace_menos_de_15_minutos(minuto, alerta):
    bloques = _bloques({1: 100, 2: 100, 3: 100, 4: 140}, desde=65)
    suplente = {4: Jugador(4, entro_min=60)}
    assert _ids(alertas_fatiga(bloques, suplente, minuto)) == ([4] if alerta else [])


def test_sin_alerta_para_quien_ya_no_esta_en_cancha():
    bloques = _bloques({1: 100, 2: 100, 3: 100, 4: 140})
    assert alertas_fatiga(bloques, {4: Jugador(4, en_cancha=False)}, minuto=25) == []


# ---------- HU-46.2 · riesgo de expulsión ----------

def test_fase_de_friccion_cuenta_tarjetas_de_los_ultimos_10_minutos():
    tarjetas = [("AMARILLA", 30), ("ROJA", 35), ("AMARILLA", 39)]
    assert tarjetas_recientes(tarjetas, 39) == 3
    assert tarjetas_recientes(tarjetas, 40) == 2    # la del 30 queda fuera
    assert tarjetas_recientes(tarjetas, 45) == 1


def test_amonestado_en_fase_de_friccion():
    jugadores = {8: Jugador(8, "Pérez", 8, amarillas=1), 5: Jugador(5, "Gómez", 5),
                 9: Jugador(9, "Ruiz", 9, amarillas=1, en_cancha=False)}
    alertas = alertas_expulsion(jugadores, [("AMARILLA", 30), ("AMARILLA", 33)], minuto=35)
    assert _ids(alertas) == [8]   # sin amarilla, o ya fuera de la cancha: nada
    assert alertas[0].tipo == TipoAlerta.RIESGO_EXPULSION
    assert alertas[0].mensaje.startswith("#8 Pérez está amonestado")
    assert alertas[0].prioridad == "ALTA"


def test_sin_friccion_no_hay_riesgo_de_expulsion():
    jugadores = {8: Jugador(8, amarillas=1)}
    assert alertas_expulsion(jugadores, [("AMARILLA", 30)], minuto=35) == []
    assert alertas_expulsion(jugadores, [("AMARILLA", 20), ("AMARILLA", 22)], minuto=35) == []


def test_orden_mas_urgente_primero_y_por_dorsal():
    fatiga = alertas_fatiga(_bloques({1: 100, 2: 100, 3: 100, 4: 140}),
                            {4: Jugador(4, dorsal=4)}, minuto=25)
    riesgo = alertas_expulsion({10: Jugador(10, dorsal=10, amarillas=1),
                                7: Jugador(7, dorsal=7, amarillas=1)},
                               [("AMARILLA", 20), ("ROJA", 22)], minuto=25)
    assert [(a.tipo, a.dorsal) for a in ordenar([*fatiga, *riesgo])] == [
        (TipoAlerta.RIESGO_EXPULSION, 7), (TipoAlerta.RIESGO_EXPULSION, 10), (TipoAlerta.FATIGA, 4),
    ]


# ---------- API: eventos reales y métricas por jugador ----------

def _auth(club: int = CLUB_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(club, club, 'DT')}"}


def _metricas(ritmos: dict[int, float], desde: int):
    return [MetricasJugadorPorIntervalo(jugador_id=jid, intervalos=[{
        "minuto_desde": desde, "minuto_hasta": desde + 5, "distancia_m": 5 * r,
        "velocidad_max_kmh": 28.0, "sprints": 0, "minutos_jugados": 5.0,
    }]) for jid, r in ritmos.items()]


@pytest.fixture
async def partido_con_eventos(monkeypatch):
    """Minuto 70. Sale el 101 y entra el 104 en el 60; amarilla del 102 en el 62 y roja
    del rival en el 66 (fricción: 2 tarjetas en 10 min). En el bloque 65-70 el 103 y el
    104 (recién entrado) van a 150 m/min."""
    await sembrar_partidos()
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        partido = await db.get(Partido, PARTIDO_A)
        partido.es_local = True
        partido.minuto_actual = 70
        for jid, apellido in ((101, "Sale"), (102, "Amonestado"), (103, "Cansado"), (104, "Suplente"),
                              (105, "Normal")):
            db.add(Ficha(id=jid, club_id=CLUB_A, equipo_id=CLUB_A, nombre="J", apellido=apellido,
                         dorsal=jid - 100, posicion="MED", altura_cm=175))
        await db.flush()
        for i, (tipo, equipo, jugador, entra, minuto) in enumerate((
            ("SUSTITUCION", "LOCAL", 101, 104, 60),
            ("AMARILLA", "LOCAL", 102, None, 62),
            ("ROJA", "VISITANTE", None, None, 66),
            ("AMARILLA", "LOCAL", 105, None, 10),   # anulada: no cuenta
        )):
            db.add(EventoManual(club_id=CLUB_A, partido_id=PARTIDO_A, uuid=f"a{i}", tipo=tipo,
                                equipo=equipo, jugador_id=jugador, jugador_entra_id=entra,
                                minuto=minuto, capturado_en=ahora, creado_por_id=CLUB_A,
                                anulado_en=ahora if i == 3 else None))
        await db.commit()

    async def metricas(_db, _usuario, partido_id, equipo):
        assert (partido_id, equipo) == (PARTIDO_A, "LOCAL")   # solo los jugadores propios
        return _metricas({102: 100, 103: 150, 104: 150, 105: 100, 101: 100}, desde=65)

    monkeypatch.setattr(service, "metricas_jugadores_intervalos", metricas)


def test_api_alertas_del_partido(partido_con_eventos):
    with TestClient(app) as cliente:
        respuesta = cliente.get(f"/api/asistencia/partidos/{PARTIDO_A}/alertas", headers=_auth())
    assert respuesta.status_code == 200, respuesta.text
    alertas = [(a["tipo"], a["jugador_id"], a["dorsal"], a["nombre"]) for a in respuesta.json()]
    # 102: amonestado con fricción. 103: fatiga. 104 entró hace 10 min y 101 ya salió: nada.
    assert alertas == [("RIESGO_EXPULSION", 102, 2, "Amonestado"), ("FATIGA", 103, 3, "Cansado")]
    assert respuesta.json()[1]["minuto"] == 70


def test_api_alertas_de_otro_club_da_404(partido_con_eventos):
    with TestClient(app) as cliente:
        r = cliente.get(f"/api/asistencia/partidos/{PARTIDO_A}/alertas", headers=_auth(CLUB_B))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_partido_sin_metricas_no_tiene_alertas():
    await sembrar_partidos()
    usuario = service.UsuarioActual(id=CLUB_A, club_id=CLUB_A, rol="DT")
    async with SesionesPrueba() as db:
        assert await service.alertas_partido(db, usuario, PARTIDO_A) == []
