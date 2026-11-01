"""T-029 · Homografía y error de reproyección (CU-21): función pura, sin base de datos."""

import numpy as np
import pytest
from datos_calibracion import (
    a_metros,
    a_pixeles,
    marcas_cancha,
)

from app.vision.homografia import (
    MIN_PUNTOS,
    UMBRAL_COLINEALIDAD,
    UMBRAL_ERROR_MEDIO_M,
    HomografiaError,
    _cociente_colinealidad,
    calcular_homografia,
    es_valida,
)


def _proyectar(matriz, pixeles):
    h = np.column_stack([pixeles, np.ones(len(pixeles))]) @ np.array(matriz).T
    return h[:, :2] / h[:, 2:3]


# ---------- recupera una homografía conocida ----------

def test_recupera_una_homografia_conocida_con_error_casi_cero():
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)

    r = calcular_homografia(pixeles, cancha)

    assert r.error_medio_m < 1e-6
    assert r.error_max_m < 1e-6
    # La matriz recuperada lleva cualquier píxel a los mismos metros que la verdadera.
    otros = np.array([[300.0, 400.0], [1500.0, 700.0], [900.0, 250.0]])
    assert _proyectar(r.matriz, otros) == pytest.approx(a_metros(otros), abs=1e-6)
    assert r.matriz[2][2] == pytest.approx(1.0)
    assert len(r.matriz) == 3 and all(len(f) == 3 for f in r.matriz)


def test_acepta_listas_de_tuplas_y_arrays():
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)
    r1 = calcular_homografia(pixeles.tolist(), cancha.tolist())
    r2 = calcular_homografia(pixeles, cancha)
    assert np.array(r1.matriz) == pytest.approx(np.array(r2.matriz))


# ---------- ruido ----------

def test_con_ruido_pequeno_el_error_es_pequeno_y_valido():
    rng = np.random.default_rng(7)
    cancha = marcas_cancha()
    # Con perspectiva, 1 px en el fondo de la cancha vale ~0,3 m: por eso el ruido es de 0,5 px.
    pixeles = a_pixeles(cancha) + rng.normal(0, 0.5, size=(len(cancha), 2))

    r = calcular_homografia(pixeles, cancha)

    assert 0 < r.error_medio_m < 0.3
    assert r.error_max_m >= r.error_medio_m
    assert es_valida(r.error_medio_m)


# ---------- el peor punto ----------

# Se prueban puntos centrales y del borde. NO se prueba la esquina 0: un clic muy malo en un
# punto de mucho "apalancamiento" arrastra la matriz y el mayor residual cae en otro punto
# (limite honesto del ajuste por minimos cuadrados, ver el resumen de T-029).
@pytest.mark.parametrize("indice", [5, 6, 11])
def test_el_indice_del_peor_punto_senala_al_desplazado(indice):
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)
    pixeles[indice] += [90.0, -70.0]   # un clic muy mal puesto

    r = calcular_homografia(pixeles, cancha)

    assert r.indice_peor == indice          # base 0 sobre la lista enviada
    assert r.error_max_m > 3 * r.error_medio_m
    assert isinstance(r.indice_peor, int)


# ---------- rechazos con mensaje claro ----------

def test_menos_de_8_puntos_se_rechaza():
    cancha = marcas_cancha()[:MIN_PUNTOS - 1]
    with pytest.raises(HomografiaError, match="al menos 8 puntos"):
        calcular_homografia(a_pixeles(cancha), cancha)


def test_exactamente_8_puntos_se_acepta():
    cancha = marcas_cancha()[:MIN_PUNTOS]
    r = calcular_homografia(a_pixeles(cancha), cancha)
    assert r.error_medio_m < 1e-6


def test_cantidades_distintas_se_rechazan():
    cancha = marcas_cancha()
    with pytest.raises(HomografiaError, match="misma cantidad"):
        calcular_homografia(a_pixeles(cancha)[:9], cancha[:10])


def test_puntos_exactamente_colineales_se_rechazan():
    t = np.linspace(0, 1, 10)
    recta = np.column_stack([100 + 800 * t, 200 + 300 * t])
    cancha = marcas_cancha()[:10]
    with pytest.raises(HomografiaError, match="alineados"):
        calcular_homografia(recta, cancha)
    with pytest.raises(HomografiaError, match="alineados"):
        calcular_homografia(a_pixeles(cancha), np.column_stack([10 * t, 5 * t]))


