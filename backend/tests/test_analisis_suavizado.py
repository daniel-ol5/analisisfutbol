"""Equivalencia con el suavizado de Alex  —  T-075.

`app/analisis/motor/suavizado.py` replica `suavizar_trayectoria` de
`vision/calibracion/suavizado.py` (el backend no puede importarlo en
producción). Esta prueba carga el archivo de Alex con importlib, SOLO aquí, y
compara los resultados con los mismos datos. Si el archivo no existe (imagen de
Docker o CI que solo tienen `backend/`), la prueba se salta.
"""

import importlib.util
import math
import random
import sys
from pathlib import Path

import pytest

from app.analisis.motor.suavizado import SuavizadorEMAUmbral, distancia, suavizar

ARCHIVO_ALEX = Path(__file__).resolve().parents[2] / "vision" / "calibracion" / "suavizado.py"


@pytest.fixture(scope="module")
def alex():
    if not ARCHIVO_ALEX.is_file():
        pytest.skip(f"No está {ARCHIVO_ALEX} (solo se copia backend/): no se puede comparar "
                    "con el suavizado de Alex en este entorno")
    spec = importlib.util.spec_from_file_location("suavizado_alex_t075", ARCHIVO_ALEX)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Sus dataclasses necesitan encontrar el módulo en sys.modules al definirse.
    sys.modules[spec.name] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        sys.modules.pop(spec.name, None)


def _trayectorias():
    rnd = random.Random(75)
    quieto = [(n / 5, 30 + rnd.gauss(0, 0.08), 20 + rnd.gauss(0, 0.08)) for n in range(300)]
    carrera = [(n / 5, 10 + 1.4 * n + rnd.gauss(0, 0.05), 34 + rnd.gauss(0, 0.05))
               for n in range(100)]
    curva = [(n / 5, 52.5 + 15 * math.cos(n / 20), 34 + 15 * math.sin(n / 20))
             for n in range(400)]
    return {"quieto": quieto, "carrera": carrera, "curva": curva}


@pytest.mark.parametrize("nombre", ["quieto", "carrera", "curva"])
@pytest.mark.parametrize(("alpha", "umbral"), [(0.2, 0.2), (0.5, 0.1), (0.1, 0.5)])
def test_mismo_resultado_que_suavizar_trayectoria_de_alex(alex, nombre, alpha, umbral):
    puntos = _trayectorias()[nombre]
    esperado = alex.suavizar_trayectoria(
        [alex.PosicionTiempo(t=t, x=x, y=y) for t, x, y in puntos], alpha=alpha, umbral_m=umbral)
    obtenido = suavizar(puntos, alpha=alpha, umbral_m=umbral)

    assert len(obtenido) == len(esperado)
    for (t, x, y), e in zip(obtenido, esperado, strict=True):
        assert (t, x, y) == pytest.approx((e.t, e.x, e.y), abs=1e-12)
    assert distancia(obtenido) == pytest.approx(alex.distancia_recorrida(esperado), abs=1e-9)


def test_mismos_valores_por_defecto_que_alex(alex):
    import inspect

    firma = inspect.signature(alex.suavizar_trayectoria)
    por_defecto = SuavizadorEMAUmbral()
    assert firma.parameters["alpha"].default == por_defecto.alpha
    assert firma.parameters["umbral_m"].default == por_defecto.umbral_m


def test_la_primera_posicion_se_reporta_tal_cual():
    s = SuavizadorEMAUmbral()
    assert s.actualizar(10.0, 5.0) == (10.0, 5.0)
    assert s.actualizar(10.1, 5.0) == (10.0, 5.0)   # el EMA se movió 0,02 m < umbral
