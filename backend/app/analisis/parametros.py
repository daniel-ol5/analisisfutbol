"""Umbrales del motor de métricas  —  T-074, T-075, T-076 (CU-42, CU-43, CU-46).

Todos en un solo lugar y en una dataclass inmutable: el motor en vivo y el
recálculo usan exactamente los mismos valores, y una prueba puede crear una
variante con `dataclasses.replace` sin tocar el resto.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Parametros:
    # ---- Posesión (CU-42) ----
    radio_posesion_m: float = 2.0
    """El jugador de campo más cercano al balón posee si está a esta distancia o menos.
    Más lejos de todos, el tiempo cuenta como disputa."""

    muestras_poseedor_estable: int = 2
    """Muestras seguidas que necesita un jugador para ser el poseedor estable (pases)."""

    # ---- Pases (CU-42, CU-46) ----
    pase_max_hueco_s: float = 4.0
    """Tiempo máximo de disputa o sin balón entre el poseedor A y el poseedor B."""

    pase_min_recorrido_m: float = 3.0
    """Recorrido mínimo del balón entre A y B para contar un pase (y no un quite)."""

    # ---- Métricas físicas (CU-43) ----
    ventana_velocidad_s: float = 1.0
    """La velocidad se mide sobre la posición suavizada en una ventana de este largo."""

    velocidad_max_valida_ms: float = 12.0
    """Por encima de esto no es un jugador corriendo sino un salto del tracking: se descarta."""

    umbral_sprint_ms: float = 21.0 / 3.6
    """Sprint: más de 21 km/h (5,83 m/s), según la historia de CU-43."""

    duracion_min_sprint_s: float = 1.0
    """Un sprint tiene que sostenerse al menos esto para contarse."""

    suavizado_alpha: float = 0.2
    suavizado_umbral_m: float = 0.2
    """Mismos valores por defecto que `suavizar_trayectoria` de vision/calibracion/suavizado.py."""

    # ---- Intervalos (CU-46) ----
    intervalo_s: float = 300.0
    segundos_primer_tiempo: float = 2700.0
    """`t` menor que esto es la parte 1; desde aquí, la parte 2 (para normalizar coordenadas)."""

    max_hueco_s: float = 1.0
    """Un hueco sin datos cuenta como mucho esto (tiempo de posesión y tiempo jugado)."""

    # ---- Bloque (CU-46, CU-45) ----
    jugadores_linea: int = 4
    """La altura de línea es la x media de los 4 jugadores de campo más retrasados."""

    area_largo_m: float = 16.5
    area_ancho_m: float = 40.32

    # ---- Cancha por defecto (si el partido no tiene calibración) ----
    largo_cancha_m: float = 105.0
    ancho_cancha_m: float = 68.0


PARAMETROS = Parametros()
