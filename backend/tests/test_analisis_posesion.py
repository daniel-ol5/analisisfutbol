"""Posesión y pases sobre el motor puro  —  T-074 (CU-42), T-076.

Criterio de T-074: con el balón lejos de todos, ese tiempo se computa como disputa.
"""

import pytest
from escenarios_analisis import muestra

from app.analisis.motor.motor import ContextoPartido, MotorPartido, porcentajes
from app.analisis.motor.posesion import EstadoPosesion, poseedor_de
from app.analisis.parametros import PARAMETROS


def _motor() -> MotorPartido:
    return MotorPartido(ContextoPartido(partido_id=1))


def _correr(motor: MotorPartido, desde: float, hasta: float, jugadores, balon) -> None:
    n = round(desde * 5)
    while n < round(hasta * 5):
        t = n / 5
        motor.procesar(muestra(t, jugadores(t) if callable(jugadores) else jugadores,
                               balon(t) if callable(balon) else balon))
        n += 1


DOS = [(1, "LOCAL", 50.0, 34.0), (2, "VISITANTE", 60.0, 34.0)]


# ---------------- Criterio ----------------

def test_criterio_balon_lejos_de_todos_es_disputa():
    motor = _motor()
    # El jugador más cercano está a 5 m: nadie posee.
    _correr(motor, 0, 30, DOS, (55.0, 39.0))
    local, visitante, disputa = porcentajes(motor.total)
    assert (local, visitante, disputa) == (0.0, 0.0, 100.0)
    assert motor.total.disputa_s == pytest.approx(29.8)


def test_a_2_m_justos_posee_y_un_poco_mas_lejos_es_disputa():
    cerca = muestra(0, DOS, (52.0, 34.0))
    lejos = muestra(0, DOS, (52.05, 34.0))
    equipos = {1: "LOCAL", 2: "VISITANTE"}
    assert poseedor_de(cerca, equipos, PARAMETROS).estado == EstadoPosesion.LOCAL
    assert poseedor_de(lejos, equipos, PARAMETROS).estado == EstadoPosesion.DISPUTA


def test_local_visitante_y_disputa_suman_100():
    motor = _motor()

    def balon(t):
        if t < 10:
            return (50.5, 34.0)       # local
        if t < 15:
            return (55.0, 20.0)       # disputa
        return (59.5, 34.0)           # visitante

    _correr(motor, 0, 20, DOS, balon)
    local, visitante, disputa = porcentajes(motor.total)
    assert local + visitante + disputa == pytest.approx(100, abs=0.01)
    # La última muestra no tiene sucesora: el visitante suma 4,8 s y no 5.
    assert motor.total.equipos["LOCAL"].posesion_s == pytest.approx(10.0)
    assert motor.total.disputa_s == pytest.approx(5.0)
    assert motor.total.equipos["VISITANTE"].posesion_s == pytest.approx(4.8)


def test_sin_balon_visible_no_se_asigna():
    motor = _motor()
    _correr(motor, 0, 10, DOS, lambda t: (50.5, 34.0) if t < 5 else None)
    assert motor.total.equipos["LOCAL"].posesion_s == pytest.approx(5.0)
    assert motor.total.disputa_s == 0
    assert porcentajes(motor.total) == (100.0, 0.0, 0.0)


def test_el_arbitro_y_los_desconocidos_no_poseen():
    motor = _motor()
    jugadores = [*DOS, (30, "ARBITRO", 55.0, 34.0), (31, "DESCONOCIDO", 55.0, 34.5)]
    _correr(motor, 0, 5, jugadores, (55.2, 34.0))
    assert porcentajes(motor.total) == (0.0, 0.0, 100.0)


def test_un_hueco_sin_datos_cuenta_como_mucho_1_s():
    motor = _motor()
    motor.procesar(muestra(0.0, DOS, (50.5, 34.0)))
    motor.procesar(muestra(30.0, DOS, (50.5, 34.0)))
    assert motor.total.equipos["LOCAL"].posesion_s == pytest.approx(1.0)


def test_el_equipo_de_un_track_es_el_del_primer_mensaje():
    motor = _motor()
    motor.procesar(muestra(0.0, [(1, "LOCAL", 50.0, 34.0)], (50.5, 34.0)))
    motor.procesar(muestra(0.2, [(1, "VISITANTE", 50.0, 34.0)], (50.5, 34.0)))
    motor.procesar(muestra(0.4, [(1, "VISITANTE", 50.0, 34.0)], (50.5, 34.0)))
    assert motor.equipo_de(1) == "LOCAL"
    assert motor.total.equipos["VISITANTE"].posesion_s == 0


# ---------------- Pases ----------------

def _pase(destino_equipo: str, recorrido_m: float = 10.0, hueco_s: float = 1.0):
    """A (local, tid 1) tiene el balón 2 s; viaja `hueco_s`; lo recibe B (tid 2) 2 s."""
    a = (1, "LOCAL", 40.0, 34.0)
    b = (2, destino_equipo, 40.0 + recorrido_m, 34.0)
    lejos = (3, "LOCAL", 10.0, 10.0)

    def balon(t):
        if t < 2:
            return (40.5, 34.0)
        if t < 2 + hueco_s:
            return (40.0 + recorrido_m / 2, 50.0)   # en el aire, lejos de todos
        return (40.0 + recorrido_m - 0.5, 34.0)

    motor = _motor()
    _correr(motor, 0, 4 + hueco_s, [a, b, lejos], balon)
    return motor.total.equipos["LOCAL"]


def test_pase_a_un_companero_es_completado():
    local = _pase("LOCAL")
    assert (local.pases_intentados, local.pases_completados) == (1, 1)


def test_pase_a_un_rival_es_intentado_y_no_completado():
    local = _pase("VISITANTE")
    assert (local.pases_intentados, local.pases_completados) == (1, 0)


def test_quite_con_el_balon_casi_quieto_no_es_pase():
    local = _pase("VISITANTE", recorrido_m=2.0, hueco_s=0.4)
    assert local.pases_intentados == 0


def test_mas_de_4_s_entre_poseedores_no_es_pase():
    local = _pase("LOCAL", hueco_s=4.6)
    assert local.pases_intentados == 0


def test_un_poseedor_de_una_sola_muestra_no_es_estable():
    """C toca el balón una muestra en el camino: el pase sigue siendo de A a B."""
    a = (1, "LOCAL", 40.0, 34.0)
    b = (2, "LOCAL", 60.0, 34.0)
    c = (3, "VISITANTE", 50.0, 20.0)

    def balon(t):
        if t < 2:
            return (40.5, 34.0)
        if abs(t - 2.4) < 1e-9:
            return (50.0, 20.5)        # roce de C, una sola muestra
        if t < 3:
            return (50.0, 45.0)
        return (59.5, 34.0)

    motor = _motor()
    _correr(motor, 0, 5, [a, b, c], balon)
    local = motor.total.equipos["LOCAL"]
    assert (local.pases_intentados, local.pases_completados) == (1, 1)
