"""Pantallas que existen en cada plataforma y quién puede abrirlas.

Es la lista blanca de las acciones del asistente: una ruta que el modelo
devuelva y no esté aquí (o que el rol no pueda abrir) se descarta. Refleja
`web/src/app/router.tsx` + `permisos.ts` y `movil/lib/app/router.dart`; si se
agrega una pantalla allá, se agrega aquí.
"""

import re

from app.asistente.schemas import Plataforma

TODOS = frozenset({"ADMIN", "DT", "ANALISTA", "ASISTENTE"})
_VISION = frozenset({"ADMIN", "ANALISTA"})
_ASISTENCIA = frozenset({"ADMIN", "DT", "ANALISTA"})
_PROGRAMAN = frozenset({"ADMIN", "DT"})

# (ruta, roles, descripción). En la web, el partido va como ?partidoId=N
# (o ?partido=N en la alineación).
PANTALLAS_WEB: tuple[tuple[str, frozenset[str], str], ...] = (
    ("/", TODOS, "Inicio: panel del club"),
    ("/seguridad/perfil", TODOS, "Mi perfil"),
    ("/seguridad/usuarios", frozenset({"ADMIN"}), "Usuarios del club"),
    ("/deportivo/equipos", TODOS, "Equipos"),
    ("/deportivo/equipos/indumentaria", TODOS, "Indumentaria: colores de camiseta"),
    ("/deportivo/plantel", TODOS, "Plantel: jugadores y carga por CSV"),
    ("/deportivo/calendario", TODOS, "Calendario de partidos"),
    ("/deportivo/calendario/programar", _PROGRAMAN, "Programar partido"),
    ("/deportivo/calendario/alineacion", TODOS, "Alineación (?partido=N)"),
    ("/deportivo/competiciones", _PROGRAMAN, "Competiciones"),
    ("/vision/guia-montaje", _VISION, "Guía de montaje de la cámara"),
    ("/vision/calibracion", _VISION, "Calibración de la cámara (?partidoId=N)"),
    ("/vision/videos", _VISION, "Videos: subir y procesar grabaciones (?partidoId=N)"),
    ("/vision/modelos", _VISION, "Modelos de detección"),
    ("/partido", TODOS, "Control de partido en vivo (?partidoId=N)"),
    ("/partido/asignar", TODOS, "Asignar jugadores a lo detectado (?partidoId=N)"),
    ("/analisis", TODOS, "Panel del partido: plano 2D y posesión (?partidoId=N)"),
    ("/analisis/metricas", TODOS, "Métricas tácticas (?partidoId=N)"),
    ("/analisis/mapa-de-calor", TODOS, "Mapa de calor (?partidoId=N)"),
    ("/analisis/red-de-pases", TODOS, "Red de pases (?partidoId=N)"),
    ("/asistencia", _ASISTENCIA, "Recomendaciones en vivo (?partidoId=N)"),
    ("/asistencia/reglas", _ASISTENCIA, "Reglas tácticas"),
)

# En el móvil, {id} es el número del partido.
PANTALLAS_MOVIL: tuple[tuple[str, frozenset[str], str], ...] = (
    ("/", TODOS, "Inicio: panel del club"),
    ("/perfil", TODOS, "Mi perfil"),
    ("/deportivo", TODOS, "Equipos y plantel"),
    ("/vision", TODOS, "Videos y consejos de montaje de la cámara"),
    ("/partidos", TODOS, "Agenda de partidos"),
    ("/partidos/{id}/alineacion", TODOS, "Alineación del partido"),
    ("/partido", TODOS, "Control de partido: registrar eventos"),
    ("/partido/{id}", TODOS, "Control de un partido: registrar eventos"),
    ("/partidos/{id}/eventos", TODOS, "Eventos del partido"),
    ("/partidos/{id}/alertas", TODOS, "Alertas del partido"),
    ("/analisis", TODOS, "Análisis en vivo"),
    ("/partidos/{id}/resumen", TODOS, "Resumen de métricas del partido"),
    ("/partidos/{id}/recomendaciones", _ASISTENCIA, "Recomendaciones en vivo"),
    ("/asistencia", TODOS, "Asistencia y reportes"),
)

_PARAM_WEB = re.compile(r"^(partidoId|partido)=(\d+)$")


def pantallas(plataforma: Plataforma) -> tuple[tuple[str, frozenset[str], str], ...]:
    return PANTALLAS_WEB if plataforma == "web" else PANTALLAS_MOVIL


def ruta_valida(ruta: str, plataforma: Plataforma, rol: str, partidos: set[int]) -> bool:
    """¿Existe la ruta en la plataforma, la puede abrir el rol y, si nombra un
    partido, es uno del club del usuario?"""
    ruta = ruta.strip()
    if not ruta.startswith("/") or len(ruta) > 120:
        return False
    if plataforma == "web":
        camino, _, consulta = ruta.partition("?")
        if consulta:
            coincide = _PARAM_WEB.match(consulta)
            if not coincide or int(coincide.group(2)) not in partidos:
                return False
        return any(camino == r and rol in roles for r, roles, _ in PANTALLAS_WEB)
    if "?" in ruta:
        return False
    for patron, roles, _ in PANTALLAS_MOVIL:
        if "{id}" not in patron:
            if ruta == patron:
                return rol in roles
            continue
        regex = "^" + re.escape(patron).replace(re.escape("{id}"), r"(\d+)") + "$"
        coincide = re.match(regex, ruta)
        if coincide:
            return rol in roles and int(coincide.group(1)) in partidos
    return False
