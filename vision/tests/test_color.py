"""Pruebas de CU-25 con recortes sinteticos: dos colores de camiseta con
ruido, mas un borde de cesped colandose (como pasa en un recorte real).

Criterio de aceptacion de CU-25: precision >= 90% sobre 200 recortes.
"""

import numpy as np
import pytest

from seguimiento.color import (
    ClasificacionJugador,
    ColoresEquipo,
    RecorteVacio,
    agrupar_equipos,
    clasificar_equipos,
    color_dominante,
    descartar_cesped,
    recortar_torso,
)
from seguimiento.tipos import EquipoDetectado

_RNG = np.random.default_rng(42)
_VERDE_CESPED_BGR = (40, 160, 40)  # BGR: cesped bajo luz normal


def _recorte_sintetico(color_bgr: tuple[int, int, int], ruido: int = 12,
                        alto: int = 30, ancho: int = 20) -> np.ndarray:
    base = np.array(color_bgr, dtype=np.int16)
    img = base + _RNG.integers(-ruido, ruido + 1, size=(alto, ancho, 3))
    img = np.clip(img, 0, 255).astype(np.uint8)
    # un borde de cesped de fondo, como se cuela en un recorte real
    img[:3, :] = _VERDE_CESPED_BGR
    img[-3:, :] = _VERDE_CESPED_BGR
    return img


# ---------------- recortar_torso ----------------

def test_recortar_torso_toma_el_pecho_no_la_caja_completa():
    cuadro = np.zeros((100, 50, 3), np.uint8)
    recorte = recortar_torso(cuadro, (10.0, 10.0, 30.0, 90.0))
    # alto de la caja: 80. del 15% al 55% -> 12 a 44 px -> 32 px de alto
    assert recorte.shape[0] == 32
    # ancho de la caja: 20. margen 20% de cada lado -> 12 px de ancho
    assert recorte.shape[1] == 12


def test_recortar_torso_caja_fuera_del_cuadro_falla():
    cuadro = np.zeros((20, 20, 3), np.uint8)
    with pytest.raises(RecorteVacio):
        recortar_torso(cuadro, (100.0, 100.0, 110.0, 110.0))


# ---------------- descartar_cesped ----------------

