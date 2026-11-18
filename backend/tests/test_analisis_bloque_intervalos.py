"""Bloque por equipo e intervalos incrementales sobre el motor puro  —  T-076 (CU-46)."""

import pytest
from escenarios_analisis import partido_sintetico

from app.analisis.motor.bloque import (
    area_envolvente,
    bloque_equipo,
    direccion_de,
    retener_ausentes,
)
from app.analisis.motor.motor import (
    ContextoPartido,
    MotorPartido,
    TramoArquero,
    minutos_de,
)
from app.analisis.motor.muestras import (
    FilaPosicion,
    muestra_de_mensaje,
    muestras_de_filas,
)
from app.analisis.parametros import PARAMETROS
from app.partido.service import filas_de

LINEA = [(2, 20.0, 10.0), (3, 20.0, 25.0), (4, 20.0, 43.0), (5, 20.0, 58.0)]
MEDIOS = [(6, 40.0, 15.0), (7, 40.0, 34.0), (8, 40.0, 53.0)]


def _bloque(puntos, arqueros=frozenset(), direccion="DER", parte=1):
    return bloque_equipo(list(puntos), set(arqueros), direccion=direccion, parte=parte,
                         largo_m=105.0, ancho_m=68.0, p=PARAMETROS)


# ---------------- Bloque ----------------

def test_el_arquero_dentro_de_su_area_no_cuenta_para_la_linea():
    b = _bloque([(1, 3.0, 34.0), *LINEA, *MEDIOS])
    assert b.altura_linea_m == pytest.approx(20.0)
    assert b.amplitud_m == pytest.approx(58.0 - 10.0)


def test_sin_excluir_al_arquero_la_linea_bajaria():
    """Control: si el arquero está fuera del área (salió jugando) cuenta como de campo."""
    b = _bloque([(1, 25.0, 34.0), *LINEA, *MEDIOS])
    assert b.altura_linea_m == pytest.approx(20.0)  # 4 más retrasados: los defensores
    b = _bloque([(1, 18.0, 34.0), *LINEA, *MEDIOS])
    assert b.altura_linea_m == pytest.approx((18 + 20 * 3) / 4)


def test_el_arquero_asignado_se_excluye_aunque_este_fuera_del_area():
    b = _bloque([(1, 18.0, 34.0), *LINEA, *MEDIOS], arqueros={1})
    assert b.altura_linea_m == pytest.approx(20.0)


def test_area_envolvente_de_figuras_conocidas():
    assert area_envolvente([(0, 0), (10, 0), (0, 10)]) == pytest.approx(50.0)       # triángulo
    cuadrado = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert area_envolvente(cuadrado) == pytest.approx(100.0)
    assert area_envolvente([*cuadrado, (5, 5), (2, 7)]) == pytest.approx(100.0)     # interiores no suman
    assert area_envolvente([(0, 0), (4, 0), (4, 6), (0, 6), (2, 3)]) == pytest.approx(24.0)


def test_area_envolvente_degenerada_es_cero():
    assert area_envolvente([]) == 0.0
    assert area_envolvente([(1, 1), (1, 1), (1, 1)]) == 0.0      # puntos repetidos
    assert area_envolvente([(0, 0), (5, 5)]) == 0.0              # dos puntos
    assert area_envolvente([(0, 0), (5, 5), (10, 10)]) == 0.0    # alineados


def test_compacidad_es_el_area_del_poligono_envolvente_de_los_jugadores_de_campo():
    # Campo: rectángulo de 20 m de largo por 48 m de ancho (x 20..40, y 10..58).
    campo = [(2, 20.0, 10.0), (3, 20.0, 58.0), (4, 40.0, 10.0), (5, 40.0, 58.0)]
    b = _bloque([(1, 3.0, 34.0), *campo])        # el arquero queda fuera del polígono
    assert b.compacidad_m2 == pytest.approx(20.0 * 48.0)
    assert b.amplitud_m == pytest.approx(48.0)
    # Un jugador dentro del rectángulo no cambia el área; uno fuera de él, sí.
    assert _bloque([(1, 3.0, 34.0), *campo, (6, 30.0, 30.0)]).compacidad_m2 == pytest.approx(960.0)
    assert _bloque([(1, 3.0, 34.0), *campo, (6, 50.0, 34.0)]).compacidad_m2 > 960.0


