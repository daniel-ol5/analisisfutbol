"""Pruebas del procesamiento diferido (T-061), sin GPU ni ultralytics.

Cuadros sintéticos (cancha verde con camisetas pintadas), detecciones armadas
a mano y un backend falso que registra lo que recibiría.
"""

import io
import json
import urllib.error
from pathlib import Path

import numpy as np
import pytest

from procesamiento.api import ApiBackend, Cancelado, ErrorApi
from procesamiento.mensajes import Contexto, armar_mensaje, equipos_de
from procesamiento.worker import atender_uno, procesar_trabajo
from seguimiento.tipos import Clase, Deteccion, EquipoDetectado

AZUL = "#1E5AA8"   # camiseta propia
ROJO = "#C8102E"   # rival
CESPED_BGR = (40, 140, 40)

# 10 píxeles = 1 metro: la proyección se verifica a ojo.
H_ESCALA = [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]]


def _bgr(color_hex: str) -> tuple[int, int, int]:
    h = color_hex.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return b, g, r


def _cuadro(jugadores: list[tuple[tuple[int, int, int, int], str]]) -> np.ndarray:
    cuadro = np.zeros((400, 600, 3), dtype=np.uint8)
    cuadro[:] = CESPED_BGR
    for (x1, y1, x2, y2), color in jugadores:
        cuadro[y1:y2, x1:x2] = _bgr(color)
    return cuadro


def _det(tid, caja, clase=Clase.JUGADOR, conf=0.9) -> Deteccion:
    return Deteccion.desde_caja(tid, clase, tuple(float(v) for v in caja), conf)


CAJAS = {
    1: ((50, 50, 80, 130), AZUL),
    2: ((150, 60, 180, 140), AZUL),
    3: ((300, 70, 330, 150), ROJO),
    4: ((420, 80, 450, 160), ROJO),
}


def _escena():
    cuadro = _cuadro(list(CAJAS.values()))
    detecciones = [_det(tid, caja) for tid, (caja, _) in CAJAS.items()]
    return cuadro, detecciones


def _ctx(es_local=True, color_rival=ROJO) -> Contexto:
    return Contexto(partido_id=7, homografia=np.array(H_ESCALA, dtype=float),
                    es_local=es_local, color_propio=AZUL, color_rival=color_rival,
                    fps_muestreo=5.0)


# ---------- mensajes.py: une color de equipo y homografía ----------

@pytest.mark.parametrize("color_rival", [ROJO, None])
def test_equipos_con_y_sin_color_del_rival(color_rival):
    cuadro, detecciones = _escena()
    equipos = equipos_de(cuadro, detecciones, _ctx(color_rival=color_rival))
    assert equipos == [EquipoDetectado.LOCAL] * 2 + [EquipoDetectado.VISITANTE] * 2


@pytest.mark.parametrize("color_rival", [ROJO, None])
def test_de_visitante_el_propio_es_visitante(color_rival):
    cuadro, detecciones = _escena()
    equipos = equipos_de(cuadro, detecciones, _ctx(es_local=False, color_rival=color_rival))
    assert equipos == [EquipoDetectado.VISITANTE] * 2 + [EquipoDetectado.LOCAL] * 2


def test_arbitro_del_modelo_propio_y_caja_fuera_del_cuadro():
    cuadro, detecciones = _escena()
    detecciones.append(_det(5, (250, 200, 270, 260), clase=Clase.ARBITRO))
    detecciones.append(_det(6, (900, 900, 950, 990)))  # fuera del cuadro
    equipos = equipos_de(cuadro, detecciones, _ctx())
    assert equipos[4] == EquipoDetectado.ARBITRO
    assert equipos[5] == EquipoDetectado.DESCONOCIDO


def test_un_solo_jugador_sin_color_rival():
    cuadro = _cuadro([CAJAS[1]])
    assert equipos_de(cuadro, [_det(1, CAJAS[1][0])], _ctx(color_rival=None)) == [
        EquipoDetectado.LOCAL
    ]