def test_descartar_cesped_excluye_el_verde_y_conserva_el_resto():
    recorte = _recorte_sintetico((200, 40, 40))  # azul con borde de cesped
    mascara = descartar_cesped(recorte)

    assert not mascara[0, :].any(), "la fila de cesped de arriba debe quedar fuera"
    assert not mascara[-1, :].any(), "la fila de cesped de abajo debe quedar fuera"
    assert mascara[len(recorte) // 2, :].all(), "el centro (camiseta) debe conservarse"


def test_color_dominante_de_recorte_todo_cesped_no_falla():
    todo_cesped = np.full((10, 10, 3), _VERDE_CESPED_BGR, np.uint8)
    color = color_dominante(todo_cesped)  # cae al recorte completo, sin mascara
    assert color.shape == (3,)
    assert np.isfinite(color).all()


def test_color_dominante_recorte_vacio_lanza_error():
    with pytest.raises(RecorteVacio):
        color_dominante(np.zeros((0, 0, 3), np.uint8))


# ---------------- agrupar_equipos (criterio de CU-25) ----------------

def test_agrupa_dos_colores_de_camiseta_con_precision_de_al_menos_90_por_ciento():
    equipo_a_bgr = (40, 40, 200)   # rojo
    equipo_b_bgr = (200, 120, 20)  # celeste/azul, bien separado del rojo en tono

    recortes = (
        [_recorte_sintetico(equipo_a_bgr) for _ in range(100)]
        + [_recorte_sintetico(equipo_b_bgr) for _ in range(100)]
    )
    verdad = np.array([0] * 100 + [1] * 100)

    colores = np.array([color_dominante(r) for r in recortes])
    etiquetas = agrupar_equipos(colores, k=2)

    # cv2.kmeans no promete que la etiqueta 0 sea el equipo A: se evaluan las
    # dos correspondencias posibles y se toma la mejor.
    precision = max((etiquetas == verdad).mean(), (etiquetas == 1 - verdad).mean())
    assert precision >= 0.90, f"precision {precision:.2%} sobre 200 recortes"


def test_camisetas_muy_similares_no_garantizan_la_separacion():
    """Documenta el limite: K-means por color no distingue tonos casi iguales."""
    rojo = (40, 40, 200)
    rojo_mas_oscuro = (30, 30, 150)

    recortes = (
        [_recorte_sintetico(rojo) for _ in range(20)]
        + [_recorte_sintetico(rojo_mas_oscuro) for _ in range(20)]
    )
    colores = np.array([color_dominante(r) for r in recortes])
    # No se afirma nada sobre el resultado: solo que no lanza excepciones.
    etiquetas = agrupar_equipos(colores, k=2)
    assert etiquetas.shape == (40,)


# ---------------- clasificar_equipos (HU-21, criterios 2 y 3) ----------------

# Mismos colores BGR que arriba, como hex #RRGGBB: lo que CU-10 registraria
# en Equipo.color_local / color_visitante.
_EQUIPO_A_BGR = (40, 40, 200)   # rojo    -> #C82828
_EQUIPO_B_BGR = (200, 120, 20)  # celeste -> #1478C8
_ARBITRO_BGR = (20, 20, 20)     # casi negro: lejos de ambos equipos

COLORES_PARTIDO = ColoresEquipo(color_local="#C82828", color_visitante="#1478C8")


def test_clasifica_segun_colores_registrados_no_clustering_ciego():
    """Criterio 2: compara contra los colores de CU-10, no un cluster sin identidad.

    A diferencia de `agrupar_equipos` (etiquetas 0/1 sin orden), aqui la
    etiqueta LOCAL/VISITANTE ya tiene significado: no hace falta evaluar las
    dos permutaciones posibles.
    """
    recortes = (
        [_recorte_sintetico(_EQUIPO_A_BGR) for _ in range(100)]
        + [_recorte_sintetico(_EQUIPO_B_BGR) for _ in range(100)]
    )
    verdad = [EquipoDetectado.LOCAL] * 100 + [EquipoDetectado.VISITANTE] * 100

    colores = [color_dominante(r) for r in recortes]
    clasificacion = clasificar_equipos(colores, COLORES_PARTIDO)

    aciertos = sum(c.equipo == v for c, v in zip(clasificacion, verdad, strict=True))
    precision = aciertos / len(verdad)
    assert precision >= 0.90, f"precision {precision:.2%} sobre 200 recortes"


def test_confianza_queda_siempre_entre_cero_y_uno():
    recortes = [_recorte_sintetico(_EQUIPO_A_BGR) for _ in range(30)]
    colores = [color_dominante(r) for r in recortes]
    clasificacion = clasificar_equipos(colores, COLORES_PARTIDO)

    assert all(isinstance(c, ClasificacionJugador) for c in clasificacion)
    assert all(0.0 <= c.confianza <= 1.0 for c in clasificacion)


def test_color_lejos_de_ambos_equipos_se_clasifica_como_arbitro():
    """Criterio 3: sin un color de arbitro registrado, se usa el umbral de
    distancia a los dos equipos."""
    recortes = [_recorte_sintetico(_ARBITRO_BGR) for _ in range(30)]
    colores = [color_dominante(r) for r in recortes]
    clasificacion = clasificar_equipos(colores, COLORES_PARTIDO)

    proporcion_arbitro = sum(c.equipo == EquipoDetectado.ARBITRO for c in clasificacion) / len(clasificacion)
    assert proporcion_arbitro >= 0.90, f"solo {proporcion_arbitro:.2%} se detecto como arbitro"


def test_color_de_arbitro_registrado_tiene_prioridad_sobre_el_umbral():
    """Si se registra `color_arbitro`, un color mas cercano a el que a
    cualquiera de los dos equipos se clasifica arbitro aunque no supere el
    umbral generico."""
    colores_con_arbitro = ColoresEquipo(
        color_local="#C82828", color_visitante="#1478C8", color_arbitro="#D7D700"
    )
    recortes = [_recorte_sintetico((0, 215, 215)) for _ in range(20)]  # amarillo, BGR
    colores = [color_dominante(r) for r in recortes]

    clasificacion = clasificar_equipos(colores, colores_con_arbitro)
    assert all(c.equipo == EquipoDetectado.ARBITRO for c in clasificacion)


def test_clasificar_equipos_lista_vacia():
    assert clasificar_equipos([], COLORES_PARTIDO) == []


def test_clasificar_equipos_con_pocos_jugadores_no_hace_kmeans_y_no_falla():
    """Con menos jugadores que `k`, no se puede correr K-means: se cae a
    comparar directo contra cada color registrado."""
    color_cercano_a_local = color_dominante(_recorte_sintetico(_EQUIPO_A_BGR))
    clasificacion = clasificar_equipos([color_cercano_a_local], COLORES_PARTIDO)

    assert len(clasificacion) == 1
    assert clasificacion[0].equipo == EquipoDetectado.LOCAL


def test_diferenciacion_camisetas_blancas_y_arbitro_negro():
    """Tottenham blanco vs Man City celeste vs Árbitro negro: deben discriminarse en CIELAB."""
    from seguimiento.color import ColoresEquipo, clasificar_equipos, color_dominante

    colores_premier = ColoresEquipo(color_local="#6CABDD", color_visitante="#FFFFFF")
    # Blanco puro y celeste
    recorte_blanco = _recorte_sintetico((245, 245, 245))
    recorte_celeste = _recorte_sintetico((220, 170, 100))
    recorte_arbitro = _recorte_sintetico((25, 25, 25))

    col_blanco = color_dominante(recorte_blanco)
    col_celeste = color_dominante(recorte_celeste)
    col_arbitro = color_dominante(recorte_arbitro)

    clasif = clasificar_equipos([col_blanco, col_celeste, col_arbitro], colores_premier)
    assert clasif[0].equipo == EquipoDetectado.VISITANTE  # Blanco
    assert clasif[1].equipo == EquipoDetectado.LOCAL      # Celeste
    assert clasif[2].equipo == EquipoDetectado.ARBITRO    # Negro


def test_clasificador_temporal_filtra_parpadeo():
    from seguimiento.color import ClasificadorTemporalEquipos

    clasificador = ClasificadorTemporalEquipos(ventana=5)
    # Simular 4 cuadros como LOCAL
    for _ in range(4):
        eq, _ = clasificador.registrar_y_suavizar(10, EquipoDetectado.LOCAL, 0.9)
        clasificador.avanzar_cuadro()
    assert eq == EquipoDetectado.LOCAL

    # Un cuadro con ruido de sombra clasificado erróneamente como VISITANTE
    eq, conf = clasificador.registrar_y_suavizar(10, EquipoDetectado.VISITANTE, 0.5)
    # Debe seguir siendo LOCAL por mayoría histórica
    assert eq == EquipoDetectado.LOCAL
    assert conf >= 0.8


# ---------------- CalibradorEquiposPartido (Fase F4) ----------------

def test_es_color_cesped():
    from seguimiento.color import es_color_cesped

    cesped = np.array([0.62, -0.18, 0.30])
    blanco = np.array([0.98, -0.02, 0.05])
    assert es_color_cesped(cesped) is True
    assert es_color_cesped(blanco) is False


def test_calibrador_equipos_partido_acumulacion_y_clustering():
    from seguimiento.color import CalibradorEquiposPartido, ColoresEquipo

    colores = ColoresEquipo(color_local="#C82828", color_visitante="#1478C8")
    calibrador = CalibradorEquiposPartido(colores_equipo=colores, min_muestras_calibracion=20)

    assert calibrador.calibrado is False
    # Acumular muestras sintéticas con ruido
    # Local: rojo BGR (40, 40, 200)
    # Visitante: celeste BGR (200, 120, 20)
    for _ in range(15):
        calibrador.acumular_muestra(color_dominante(_recorte_sintetico((40, 40, 200))))
        calibrador.acumular_muestra(color_dominante(_recorte_sintetico((200, 120, 20))))

    assert calibrador.calibrado is True
    assert calibrador.centroide_local is not None
    assert calibrador.centroide_visitante is not None


def test_calibrador_ignora_portero_y_arbitro_en_clustering():
    from seguimiento.color import CalibradorEquiposPartido, ColoresEquipo

    colores = ColoresEquipo(color_local="#C82828", color_visitante="#1478C8")
    calibrador = CalibradorEquiposPartido(colores_equipo=colores, min_muestras_calibracion=10)

    # Intentar acumular muestras marcadas como árbitro o portero
    for _ in range(10):
        calibrador.acumular_muestra(np.array([0.2, 0.0, 0.0]), es_arbitro=True)
        calibrador.acumular_muestra(np.array([0.8, 0.2, 0.2]), es_portero=True)

    assert calibrador.total_muestras == 0
    assert calibrador.calibrado is False


def test_calibrador_clasifica_portero_por_mitad_de_campo():
    from seguimiento.color import CalibradorEquiposPartido, ColoresEquipo

    colores = ColoresEquipo(color_local="#FFFFFF", color_visitante="#6CABDD")
    calibrador = CalibradorEquiposPartido(colores_equipo=colores)

    # Portero en x = 8.0m (mitad izquierda / arco local)
    res_izq = calibrador.clasificar_jugador(
        color=np.array([0.7, 0.1, 0.2]),  # color amarillo de portero
        posicion_m=(8.0, 34.0),
        es_portero=True,
        centroides_equipo_x=(30.0, 70.0),  # local en izquierda, visitante en derecha
    )
    assert res_izq.equipo == EquipoDetectado.LOCAL
    assert res_izq.confianza >= 0.90

    # Portero en x = 98.0m (mitad derecha / arco visitante)
    res_der = calibrador.clasificar_jugador(
        color=np.array([0.7, 0.1, 0.2]),
        posicion_m=(98.0, 34.0),
        es_portero=True,
        centroides_equipo_x=(30.0, 70.0),
    )
    assert res_der.equipo == EquipoDetectado.VISITANTE


def test_calibrador_clasifica_con_precision_superior_a_95_por_ciento():
    from seguimiento.color import CalibradorEquiposPartido, ColoresEquipo

    colores = ColoresEquipo(color_local="#FFFFFF", color_visitante="#6CABDD")
    calibrador = CalibradorEquiposPartido(colores_equipo=colores, min_muestras_calibracion=20)

    # Simular condiciones de iluminación real de partido (Tottenham blanco vs Man City celeste)
    muestras_blancas = [np.array([0.98 + float(_RNG.normal(0, 0.01)), -0.03, 0.06]) for _ in range(40)]
    muestras_celestes = [np.array([0.90 + float(_RNG.normal(0, 0.01)), -0.05, -0.02]) for _ in range(40)]

    for mb, mc in zip(muestras_blancas[:15], muestras_celestes[:15], strict=True):
        calibrador.acumular_muestra(mb)
        calibrador.acumular_muestra(mc)

    assert calibrador.calibrado is True

    aciertos = 0
    total = len(muestras_blancas[15:]) + len(muestras_celestes[15:])
    for mb in muestras_blancas[15:]:
        if calibrador.clasificar_jugador(mb).equipo == EquipoDetectado.LOCAL:
            aciertos += 1
    for mc in muestras_celestes[15:]:
        if calibrador.clasificar_jugador(mc).equipo == EquipoDetectado.VISITANTE:
            aciertos += 1

    assert aciertos / total >= 0.95

