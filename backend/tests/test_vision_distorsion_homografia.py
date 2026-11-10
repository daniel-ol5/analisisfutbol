"""Corrección del lente integrada con la homografía  —  T-036 (CU-23).

Criterio de finalización: después de corregir, un punto cercano al borde tiene
un error comparable al de un punto central.

Se reusa la cámara sintética de test_vision_distorsion.py: gran angular con
distorsión de barril, en la tribuna, mirando una cancha de 105 x 68.
"""

import threading

import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from test_vision_calibracion_previa import _auth, _club, _partido
from test_vision_distorsion import (
    ALTO,
    ANCHO,
    MARCAS_M,
    PATRON,
    POSES,
    D,
    K,
    _a_pixeles,
    _pose,
    _renderizar_tablero,
)

from app.main import app
from app.vision import service
from app.vision.calibracion import CalibracionIntrinseca, corregir_puntos
from app.vision.homografia import calcular_homografia

INTRINSECA = {"matriz_camara": K.tolist(), "coef_distorsion": D.tolist(),
              "tamano_imagen": [ANCHO, ALTO]}
CENTRO_M = np.array([[50.0, 30.0], [58.0, 38.0], [45.0, 36.0]])
BORDE_M = np.array([[6.0, 3.0], [99.0, 3.0], [8.0, 64.0], [97.0, 65.0], [52.0, 66.0]])


@pytest.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _cuerpo(**extra) -> dict:
    """Las marcas de la cancha tal como se ven con el lente (sin corregir)."""
    px = _a_pixeles(MARCAS_M)
    return {"puntos_imagen": [{"x": float(x), "y": float(y)} for x, y in px],
            "puntos_cancha": [{"x": float(x), "y": float(y)} for x, y in MARCAS_M],
            **extra}


async def _calibrar(cliente, club, **extra) -> dict:
    partido = await _partido(cliente, club, "Estadio")
    r = await cliente.post(f"/api/vision/partidos/{partido}/calibracion",
                           headers=club["auth"], json=_cuerpo(**extra))
    assert r.status_code == 201, r.text
    return r.json()


def _a_metros(h: list[list[float]], px: np.ndarray) -> np.ndarray:
    homogeneos = np.column_stack([px, np.ones(len(px))]) @ np.asarray(h).T
    return homogeneos[:, :2] / homogeneos[:, 2:]


def _errores_m(h: list[list[float]], verdaderos_m: np.ndarray, corregir: bool) -> np.ndarray:
    """Error en metros de jugadores que NO se usaron para calibrar. Con
    `corregir`, cada pie se corrige igual que lo hará el worker (alfa=0)."""
    px = _a_pixeles(verdaderos_m)
    if corregir:
        px = corregir_puntos(px, CalibracionIntrinseca.desde_dict(INTRINSECA), alfa=0.0)
    return np.linalg.norm(_a_metros(h, px) - verdaderos_m, axis=1)


# ---------------- Criterio de finalización ----------------

async def test_con_la_intrinseca_el_borde_queda_como_el_centro(cliente):
    club = await _club(cliente, "a")
    sin = await _calibrar(cliente, club)
    con = await _calibrar(cliente, club, **INTRINSECA)

    sin_c, sin_b = _errores_m(sin["matriz_h"], CENTRO_M, False), _errores_m(
        sin["matriz_h"], BORDE_M, False)
    con_c, con_b = _errores_m(con["matriz_h"], CENTRO_M, True), _errores_m(
        con["matriz_h"], BORDE_M, True)

    # Sin corregir, la homografía no puede representar la curva del lente
    assert sin_b.max() > 1.0, f"sin corregir, borde {sin_b.max():.2f} m"
    assert sin_c.max() < sin_b.max()
    # Corregido: el borde queda en el orden del centro (y de centímetros)
    assert con_b.max() < 0.10, f"corregido, borde {con_b.max():.3f} m"
    assert con_b.max() < con_c.max() + 0.05
    assert con_b.max() < sin_b.max() / 10


async def test_el_error_de_reproyeccion_informado_baja(cliente):
    """CU-21 informa el error sobre los propios puntos marcados."""
    club = await _club(cliente, "a")
    sin = await _calibrar(cliente, club)
    con = await _calibrar(cliente, club, **INTRINSECA)

    assert sin["error_max_m"] > 0.5
    assert con["error_max_m"] < 0.05
    assert con["error_medio_m"] < sin["error_medio_m"] / 10


async def test_validar_tambien_corrige(cliente):
    club = await _club(cliente, "a")
    r_sin = await cliente.post("/api/vision/partidos/1/calibracion/validar",
                               headers=club["auth"], json=_cuerpo())
    r_con = await cliente.post("/api/vision/partidos/1/calibracion/validar",
                               headers=club["auth"], json=_cuerpo(**INTRINSECA))
    assert r_con.json()["error_max_m"] < r_sin.json()["error_max_m"] / 10


# ---------------- Sin intrínseca, todo igual que antes ----------------