def test_un_equipo_mas_junto_tiene_menos_compacidad():
    abierto = [(2, 20.0, 5.0), (3, 20.0, 63.0), (4, 45.0, 5.0), (5, 45.0, 63.0)]
    junto = [(2, 20.0, 25.0), (3, 20.0, 43.0), (4, 35.0, 25.0), (5, 35.0, 43.0)]
    assert _bloque(junto).compacidad_m2 < _bloque(abierto).compacidad_m2


def test_con_menos_de_cuatro_de_campo_no_hay_altura_pero_si_forma():
    b = _bloque([(1, 3.0, 34.0), (2, 20.0, 30.0), (3, 20.0, 38.0)])
    assert b.altura_linea_m is None   # menos de 4 de campo
    assert b.amplitud_m == pytest.approx(8.0)
    assert b.compacidad_m2 == 0.0     # dos jugadores no forman polígono


# ---------------- Suavizado: retención de ausentes (CU-45) ----------------

ULTIMAS = {2: (10.0, 20.0, 10.0), 3: (9.0, 20.0, 25.0), 9: (10.0, 70.0, 30.0), 50: (2.0, 1.0, 1.0)}
EQUIPOS = {2: "LOCAL", 3: "LOCAL", 9: "VISITANTE", 50: "LOCAL"}


def test_retener_ausentes_agrega_a_los_del_equipo_vistos_hace_poco():
    visibles = [(3, 20.0, 26.0)]
    # El 2 se vio hace 1 s y el 50 hace 9 s: solo el primero sigue contando.
    salida = retener_ausentes(visibles, ULTIMAS, EQUIPOS, "LOCAL", 11.0, 3.0)
    assert salida == [(3, 20.0, 26.0), (2, 20.0, 10.0)]


def test_retener_ausentes_no_duplica_a_los_visibles_ni_mezcla_equipos():
    salida = retener_ausentes([(2, 21.0, 11.0)], ULTIMAS, EQUIPOS, "LOCAL", 10.5, 3.0)
    assert (2, 20.0, 10.0) not in salida and (2, 21.0, 11.0) in salida   # manda la posición actual
    assert all(tid != 9 for tid, _, _ in salida)                       # el 9 es del visitante


def test_retener_ausentes_vence_exactamente_al_pasar_la_retencion():
    assert (2, 20.0, 10.0) in retener_ausentes([], ULTIMAS, EQUIPOS, "LOCAL", 13.0, 3.0)
    assert (2, 20.0, 10.0) not in retener_ausentes([], ULTIMAS, EQUIPOS, "LOCAL", 13.1, 3.0)
    assert retener_ausentes([], ULTIMAS, EQUIPOS, "LOCAL", 11.0, 0.0) == []   # sin retención


def test_el_rival_y_el_segundo_tiempo_se_normalizan():
    # El visitante ataca hacia -x en el 1er tiempo: su arquero está cerca de x = 105.
    visitante = [(12, 102.0, 34.0), *[(t, 105 - x, 68 - y) for t, x, y in LINEA + MEDIOS]]
    direccion = direccion_de("VISITANTE", "LOCAL", "DER")
    assert direccion == "IZQ"
    b = _bloque(visitante, direccion=direccion)
    assert b.altura_linea_m == pytest.approx(20.0)
    # En el 2do tiempo el local ataca hacia -x: mismo bloque, espejado.
    b2 = _bloque([(1, 102.0, 34.0), *[(t, 105 - x, 68 - y) for t, x, y in LINEA + MEDIOS]],
                 direccion="DER", parte=2)
    assert b2.altura_linea_m == pytest.approx(20.0)