def test_colinealidad_el_umbral_separa_una_franja_estrecha_de_una_cancha_aplastada():
    """Aplastar la cancha en Y acerca las marcas a una recta. Un lado del umbral rechaza, el otro no."""
    def con_ancho(factor):
        cancha = marcas_cancha()
        cancha[:, 1] *= factor
        return a_pixeles(cancha), cancha

    img_cerca, can_cerca = con_ancho(0.04)
    img_lejos, can_lejos = con_ancho(0.5)

    # La perspectiva aplasta aún más la imagen: el cociente que cuenta es el menor de los dos.
    cerca = min(_cociente_colinealidad(img_cerca), _cociente_colinealidad(can_cerca))
    lejos = min(_cociente_colinealidad(img_lejos), _cociente_colinealidad(can_lejos))
    assert cerca < UMBRAL_COLINEALIDAD < lejos
    with pytest.raises(HomografiaError, match="alineados"):
        calcular_homografia(img_cerca, can_cerca)
    r = calcular_homografia(img_lejos, can_lejos)   # cruza el umbral: ya se acepta
    assert r.error_medio_m < 1e-4


def test_puntos_repetidos_se_rechazan_con_su_indice():
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)
    pixeles[4] = pixeles[2]
    with pytest.raises(HomografiaError, match=r"repetidos.*\[4\]"):
        calcular_homografia(pixeles, cancha)


def test_puntos_degenerados_siete_en_una_recta_y_uno_fuera_se_rechazan():
    """Siete puntos alineados y uno suelto no fijan una única homografía (rango < 8).

    Aquí el cociente de colinealidad es alto (~0,7): lo detecta el rango del DLT.
    """
    recta = np.column_stack([np.linspace(0, 105, 7), np.zeros(7)])
    cancha = np.vstack([recta, [[50.0, 68.0]]])
    assert _cociente_colinealidad(cancha) > UMBRAL_COLINEALIDAD
    with pytest.raises(HomografiaError, match="degenerados"):
        calcular_homografia(a_pixeles(cancha), cancha)


@pytest.mark.parametrize("malo", [np.nan, np.inf, -np.inf])
def test_valores_no_finitos_se_rechazan(malo):
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha)
    pixeles[3, 0] = malo
    with pytest.raises(HomografiaError, match="no finitos"):
        calcular_homografia(pixeles, cancha)


def test_entrada_que_no_son_pares_se_rechaza():
    with pytest.raises(HomografiaError):
        calcular_homografia([[1, 2, 3]] * 8, [[1, 2]] * 8)
    with pytest.raises(HomografiaError):
        calcular_homografia([["a", "b"]] * 8, [[1, 2]] * 8)


# ---------- umbral de validez ----------

def test_el_umbral_es_2_metros_y_2_exacto_es_valido():
    assert UMBRAL_ERROR_MEDIO_M == 2.0
    assert es_valida(2.0)
    assert es_valida(0.0)
    assert not es_valida(2.0001)


def test_error_medio_mayor_a_2_m_marca_no_valida():
    rng = np.random.default_rng(3)
    cancha = marcas_cancha()
    pixeles = a_pixeles(cancha) + rng.normal(0, 40.0, size=(len(cancha), 2))  # clics muy malos

    r = calcular_homografia(pixeles, cancha)

    assert r.error_medio_m > UMBRAL_ERROR_MEDIO_M
    assert not es_valida(r.error_medio_m)


# ---------- cancha no reglamentaria ----------

def test_cancha_100_por_60_da_distancias_acordes_a_sus_medidas():
    cancha = marcas_cancha(100.0, 60.0)
    r = calcular_homografia(a_pixeles(cancha), cancha)
    assert r.error_medio_m < 1e-6

    esquinas_px = a_pixeles(np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 60.0]]))
    m = _proyectar(r.matriz, esquinas_px)
    assert np.linalg.norm(m[1] - m[0]) == pytest.approx(100.0, abs=1e-6)   # largo real
    assert np.linalg.norm(m[2] - m[1]) == pytest.approx(60.0, abs=1e-6)    # ancho real
    assert np.linalg.norm(m[2] - m[0]) == pytest.approx(np.hypot(100, 60), abs=1e-6)