def test_mensaje_con_el_contrato_del_worker_en_vivo():
    cuadro, detecciones = _escena()
    detecciones.append(_det(0, (295, 195, 305, 205), clase=Clase.BALON, conf=0.4))
    detecciones.append(_det(0, (395, 295, 405, 305), clase=Clase.BALON, conf=0.8))

    m = armar_mensaje(_ctx(), 12.3456, cuadro, detecciones)

    # Mismas claves que backend/app/partido/schemas.py::MensajeWorker.
    assert set(m) == {"partido", "t", "jugadores", "balon", "calidad"}
    assert set(m["calidad"]) == {"worker_conectado", "fps", "jugadores_detectados",
                                 "balon_visible", "retraso_s", "degradado", "motivo"}
    assert m["partido"] == 7
    assert m["t"] == 12.346
    assert [j["tid"] for j in m["jugadores"]] == [1, 2, 3, 4]
    # Punto de apoyo (pie), no el centro: jugador 1 en x=(50+80)/2=65 px, y=130 px.
    assert (m["jugadores"][0]["x"], m["jugadores"][0]["y"]) == (6.5, 13.0)
    assert {j["equipo"] for j in m["jugadores"]} == {"LOCAL", "VISITANTE"}
    # La pelota más segura, proyectada.
    assert m["balon"]["conf"] == 0.8
    assert (m["balon"]["x"], m["balon"]["y"]) == (40.0, 30.5)
    assert m["calidad"]["jugadores_detectados"] == 4
    assert m["calidad"]["degradado"] is True
    assert m["calidad"]["balon_visible"] is True
    json.dumps(m)  # serializable tal cual


def test_mensaje_sin_detecciones():
    m = armar_mensaje(_ctx(), 0, _cuadro([]), [])
    assert m["jugadores"] == []
    assert m["balon"] is None
    assert m["calidad"]["balon_visible"] is False


# ---------- worker.py: lotes, progreso, cancelación ----------

class BackendFalso:
    def __init__(self, trabajo=None, cancelar_en_lote=None):
        self.trabajo = trabajo
        self.lotes: list[tuple[int, list[dict]]] = []
        self.terminado: tuple[bool, str | None] | None = None
        self.cancelar_en_lote = cancelar_en_lote
        self.descargados: list[Path] = []

    def tomar(self):
        trabajo, self.trabajo = self.trabajo, None
        return trabajo

    def descargar(self, ruta, destino):
        destino.write_bytes(b"video")
        self.descargados.append(destino)
        return destino

    def resultados(self, video_id, progreso_pct, muestras):
        if self.cancelar_en_lote is not None and len(self.lotes) == self.cancelar_en_lote:
            raise Cancelado("cancelado")
        self.lotes.append((progreso_pct, muestras))

    def terminar(self, video_id, ok, mensaje_error=None):
        self.terminado = (ok, mensaje_error)


TRABAJO = {
    "video_id": 3, "partido_id": 7, "archivo": "/api/vision/videos/3/archivo",
    "nombre": "fecha.mp4", "matriz_h": H_ESCALA, "es_local": True,
    "color_propio": AZUL, "color_rival": ROJO, "modelo": None,
}


def _cuadros(n):
    cuadro, detecciones = _escena()
    return [(cuadro, detecciones) for _ in range(n)]


def test_procesar_manda_lotes_con_progreso_y_cierra():
    backend = BackendFalso()
    # 60 muestras de un video de 30 fps cada 6 cuadros = 360 cuadros.
    enviadas = procesar_trabajo(TRABAJO, _cuadros(60), backend, fps_video=30, total_cuadros=360)

    assert enviadas == 60
    assert [len(m) for _, m in backend.lotes] == [25, 25, 10]
    progresos = [p for p, _ in backend.lotes]
    assert progresos == sorted(progresos)
    assert progresos[-1] == 99  # el 100 lo pone el backend
    assert backend.terminado == (True, None)
    tiempos = [m["t"] for _, lote in backend.lotes for m in lote]
    assert tiempos[:3] == [0, 0.2, 0.4]  # 5 muestras por segundo
    assert all(m["partido"] == 7 for _, lote in backend.lotes for m in lote)


def test_una_cancelacion_corta_sin_cerrar():
    backend = BackendFalso(cancelar_en_lote=1)
    with pytest.raises(Cancelado):
        procesar_trabajo(TRABAJO, _cuadros(60), backend, fps_video=30, total_cuadros=360)
    assert len(backend.lotes) == 1
    assert backend.terminado is None


def test_video_sin_fps_es_un_error():
    with pytest.raises(ValueError):
        procesar_trabajo(TRABAJO, [], BackendFalso(), fps_video=0, total_cuadros=0)