def test_el_motor_usa_los_tramos_de_arquero_vigentes():
    from escenarios_analisis import muestra

    jugadores = [(1, "LOCAL", 18.0, 34.0)] + [(t, "LOCAL", x, y) for t, x, y in LINEA + MEDIOS]
    sin = MotorPartido(ContextoPartido(partido_id=1))
    con = MotorPartido(ContextoPartido(partido_id=1), arqueros=[TramoArquero(1, 0.0, None)])
    for motor in (sin, con):
        motor.procesar(muestra(0.0, jugadores, None))
    assert sin.total.equipos["LOCAL"].altura_linea_m == pytest.approx(19.5)
    assert con.total.equipos["LOCAL"].altura_linea_m == pytest.approx(20.0)


# ---------------- Intervalos ----------------

def test_el_intervalo_se_cierra_con_la_primera_muestra_del_siguiente():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    cierres = {}
    for m in partido_sintetico(1, 290, 312):
        salida = motor.procesar(muestra_de_mensaje(m))
        if salida.cerrados:
            cierres[m.t] = salida.cerrados
    assert cierres == {300.0: [0]}
    assert motor.intervalos[0].cerrado and not motor.intervalos[0].parcial
    assert minutos_de(motor.intervalos[0]) == (0, 5)
    assert motor.abierto is motor.intervalos[1]


def test_al_cerrar_el_ultimo_queda_parcial():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    for m in partido_sintetico(1, 298, 304):
        motor.procesar(muestra_de_mensaje(m))
    assert motor.cerrar() == 1
    assert motor.intervalos[1].parcial
    assert minutos_de(motor.intervalos[1]) == (5, 6)
    assert motor.cerrar() is None


def test_avisa_cada_segundo_y_cada_minuto_de_partido():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    salidas = [motor.procesar(muestra_de_mensaje(m)) for m in partido_sintetico(1, 0, 125)]
    assert sum(s.nuevo_segundo for s in salidas) == 125
    assert sum(s.nuevo_minuto for s in salidas) == 3


def test_ultimos_5_minutos_es_una_ventana_movil():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    for m in partido_sintetico(1, 0, 420):
        motor.procesar(muestra_de_mensaje(m))
    ultimos = motor.ultimos()
    tiempo = sum(e.posesion_s for e in ultimos.equipos.values()) + ultimos.disputa_s
    total = sum(e.posesion_s for e in motor.total.equipos.values()) + motor.total.disputa_s
    assert tiempo == pytest.approx(300 * total / 419.8, rel=0.02)


def test_muestras_repetidas_o_fuera_de_orden_se_ignoran():
    motor = MotorPartido(ContextoPartido(partido_id=1))
    mensajes = partido_sintetico(1, 0, 4)
    for m in mensajes:
        motor.procesar(muestra_de_mensaje(m))
    antes = motor.total.equipos["LOCAL"].distancia_m
    motor.procesar(muestra_de_mensaje(mensajes[3]))
    assert motor.total.equipos["LOCAL"].distancia_m == antes


# ---------------- Vivo y tabla dan lo mismo ----------------

def test_desde_mensajes_y_desde_filas_de_posicion_el_motor_da_lo_mismo():
    """El camino en vivo (MensajeWorker) y el del recálculo (filas) no pueden divergir."""
    mensajes = partido_sintetico(1, 0, 320)
    vivo = MotorPartido(ContextoPartido(partido_id=1))
    for m in mensajes:
        vivo.procesar(muestra_de_mensaje(m))

    filas = [FilaPosicion(f["t"], f["track_id"], f["x_m"], f["y_m"], f["es_balon"])
             for m in mensajes for f in filas_de(m)]
    equipos = {j.tid: j.equipo.value for j in mensajes[0].jugadores}
    tabla = MotorPartido(ContextoPartido(partido_id=1))
    for muestra in muestras_de_filas(filas, equipos):
        tabla.procesar(muestra)

    assert tabla.intervalos.keys() == vivo.intervalos.keys()
    for k in vivo.intervalos:
        assert tabla.intervalos[k] == vivo.intervalos[k]
    assert tabla.total == vivo.total
    local = vivo.total.equipos["LOCAL"]
    assert local.pases_intentados > 0 and local.pases_completados > 0
    assert vivo.total.disputa_s > 0


def test_filas_de_marca_la_fila_del_balon():
    m = partido_sintetico(1, 0, 0.2)[0]
    filas = filas_de(m)
    assert [f["es_balon"] for f in filas] == [False] * 22 + [True]
