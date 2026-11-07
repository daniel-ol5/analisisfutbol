from seguimiento.tipos import Clase, Deteccion


def test_punto_de_apoyo_es_el_pie_no_el_centro_de_la_caja():
    caja = (10.0, 20.0, 30.0, 80.0)

    d = Deteccion.desde_caja(tid=5, clase=Clase.JUGADOR, caja=caja, conf=0.9)

    # (x1+x2)/2, y2 -- nunca (y1+y2)/2, que seria el centro de la caja
    assert d.punto_apoyo == (20.0, 80.0)
    assert d.tid == 5
    assert d.clase is Clase.JUGADOR
    assert d.caja == caja
    assert d.conf == 0.9