def test_atender_sin_trabajos(tmp_path):
    assert atender_uno(BackendFalso(), lambda t, r: ([], 30, 0), tmp_path) is False


def test_atender_procesa_y_borra_el_video_descargado(tmp_path):
    backend = BackendFalso(trabajo=dict(TRABAJO))
    assert atender_uno(backend, lambda t, r: (_cuadros(3), 30, 18), tmp_path) is True
    assert backend.terminado == (True, None)
    assert not backend.descargados[0].exists()


def test_una_falla_del_pipeline_llega_al_analista(tmp_path):
    backend = BackendFalso(trabajo=dict(TRABAJO))

    def roto(trabajo, ruta):
        raise RuntimeError("CUDA out of memory")

    assert atender_uno(backend, roto, tmp_path) is True
    ok, mensaje = backend.terminado
    assert ok is False
    assert mensaje == "RuntimeError: CUDA out of memory"
    assert not backend.descargados[0].exists()


def test_una_cancelacion_no_se_informa_como_error(tmp_path):
    backend = BackendFalso(trabajo=dict(TRABAJO), cancelar_en_lote=0)
    atender_uno(backend, lambda t, r: (_cuadros(30), 30, 180), tmp_path)
    assert backend.terminado is None


# ---------- api.py: sesión vencida y cancelación ----------

class _Respuesta(io.BytesIO):
    def __init__(self, cuerpo=b"", status=200):
        super().__init__(cuerpo)
        self.status = status


def _http_error(codigo, detalle="x"):
    return urllib.error.HTTPError("http://t", codigo, "error", {},
                                  io.BytesIO(json.dumps({"detail": detalle}).encode()))


class Servidor:
    """Hace de urlopen: responde según la lista de respuestas o excepciones."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.pedidos = []

    def __call__(self, pedido, timeout=None):
        self.pedidos.append((pedido.get_method(), pedido.full_url,
                             pedido.get_header("Authorization")))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _login(token):
    return _Respuesta(json.dumps({"access_token": token}).encode())


def test_vuelve_a_iniciar_sesion_si_el_token_vence():
    servidor = Servidor(_login("viejo"), _http_error(401), _login("nuevo"), _Respuesta(status=204))
    api = ApiBackend("http://api/api", "a@b.com", "x", abrir=servidor)

    assert api.tomar() is None
    metodos = [(m, u.split("/api")[-1]) for m, u, _ in servidor.pedidos]
    assert metodos == [("POST", "/seguridad/login"), ("POST", "/vision/trabajos/tomar"),
                       ("POST", "/seguridad/login"), ("POST", "/vision/trabajos/tomar")]
    assert servidor.pedidos[-1][2] == "Bearer nuevo"


def test_un_409_en_resultados_es_cancelacion():
    servidor = Servidor(_login("t"), _http_error(409, "El procesamiento se canceló"))
    api = ApiBackend("http://api/api", "a@b.com", "x", abrir=servidor)
    with pytest.raises(Cancelado):
        api.resultados(3, 10, [])


def test_otros_errores_llegan_con_su_detalle():
    servidor = Servidor(_login("t"), _http_error(422, "Las muestras son del partido [9]"))
    api = ApiBackend("http://api/api", "a@b.com", "x", abrir=servidor)
    with pytest.raises(ErrorApi) as e:
        api.resultados(3, 10, [])
    assert e.value.codigo == 422
    assert "partido [9]" in e.value.detalle


def test_tomar_devuelve_el_trabajo():
    servidor = Servidor(_login("t"), _Respuesta(json.dumps(TRABAJO).encode()))
    api = ApiBackend("http://api/api", "a@b.com", "x", abrir=servidor)
    assert api.tomar()["video_id"] == 3
    assert servidor.pedidos[1][1] == "http://api/api/vision/trabajos/tomar"


def test_descarga_usa_la_ruta_del_trabajo(tmp_path):
    servidor = Servidor(_login("t"), _Respuesta(b"contenido-del-video"))
    api = ApiBackend("http://api/api", "a@b.com", "x", abrir=servidor)
    destino = api.descargar("/api/vision/videos/3/archivo", tmp_path / "v.mp4")
    assert destino.read_bytes() == b"contenido-del-video"
    assert servidor.pedidos[1][1] == "http://api/api/vision/videos/3/archivo"
