"""Pruebas del comando de regresión del modelo (T-064), sin GPU.

El "detector" se reemplaza por una función que devuelve detecciones armadas a
mano, igual que el resto de las pruebas de vision/.
"""

import json
from argparse import Namespace

import pytest

from evaluacion.regresion import (
    UMBRALES,
    Metricas,
    alinear,
    argumentos,
    cargar_anotaciones,
    correr,
    evaluar,
    fallas,
)
from seguimiento.tipos import Clase, Deteccion


def _det(tid, x, clase=Clase.JUGADOR, conf=0.9):
    return Deteccion.desde_caja(tid, clase, (x, 100.0, x + 40.0, 180.0), conf)


def _anotaciones(tmp_path, con_balon=True):
    cuadros = {}
    for i in range(0, 30, 3):  # 10 cuadros anotados, cada 3
        objetos = [
            {"tid": tid, "clase": "JUGADOR", "caja": [x + i, 100, x + i + 40, 180]}
            for tid, x in ((1, 50), (2, 200), (3, 350))
        ]
        if con_balon:
            objetos.append({"tid": 0, "clase": "BALON", "caja": [300 + i, 170, 310 + i, 180]})
        cuadros[str(i)] = objetos
    ruta = tmp_path / "clip.json"
    ruta.write_text(json.dumps({"cuadros": cuadros}), encoding="utf-8")
    return ruta


def _detector_perfecto(verdad):
    """Devuelve lo anotado, en todos los cuadros (también los no anotados)."""

    def detectar(_pesos, _clip):
        for i in range(30):
            yield i, [
                Deteccion.desde_caja(d.tid, d.clase, d.caja, 0.95) for d in verdad.get(i, [])
            ]

    return detectar


class ApiFalsa:
    def __init__(self, activo=None):
        self.activo = activo
        self.registrados = []

    def modelo_activo(self):
        return self.activo

    def registrar_modelo(self, datos):
        self.registrados.append(datos)
        return {"id": 9, **datos}


def _args(tmp_path, anotaciones, **extra):
    base = {"pesos": "best.pt", "clip": str(tmp_path / "clip.mp4"),
            "anotaciones": str(anotaciones), "registrar": False,
            "nombre": None, "version": None, "archivo_url": None}
    return Namespace(**{**base, **extra})


# ---------- anotaciones ----------

def test_cargar_anotaciones(tmp_path):
    verdad = cargar_anotaciones(_anotaciones(tmp_path))
    assert sorted(verdad) == list(range(0, 30, 3))
    assert [d.clase for d in verdad[0]] == [Clase.JUGADOR] * 3 + [Clase.BALON]
    assert verdad[3][0].caja == (53.0, 100.0, 93.0, 180.0)
    assert verdad[3][0].punto_apoyo == (73.0, 180.0)


@pytest.mark.parametrize("contenido", ['{"cuadros": {}}', "[]", '{"otra": 1}'])
def test_anotaciones_sin_cuadros_son_invalidas(tmp_path, contenido):
    ruta = tmp_path / "x.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_anotaciones(ruta)


def test_un_cuadro_anotado_sin_detecciones_cuenta_como_fallo():
    verdad = {0: [_det(1, 10)], 6: [_det(1, 20)]}
    detectadas, anotadas = alinear([(0, [_det(1, 10)])], verdad)  # el 6 no se detectó
    assert detectadas == [[_det(1, 10)], []]
    assert len(anotadas) == 2


# ---------- métricas y veredicto ----------

def test_un_detector_perfecto_da_metricas_perfectas(tmp_path):
    verdad = cargar_anotaciones(_anotaciones(tmp_path))
    m = evaluar(*alinear(_detector_perfecto(verdad)("p", "c"), verdad))
    assert m.map50_jugador == pytest.approx(1.0)
    assert m.map50_balon == pytest.approx(1.0)
    assert m.idf1 == pytest.approx(1.0)


def test_sin_balon_anotado_esa_metrica_queda_vacia(tmp_path):
    verdad = cargar_anotaciones(_anotaciones(tmp_path, con_balon=False))
    m = evaluar(*alinear(_detector_perfecto(verdad)("p", "c"), verdad))
    assert m.map50_balon is None


