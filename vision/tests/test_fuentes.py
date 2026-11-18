from threading import Event
from types import SimpleNamespace

import numpy as np
from deteccion.modelo import ConfigModelo
from procesamiento.fuente import seguir_con_cuadros


def test_fuente_usa_pts_del_decodificador_y_libera_archivo(monkeypatch):
    pts = [0, 41, 205, 254]

    class Captura:
        i = -1
        liberada = False

        def isOpened(self): return True
        def get(self, propiedad):
            from procesamiento.fuente import cv2
            return 30 if propiedad == cv2.CAP_PROP_FPS else pts[self.i]
        def read(self):
            self.i += 1
            return (True, np.zeros((10, 10, 3), np.uint8)) if self.i < 4 else (False, None)
        def release(self): self.liberada = True

    captura = Captura()
    monkeypatch.setattr("procesamiento.fuente.cv2.VideoCapture", lambda ruta: captura)
    modelo = SimpleNamespace(config=ConfigModelo(dispositivo="cpu"),
        modelo=SimpleNamespace(track=lambda *args, **kwargs: [SimpleNamespace(boxes=None)]))
    cuadros = list(seguir_con_cuadros(modelo, "prueba.mp4", vid_stride=2))
    assert [c.t for c in cuadros] == [0, 0.205]
    assert [c.indice for c in cuadros] == [0, 2]
    assert captura.liberada


def test_directo_descarta_cuadros_atrasados_en_vez_de_acumular_una_cola(monkeypatch):
    from procesamiento.directo import cuadros_recientes

    permitir = Event()
    termino = Event()

    class Captura:
        indice = -1
        liberada = False

        def isOpened(self): return True
        def set(self, *args): return True
        def get(self, *args): return 30
        def read(self):
            self.indice += 1
            if self.indice > 0:
                permitir.wait(timeout=2)
            if self.indice > 10:
                termino.set()
                return False, None
            return True, np.full((4, 4, 3), self.indice, np.uint8)
        def release(self): self.liberada = True

    captura = Captura()
    monkeypatch.setattr("procesamiento.directo.cv2.VideoCapture", lambda fuente: captura)
    fuente = cuadros_recientes("0")
    try:
        assert next(fuente)[0][0, 0, 0] == 0
        permitir.set()
        assert termino.wait(timeout=2)
        assert next(fuente)[0][0, 0, 0] == 10
    finally:
        permitir.set()
        fuente.close()
    assert captura.liberada
