# ruff: noqa: F811 -- fixtures importadas se solicitan como parámetros de pytest
import base64

import cv2
import numpy as np
from test_vision_procesamiento import (  # noqa: F401 - fixtures compartidas
    _club,
    _video_subido,
    almacen,
    cliente,
    mp4,
    posiciones,
)


async def test_automatico_encola_sin_inventar_una_matriz(cliente, mp4):
    club = await _club(cliente, "auto", calibrar=False)
    video = await _video_subido(cliente, club, mp4)
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/calibracion", headers=club["auth"],
        json={"modo": "AUTOMATICA", "referencia": {"tipo": "VIDEO", "video_id": video["id"]}})
    assert r.status_code == 201, r.text
    assert r.json()["matriz_h"] is None
    assert r.json()["valida"] is False
    r = await cliente.post(f"/api/vision/videos/{video['id']}/procesar", headers=club["auth"], json={})
    assert r.status_code == 200, r.text
    r = await cliente.post("/api/vision/trabajos/tomar", headers=club["auth"])
    assert r.status_code == 200, r.text
    assert r.json()["modo_calibracion"] == "AUTOMATICA"
    assert r.json()["matriz_h"] is None


async def test_referencia_no_se_puede_aplicar_a_otro_video(cliente, mp4):
    club = await _club(cliente, "fuente", calibrar=False)
    uno = await _video_subido(cliente, club, mp4)
    dos = await _video_subido(cliente, club, mp4)
    r = await cliente.post(f"/api/vision/partidos/{club['partido_id']}/calibracion", headers=club["auth"],
        json={"modo": "AUTOMATICA", "referencia": {"tipo": "VIDEO", "video_id": uno["id"]}})
    assert r.status_code == 201
    r = await cliente.post(f"/api/vision/videos/{dos['id']}/procesar", headers=club["auth"], json={})
    assert r.status_code == 409


async def test_cuadro_conserva_resolucion_pts_y_aislamiento(cliente, mp4):
    club = await _club(cliente, "cuadro", calibrar=False)
    otro = await _club(cliente, "otro", calibrar=False)
    video = await _video_subido(cliente, club, mp4)
    url = f"/api/vision/videos/{video['id']}/cuadro?t_s=0.4"
    assert (await cliente.get(url, headers=otro["auth"])).status_code == 404
    r = await cliente.get(url, headers=club["auth"])
    assert r.status_code == 200, r.text
    datos = r.json()
    img = cv2.imdecode(np.frombuffer(base64.b64decode(datos["imagen_base64"]), np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[:2] == (48, 64)
    assert abs(datos["tiempo_s"] - .4) < .05
    assert datos["cuadro_indice"] == 10