async def test_sin_datos_de_distorsion_la_homografia_no_cambia(cliente):
    club = await _club(cliente, "a")
    guardada = await _calibrar(cliente, club)

    px = _a_pixeles(MARCAS_M)
    directa = calcular_homografia(px.tolist(), MARCAS_M.tolist())
    assert guardada["matriz_h"] == directa.matriz
    assert guardada["error_medio_m"] == directa.error_medio_m
    assert (guardada["matriz_camara"], guardada["tamano_imagen"]) == (None, None)


async def test_solo_coef_distorsion_se_acepta_como_antes_y_no_corrige(cliente):
    club = await _club(cliente, "a")
    sin = await _calibrar(cliente, club)
    solo_coef = await _calibrar(cliente, club, coef_distorsion=D.tolist())

    assert solo_coef["matriz_h"] == sin["matriz_h"]
    assert solo_coef["coef_distorsion"] == D.tolist()


# ---------------- Contrato: los tres campos van juntos ----------------

@pytest.mark.parametrize("parcial", [
    {"matriz_camara": K.tolist()},
    {"tamano_imagen": [ANCHO, ALTO]},
    {"matriz_camara": K.tolist(), "tamano_imagen": [ANCHO, ALTO]},
    {"matriz_camara": K.tolist(), "coef_distorsion": D.tolist()},
    {"tamano_imagen": [ANCHO, ALTO], "coef_distorsion": D.tolist()},
])
async def test_intrinseca_incompleta_es_422(cliente, parcial):
    club = await _club(cliente, "a")
    r = await cliente.post("/api/vision/partidos/1/calibracion", headers=club["auth"],
                           json=_cuerpo(**parcial))
    assert r.status_code == 422
    assert "van juntos" in r.text


@pytest.mark.parametrize(("campo", "valor", "texto"), [
    ("matriz_camara", [[1, 0, 1], [0, 1, 1]], "3x3"),
    ("matriz_camara", [[-380, 0, 322], [0, 380, 238], [0, 0, 1]], "fx y fy"),
    ("matriz_camara", [[380, 0, 322], [0, 380, 238], [0, 1, 1]], "ultima fila"),
    ("coef_distorsion", [0.1, 0.2, 0.3], "coeficientes"),
    ("tamano_imagen", [0, 480], "greater than 0"),
    ("tamano_imagen", [640, 480, 3], "at most 2"),
])
async def test_intrinseca_mal_formada_es_422(cliente, campo, valor, texto):
    club = await _club(cliente, "a")
    r = await cliente.post("/api/vision/partidos/1/calibracion", headers=club["auth"],
                           json=_cuerpo(**{**INTRINSECA, campo: valor}))
    assert r.status_code == 422
    assert texto in r.text


async def test_se_guarda_y_se_devuelve(cliente):
    club = await _club(cliente, "a")
    guardada = await _calibrar(cliente, club, **INTRINSECA)
    for campo, valor in INTRINSECA.items():
        assert guardada[campo] == valor, campo

    r = await cliente.get(f"/api/vision/partidos/{guardada['partido_id']}/calibracion",
                          headers=club["auth"])
    assert r.json()["matriz_camara"] == K.tolist()
    # Y la calibración previa de la sede (T-035) la trae completa
    r = await cliente.get("/api/vision/sedes/Estadio/calibracion-previa", headers=club["auth"])
    assert (r.json()["matriz_camara"], r.json()["tamano_imagen"]) == (K.tolist(), [ANCHO, ALTO])


async def test_acepta_el_resultado_de_calibracion_intrinseca_tal_cual(cliente):
    """Los campos extra de POST /calibracion-intrinseca se ignoran."""
    club = await _club(cliente, "a")
    guardada = await _calibrar(cliente, club, **INTRINSECA, error_reproyeccion_px=0.2,
                               imagenes_usadas=15)
    assert guardada["error_max_m"] < 0.05


# ---------------- POST /calibracion-intrinseca ----------------

def _png(imagen: np.ndarray) -> bytes:
    ok, datos = cv2.imencode(".png", imagen)
    assert ok
    return datos.tobytes()


@pytest.fixture(scope="module")
def fotos_tablero() -> list[bytes]:
    """Centro, inclinadas y llegando a las esquinas del cuadro."""
    elegidas = [0, 1, 2, 3, 4, 5, 6, 12, 13, 14, 15, 16, 17]
    return [_png(_renderizar_tablero(*_pose(*POSES[i]))) for i in elegidas]


