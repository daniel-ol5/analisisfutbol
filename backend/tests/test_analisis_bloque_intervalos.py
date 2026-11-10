"""Bloque por equipo e intervalos incrementales sobre el motor puro  —  T-076 (CU-46)."""

import pytest
from escenarios_analisis import partido_sintetico

from app.analisis.motor.bloque import bloque_equipo, direccion_de
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


def test_compacidad_es_la_distancia_media_al_centroide():
    b = _bloque([(1, 3.0, 34.0), (2, 20.0, 30.0), (3, 20.0, 38.0)])
    assert b.compacidad_m == pytest.approx(4.0)
    assert b.altura_linea_m is None   # menos de 4 de campo


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
