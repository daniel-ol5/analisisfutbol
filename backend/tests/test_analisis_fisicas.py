"""Métricas físicas sobre el motor puro  —  T-075 (CU-43).

Criterio de T-075: un jugador parado 1 minuto acumula menos de 5 m en ese intervalo.
"""

import random
from itertools import pairwise

import pytest
from escenarios_analisis import muestra

from app.analisis.motor.motor import ContextoPartido, MotorPartido

HZ = 5


def _motor() -> MotorPartido:
    return MotorPartido(ContextoPartido(partido_id=1))


def _trayectoria(motor: MotorPartido, posiciones, tid: int = 9, equipo: str = "LOCAL"):
    salidas = []
    for t, x, y in posiciones:
        salidas.append(motor.procesar(muestra(t, [(tid, equipo, x, y)], None)))
    return salidas


# ---------------- Criterio ----------------

def test_criterio_jugador_parado_un_minuto_con_ruido_acumula_menos_de_5_m():
    """60 s a 5 Hz con ruido gaussiano sigma = 0,08 m en x e y (ruido típico de la proyección)."""
    rnd = random.Random(2026)
    motor = _motor()
    puntos = [(n / HZ, 30 + rnd.gauss(0, 0.08), 20 + rnd.gauss(0, 0.08))
              for n in range(60 * HZ)]
    _trayectoria(motor, puntos)

    track = motor.intervalos[0].tracks[9]
    assert track.distancia_m < 5.0
    assert track.sprints == 0
    assert track.velocidad_max_ms < 1.0
    # Sin suavizado, el mismo ruido sumaría decenas de metros.
    crudo = sum(((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5
                for a, b in pairwise(puntos))
    assert crudo > 20


@pytest.mark.parametrize("semilla", range(5))
def test_criterio_se_cumple_con_cualquier_semilla(semilla):
    rnd = random.Random(semilla)
    motor = _motor()
    _trayectoria(motor, [(n / HZ, 52.5 + rnd.gauss(0, 0.08), 34 + rnd.gauss(0, 0.08))
                         for n in range(60 * HZ)])
    assert motor.intervalos[0].tracks[9].distancia_m < 5.0


# ---------------- Distancia, velocidad y sprints ----------------

def _carrera(velocidad: float, segundos: float, quieto_despues: float = 3.0, t0: float = 0.0):
    """Quieto 2 s, corre en línea recta y se queda quieto para que el suavizado alcance."""
    puntos, x = [], 10.0
    n = 0
    total = 2 + segundos + quieto_despues
    while n < round(total * HZ):
        t = n / HZ
        if 2 <= t < 2 + segundos:
            x += velocidad / HZ
        puntos.append((round(t0 + t, 2), round(x, 4), 30.0))
        n += 1
    return puntos


def test_carrera_a_7_m_s_mide_distancia_velocidad_y_un_sprint():
    motor = _motor()
    _trayectoria(motor, _carrera(7.0, 4.0))
    track = motor.intervalos[0].tracks[9]
    assert track.distancia_m == pytest.approx(28.0, abs=0.5)
    assert track.velocidad_max_ms == pytest.approx(7.0, abs=0.5)   # ~25 km/h
    assert track.sprints == 1


def test_trote_a_4_m_s_no_es_sprint():
    motor = _motor()
    _trayectoria(motor, _carrera(4.0, 6.0))
    assert motor.intervalos[0].tracks[9].sprints == 0


def test_pique_corto_que_no_se_sostiene_1_s_no_es_sprint():
    motor = _motor()
    _trayectoria(motor, _carrera(7.5, 0.8))
    assert motor.intervalos[0].tracks[9].sprints == 0


def test_dos_piques_separados_son_dos_sprints():
    motor = _motor()
    _trayectoria(motor, _carrera(7.0, 4.0) + _carrera(7.0, 4.0, t0=20.0))
    assert motor.intervalos[0].tracks[9].sprints == 2


def test_salto_del_tracking_no_suma_metros_ni_velocidad():
    motor = _motor()
    puntos = [(n / HZ, 30.0, 30.0) for n in range(10)]
    puntos += [(n / HZ, 70.0, 30.0) for n in range(10, 30)]   # 40 m en 0,2 s
    _trayectoria(motor, puntos)
    track = motor.intervalos[0].tracks[9]
    assert track.distancia_m < 0.5
    assert track.velocidad_max_ms < 1.0


def test_el_sprint_cuenta_en_el_intervalo_donde_empieza():
    """Corre desde t = 297,6: el sprint empieza en ~299,6 (intervalo 0) y se confirma
    1 s después, con el intervalo 0 ya cerrado."""
    motor = _motor()
    puntos = [(round(n / HZ, 2), 10.0, 30.0) for n in range(round(297.6 * HZ))]
    x = 10.0
    for n in range(round(297.6 * HZ), round(306 * HZ)):
        x += 7.0 / HZ
        puntos.append((round(n / HZ, 2), round(x, 4), 30.0))
    salidas = _trayectoria(motor, puntos)

    assert any(s.cerrados == [0] for s in salidas)
    assert any(s.corregidos == [0] for s in salidas), "el sprint se confirmó tras el cierre"
    assert motor.intervalos[0].tracks[9].sprints == 1
    assert motor.intervalos[1].tracks[9].sprints == 0


def test_tiempo_jugado_cuenta_huecos_de_hasta_1_s():
    motor = _motor()
    _trayectoria(motor, [(0.0, 10, 10), (0.2, 10, 10), (10.0, 10, 10), (10.2, 10, 10)])
    assert motor.intervalos[0].tracks[9].tiempo_s == pytest.approx(1.4)


def test_un_track_sin_asignar_suma_a_su_equipo():
    motor = _motor()
    _trayectoria(motor, _carrera(5.0, 4.0), tid=40, equipo="VISITANTE")
    assert motor.total.equipos["VISITANTE"].distancia_m == pytest.approx(20.0, abs=0.5)
    assert motor.total.equipos["LOCAL"].distancia_m == 0


def test_el_arbitro_no_suma_a_ningun_equipo():
    motor = _motor()
    _trayectoria(motor, _carrera(5.0, 4.0), tid=50, equipo="ARBITRO")
    assert motor.intervalos[0].tracks[50].distancia_m > 0
    assert motor.total.equipos["LOCAL"].distancia_m == 0
    assert motor.total.equipos["VISITANTE"].distancia_m == 0