def _archivos(fotos: list[bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("imagenes", (f"tablero{i}.png", f, "image/png")) for i, f in enumerate(fotos)]


async def _intrinseca(cliente, club, fotos, **params):
    return await cliente.post("/api/vision/calibracion-intrinseca", headers=club["auth"],
                              files=_archivos(fotos), params=params)


async def test_calibra_el_lente_con_fotos_del_tablero(cliente, fotos_tablero):
    club = await _club(cliente, "a")
    r = await _intrinseca(cliente, club, fotos_tablero,
                          columnas=PATRON[0], filas=PATRON[1])
    assert r.status_code == 200, r.text
    datos = r.json()

    assert datos["tamano_imagen"] == [ANCHO, ALTO]
    assert datos["imagenes_usadas"] == len(fotos_tablero)
    assert datos["error_reproyeccion_px"] < 0.5
    k = np.asarray(datos["matriz_camara"])
    assert k[0, 0] == pytest.approx(K[0, 0], rel=0.02)
    assert k[1, 1] == pytest.approx(K[1, 1], rel=0.02)
    assert datos["coef_distorsion"][0] == pytest.approx(D[0], abs=0.03)


async def test_flujo_en_dos_pasos(cliente, fotos_tablero):
    """Primero calibracion-intrinseca, después el resultado tal cual en la cancha."""
    club = await _club(cliente, "a")
    intrinseca = (await _intrinseca(cliente, club, fotos_tablero)).json()
    guardada = await _calibrar(cliente, club, **intrinseca)

    assert guardada["valida"] is True
    assert guardada["matriz_camara"] == intrinseca["matriz_camara"]
    assert guardada["error_max_m"] < 0.15
    errores = _errores_m_con(guardada, intrinseca)
    assert errores["borde"] < errores["centro"] + 0.15


def _errores_m_con(guardada: dict, intrinseca: dict) -> dict[str, float]:
    cal = CalibracionIntrinseca.desde_dict(intrinseca)
    resultado = {}
    for nombre, verdaderos in (("centro", CENTRO_M), ("borde", BORDE_M)):
        px = corregir_puntos(_a_pixeles(verdaderos), cal, alfa=0.0)
        resultado[nombre] = float(np.linalg.norm(
            _a_metros(guardada["matriz_h"], px) - verdaderos, axis=1).max())
    return resultado


async def test_opencv_corre_fuera_del_event_loop(cliente, fotos_tablero, monkeypatch):
    hilos: list[threading.Thread] = []
    original = service.calibrar_intrinseca

    def espia(fotos, patron):
        hilos.append(threading.current_thread())
        return original(fotos, patron)

    monkeypatch.setattr(service, "calibrar_intrinseca", espia)
    club = await _club(cliente, "a")
    assert (await _intrinseca(cliente, club, fotos_tablero[:5])).status_code == 200
    assert hilos and hilos[0] is not threading.main_thread()


@pytest.mark.parametrize("cantidad", [4, 21])
async def test_entre_5_y_20_fotos(cliente, fotos_tablero, cantidad):
    club = await _club(cliente, "a")
    fotos = (fotos_tablero * 2)[:cantidad]
    r = await _intrinseca(cliente, club, fotos)
    assert r.status_code == 422
    assert f"llegaron {cantidad}" in r.text


async def test_una_foto_de_mas_de_10_mb_es_413(cliente, fotos_tablero):
    club = await _club(cliente, "a")
    pesada = fotos_tablero[0] + b"\0" * (10 * 1024 * 1024)
    r = await _intrinseca(cliente, club, [*fotos_tablero[:4], pesada])
    assert r.status_code == 413
    assert "foto 4" in r.text


async def test_una_foto_ilegible_es_422(cliente, fotos_tablero):
    club = await _club(cliente, "a")
    r = await _intrinseca(cliente, club, [*fotos_tablero[:2], b"no es una imagen",
                                          *fotos_tablero[2:5]])
    assert r.status_code == 422
    assert "La foto 2 no es una imagen" in r.text


async def test_sin_tablero_visible_es_422(cliente):
    club = await _club(cliente, "a")
    gris = _png(np.full((ALTO, ANCHO), 128, np.uint8))
    r = await _intrinseca(cliente, club, [gris] * 5)
    assert r.status_code == 422
    assert "Se detectó el patrón en 0 imágenes" in r.text


async def test_patron_equivocado_es_422(cliente, fotos_tablero):
    club = await _club(cliente, "a")
    r = await _intrinseca(cliente, club, fotos_tablero[:5], columnas=7, filas=5)
    assert r.status_code == 422
    assert "7 x 5" in r.text


async def test_fotos_de_distinto_tamano_son_422(cliente, fotos_tablero):
    club = await _club(cliente, "a")
    chica = _png(np.full((240, 320), 128, np.uint8))
    r = await _intrinseca(cliente, club, [*fotos_tablero[:4], chica])
    assert r.status_code == 422
    assert "deben medir" in r.text


async def test_sin_sesion_es_401(cliente, fotos_tablero):
    r = await cliente.post("/api/vision/calibracion-intrinseca",
                           files=_archivos(fotos_tablero[:5]))
    assert r.status_code == 401


@pytest.mark.parametrize("rol", ["DT", "ASISTENTE"])
async def test_solo_admin_y_analista(cliente, fotos_tablero, rol):
    club = await _club(cliente, "a")
    email = f"{rol.lower()}@test.com"
    await cliente.post("/api/seguridad/usuarios", headers=club["auth"],
                       json={"email": email, "password": "password123", "rol": rol})
    r = await cliente.post("/api/seguridad/login", json={"email": email, "password": "password123"})
    otro = {"auth": _auth(r.json()["access_token"])}
    assert (await _intrinseca(cliente, otro, fotos_tablero[:5])).status_code == 403