def test_si_los_tid_cambian_baja_el_idf1(tmp_path):
    verdad = cargar_anotaciones(_anotaciones(tmp_path))

    def ids_cambiados(_p, _c):
        for i in sorted(verdad):
            # A mitad del clip el tracker les cambia el id a todos.
            yield i, [Deteccion.desde_caja(d.tid + (100 if i >= 15 else 0), d.clase, d.caja, 0.9)
                      for d in verdad[i]]

    m = evaluar(*alinear(ids_cambiados("p", "c"), verdad))
    assert m.map50_jugador == pytest.approx(1.0)  # las cajas siguen bien
    assert m.idf1 < UMBRALES["idf1"]


def test_veredicto_umbrales_de_t055():
    assert fallas(Metricas(0.90, None, 0.75)) == []
    motivos = fallas(Metricas(0.80, None, 0.60))
    assert any("mAP@50 jugador 0.800 por debajo del mínimo 0.85" in m for m in motivos)
    assert any("IDF1 0.600 por debajo del mínimo 0.70" in m for m in motivos)


def test_veredicto_no_empeorar_la_version_activa():
    activa = {"version": "v3", "map50_jugador": 0.92, "map50_balon": 0.70, "idf1": 0.80}
    motivos = fallas(Metricas(0.90, 0.75, 0.85), activa)
    assert motivos == ["mAP@50 jugador 0.900 peor que la versión activa v3 (0.920)"]
    assert fallas(Metricas(0.93, 0.70, 0.80), activa) == []


def test_sin_balon_medido_frente_a_una_activa_que_lo_tiene():
    activa = {"version": "v3", "map50_balon": 0.70}
    assert fallas(Metricas(0.90, None, 0.80), activa) == [
        "mAP@50 balón sin medir (la versión activa tiene 0.70)"
    ]


# ---------- comando completo ----------

def test_pasa_imprime_metricas_y_sale_con_0(tmp_path, capsys):
    ruta = _anotaciones(tmp_path)
    codigo = correr(_args(tmp_path, ruta), _detector_perfecto(cargar_anotaciones(ruta)))
    salida = json.loads(capsys.readouterr().out)
    assert codigo == 0
    assert salida["pasa"] is True
    assert salida["cuadros_evaluados"] == 10


def test_falla_sale_con_1_y_no_registra(tmp_path, capsys):
    ruta = _anotaciones(tmp_path)
    api = ApiFalsa()

    def malo(_p, _c):
        yield 0, []  # no detecta nada

    codigo = correr(_args(tmp_path, ruta, registrar=True, nombre="f", version="v4",
                          archivo_url="https://x/f.pt"), malo, api)
    assert codigo == 1
    assert json.loads(capsys.readouterr().out)["pasa"] is False
    assert api.registrados == []


def test_peor_que_la_activa_no_se_registra(tmp_path, capsys):
    ruta = _anotaciones(tmp_path, con_balon=False)
    verdad = cargar_anotaciones(ruta)

    def con_un_jugador_perdido(_p, _c):
        for i, dets in _detector_perfecto(verdad)("p", "c"):
            yield i, [d for d in dets if not (d.tid == 3 and i % 2)]  # pierde al 3 a veces

    api = ApiFalsa(activo={"version": "v3", "map50_jugador": 0.99, "idf1": 0.99})
    codigo = correr(_args(tmp_path, ruta, registrar=True, nombre="f", version="v4",
                          archivo_url="https://x/f.pt"), con_un_jugador_perdido, api)
    salida = json.loads(capsys.readouterr().out)
    assert codigo == 1
    assert any("peor que la versión activa v3" in m for m in salida["fallas"])
    assert api.registrados == []


def test_si_pasa_se_registra_con_sus_metricas_sin_activar(tmp_path, capsys):
    ruta = _anotaciones(tmp_path)
    api = ApiFalsa(activo={"version": "v3", "map50_jugador": 0.90, "idf1": 0.75})
    codigo = correr(_args(tmp_path, ruta, registrar=True, nombre="futbol", version="v4",
                          archivo_url="https://cdn/futbol-v4.pt"),
                    _detector_perfecto(cargar_anotaciones(ruta)), api)
    assert codigo == 0
    (datos,) = api.registrados
    assert datos["version"] == "v4"
    assert datos["map50_jugador"] == 1.0
    assert datos["idf1"] == 1.0
    assert "activo" not in datos
    assert "10 cuadros anotados" in datos["notas"]
    assert "sin activar" in capsys.readouterr().out


def test_registrar_exige_los_datos_de_la_version():
    with pytest.raises(SystemExit):
        argumentos(["--pesos", "p.pt", "--clip", "c.mp4", "--anotaciones", "a.json",
                    "--registrar"])
