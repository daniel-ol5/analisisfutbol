"""En qué punto del flujo está el club: pasos hechos, pendientes y el siguiente.

Todo se calcula con los datos reales del club del usuario, siempre a través de
`del_club` (Pb-03): otro club nunca influye en el progreso.
"""

from dataclasses import dataclass

from sqlalchemy import case, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis.models import MetricaIntervalo
from app.asistente.schemas import PasoProgreso, Plataforma, Progreso
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club
from app.deportivo.models import Equipo, Jugador, Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import AsignacionTrack
from app.vision.models import Calibracion

NOMBRE_ROL = {
    "ADMIN": "Administrador",
    "DT": "Director Técnico",
    "ANALISTA": "Analista",
    "ASISTENTE": "Asistente",
}
_TODOS = ("ADMIN", "DT", "ANALISTA", "ASISTENTE")
_INICIADOS = (
    EstadoPartido.EN_CURSO.value,
    EstadoPartido.FINALIZADO.value,
    EstadoPartido.PROCESANDO.value,
    EstadoPartido.ANALIZADO.value,
)


@dataclass(frozen=True)
class _Paso:
    clave: str
    titulo: str
    roles: tuple[str, ...]
    web: str | None
    movil: str | None
    con_partido: bool = False   # la ruta lleva el partido de referencia
    disponible: bool = True


# Orden del flujo de la guía (app/asistente/guia_uso.md). En las rutas, {id}
# es el partido de referencia.
PASOS: tuple[_Paso, ...] = (
    _Paso("club", "Registrar el club", ("ADMIN",), None, None),
    _Paso("equipo", "Crear el equipo y sus colores", _TODOS, "/deportivo/equipos", "/deportivo"),
    _Paso("jugadores", "Cargar los jugadores", _TODOS, "/deportivo/plantel", "/deportivo"),
    _Paso("partido", "Programar un partido", ("ADMIN", "DT"),
          "/deportivo/calendario/programar", None),
    _Paso("calibracion", "Calibrar la cámara", ("ADMIN", "ANALISTA"),
          "/vision/calibracion?partidoId={id}", None, con_partido=True),
    _Paso("inicio", "Iniciar el partido", ("ADMIN", "ANALISTA"),
          "/partido?partidoId={id}", None, con_partido=True),
    _Paso("asignacion", "Asignar los jugadores detectados", ("ADMIN", "ANALISTA"),
          "/partido/asignar?partidoId={id}", None, con_partido=True),
    _Paso("analisis", "Ver métricas y recomendaciones", _TODOS,
          "/analisis?partidoId={id}", "/partidos/{id}/resumen", con_partido=True),
    _Paso("informe", "Informe del partido", (), None, None, disponible=False),
)


async def partido_de_referencia(db: AsyncSession, usuario: UsuarioActual) -> Partido | None:
    """El partido en curso; si no hay, el próximo programado; si no, el último jugado."""
    prioridad = case(
        (Partido.estado == EstadoPartido.EN_CURSO.value, 0),
        (Partido.estado == EstadoPartido.PROGRAMADO.value, 1),
        else_=2,
    )
    stmt = (
        del_club(Partido, usuario)
        .where(Partido.estado != EstadoPartido.CANCELADO.value)
        .order_by(
            prioridad,
            # Programados: el más cercano primero; jugados: el más reciente primero.
            case((Partido.estado == EstadoPartido.PROGRAMADO.value, Partido.fecha_hora)),
            Partido.fecha_hora.desc(),
            Partido.id.desc(),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def _hay(db: AsyncSession, stmt) -> bool:
    return bool((await db.execute(select(exists(stmt)))).scalar())


async def _pasos_hechos(
    db: AsyncSession, usuario: UsuarioActual, partido: Partido | None
) -> set[str]:
    hechos = {"club"}   # quien tiene sesión ya pertenece a un club registrado
    if await _hay(db, del_club(Equipo, usuario).where(Equipo.activo)):
        hechos.add("equipo")
    if await _hay(db, del_club(Jugador, usuario).where(Jugador.activo)):
        hechos.add("jugadores")
    if partido is None:
        return hechos
    hechos.add("partido")
    calibrado = del_club(Calibracion, usuario).where(
        Calibracion.partido_id == partido.id,
        (Calibracion.modo == "AUTOMATICA") | Calibracion.valida,
    )
    if partido.estado in _INICIADOS or await _hay(db, calibrado):
        hechos.add("calibracion")
    if partido.estado in _INICIADOS:
        hechos.add("inicio")
    asignado = del_club(AsignacionTrack, usuario).where(
        AsignacionTrack.partido_id == partido.id, AsignacionTrack.jugador_id.is_not(None)
    )
    if await _hay(db, asignado):
        hechos.add("asignacion")
    # MetricaIntervalo no tiene club_id: cuelga del partido, que ya salió de del_club.
    metricas = select(MetricaIntervalo).where(MetricaIntervalo.partido_id == partido.id)
    if await _hay(db, metricas):
        hechos.add("analisis")
    return hechos


def _quien(roles: tuple[str, ...]) -> str:
    return " o ".join(NOMBRE_ROL[r] for r in roles)


def _armar_paso(
    paso: _Paso, hecho: bool, plataforma: Plataforma, rol: str, partido_id: int | None
) -> PasoProgreso:
    plantilla = paso.web if plataforma == "web" else paso.movil
    solo_web = paso.disponible and paso.web is not None and paso.movil is None
    puede = rol in paso.roles
    nota: str | None = None
    ruta: str | None = None
    if not paso.disponible:
        nota = "Esta función todavía no está disponible en Área Técnica."
    elif plataforma == "movil" and solo_web:
        nota = "Este paso solo se puede hacer en la web."
    elif not puede and not hecho:
        nota = f"Lo hace un {_quien(paso.roles)}."
    elif paso.con_partido and partido_id is None:
        nota = "Primero programa un partido."
    elif plantilla is not None and puede:
        ruta = plantilla.replace("{id}", str(partido_id))
    return PasoProgreso(
        clave=paso.clave,
        titulo=paso.titulo,
        estado="hecho" if hecho else "pendiente",
        ruta=ruta,
        solo_web=solo_web,
        disponible=paso.disponible,
        tu_rol_puede=puede,
        nota=nota,
    )


async def calcular_progreso(
    db: AsyncSession, usuario: UsuarioActual, plataforma: Plataforma, asistente_activo: bool
) -> Progreso:
    partido = await partido_de_referencia(db, usuario)
    partido_id = partido.id if partido else None
    hechos = await _pasos_hechos(db, usuario, partido)
    pasos = [
        _armar_paso(p, p.clave in hechos, plataforma, usuario.rol, partido_id) for p in PASOS
    ]
    siguiente = next((p for p in pasos if p.estado == "pendiente" and p.disponible), None)
    return Progreso(
        plataforma=plataforma,
        partido_id=partido_id,
        pasos=pasos,
        siguiente=siguiente,
        asistente_activo=asistente_activo,
    )
