"""Pruebas de CU-26 (suavizado de trayectorias): un jugador detenido durante
1 minuto, con el mismo ruido de proyeccion que se veria en la vida real (en
metros: ya paso por `calibracion.homografia`).

Criterio de aceptacion de CU-26: un jugador parado 1 minuto acumula menos de
5 metros.
"""

import numpy as np
import pytest

from calibracion.suavizado import PosicionTiempo, distancia_recorrida, suavizar_trayectoria

_RNG = np.random.default_rng(7)


def _trayectoria_jugador_detenido(
    segundos: float = 60.0,
    hz: float = 5.0,
    sigma_m: float = 0.08,
    x0: float = 50.0,
    y0: float = 30.0,
) -> list[PosicionTiempo]:
    n = int(segundos * hz)
    pasos = np.arange(n) / hz
    ruido = _RNG.normal(0, sigma_m, size=(n, 2))
    return [
        PosicionTiempo(t=float(t), x=x0 + dx, y=y0 + dy)
        for t, (dx, dy) in zip(pasos, ruido)
    ]


def test_sin_filtrar_el_ruido_ya_acumula_varios_metros():
    """Documenta el problema que motiva CU-26: aunque el jugador no se mueva,
    sin filtrar el ruido de deteccion/proyeccion ya rompe el criterio de los
    5 metros."""
    trayectoria = _trayectoria_jugador_detenido()
    assert distancia_recorrida(trayectoria) > 5.0


def test_jugador_detenido_un_minuto_acumula_menos_de_5_metros():
    """Criterio de aceptacion de CU-26."""
    trayectoria = _trayectoria_jugador_detenido()
    suavizada = suavizar_trayectoria(trayectoria, alpha=0.2, umbral_m=0.2)
    distancia = distancia_recorrida(suavizada)
    assert distancia < 5.0, f"{distancia:.2f} m en 60 s detenido"


def test_umbral_cero_no_descarta_ninguna_muestra():
    """Con umbral 0 toda posicion del EMA se reporta: sirve para separar el
    aporte del EMA del aporte del umbral de desplazamiento minimo."""
    trayectoria = _trayectoria_jugador_detenido()
    suavizada = suavizar_trayectoria(trayectoria, alpha=0.2, umbral_m=0.0)
    assert len(suavizada) == len(trayectoria)


def test_lista_vacia_no_falla():
    assert suavizar_trayectoria([]) == []
    assert distancia_recorrida([]) == 0.0


def test_una_sola_posicion_no_falla():
    unica = [PosicionTiempo(t=0.0, x=1.0, y=2.0)]
    assert suavizar_trayectoria(unica) == unica
    assert distancia_recorrida(unica) == 0.0


def test_un_movimiento_real_se_sigue_detectando():
    """El filtro no debe esconder un desplazamiento real grande: no es solo
    un umbral que nunca deja reportar nada."""
    quieto = _trayectoria_jugador_detenido(segundos=10.0)
    caminata = [
        PosicionTiempo(t=10.0 + i * 0.2, x=50.0 + i * 0.4, y=30.0)
        for i in range(1, 26)  # 5 s recorriendo ~10 m en linea recta
    ]
    trayectoria = quieto + caminata
    suavizada = suavizar_trayectoria(trayectoria, alpha=0.2, umbral_m=0.2)

    inicio, fin = suavizada[0], suavizada[-1]
    desplazamiento = ((fin.x - inicio.x) ** 2 + (fin.y - inicio.y) ** 2) ** 0.5
    assert desplazamiento > 8.0, f"se perdio el movimiento real: {desplazamiento:.2f} m"
