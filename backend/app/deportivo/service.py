"""Lógica de negocio de Gestión Deportiva  —  CU-09 … CU-17.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import colorsys
import csv
import io
import math
from datetime import UTC, date, datetime, time

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import (
    Alineacion,
    AlineacionJugador,
    Competicion,
    Equipo,
    Jugador,
    Partido,
)
from app.deportivo.schemas import (
    Alineacion as AlineacionOut,
)
from app.deportivo.schemas import (
    AlineacionGuardar,
    AvisoColores,
    Cancelacion,
    CompeticionCrear,
    EquipoCrear,
    EquipoEditar,
    EstadoPartido,
    FilaImportacion,
    JugadorAlineadoOut,
    JugadorBase,
    JugadorCrear,
    JugadorEditar,
    PartidoCrear,
    PartidoEditar,
    Posicion,
    ResultadoImportacion,
)
from app.deportivo.schemas import (
    Competicion as CompeticionOut,
)
from app.deportivo.schemas import (
    Equipo as EquipoOut,
)
from app.deportivo.schemas import (
    Jugador as JugadorOut,
)
from app.deportivo.schemas import (
    Partido as PartidoOut,
)

_ORDEN_JUGADOR = {
    "dorsal": Jugador.dorsal,
    "posicion": Jugador.posicion,
    "apellido": Jugador.apellido,
}


def _hex_a_hsv(hex_color: str) -> tuple[float, float, float]:
    hex_clean = hex_color.strip().lstrip("#")
    if len(hex_clean) != 6:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"El formato del color '{hex_color}' es inválido. Use formato hexadecimal #RRGGBB.",
        )
    try:
        r = int(hex_clean[0:2], 16) / 255.0
        g = int(hex_clean[2:4], 16) / 255.0
        b = int(hex_clean[4:6], 16) / 255.0
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"El color '{hex_color}' contiene caracteres hexadecimales inválidos.",
        ) from None
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s * 100.0, v * 100.0


def calcular_distancia_hsv(hex1: str, hex2: str) -> float:
    """Calcula la distancia euclidiana en el espacio cilíndrico HSV.

    Menor a 40 se considera riesgoso para la diferenciación óptica de los equipos.
    """
    h1, s1, v1 = _hex_a_hsv(hex1)
    h2, s2, v2 = _hex_a_hsv(hex2)

    rad1 = math.radians(h1)
    rad2 = math.radians(h2)

    x1 = s1 * math.cos(rad1)
    y1 = s1 * math.sin(rad1)
    z1 = v1

    x2 = s2 * math.cos(rad2)
    y2 = s2 * math.sin(rad2)
    z2 = v2

    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)


async def _contar_jugadores_activos(
    db: AsyncSession, club_id: int, equipo_ids: list[int]
) -> dict[int, int]:
    if not equipo_ids:
        return {}
    q = (
        select(Jugador.equipo_id, func.count(Jugador.id))
        .where(
            Jugador.club_id == club_id,
            Jugador.equipo_id.in_(equipo_ids),
            Jugador.activo,
        )
        .group_by(Jugador.equipo_id)
    )
    res = await db.execute(q)
    return dict(res.all())


async def listar_equipos(
    db: AsyncSession, usuario: UsuarioActual, activos: bool = True
) -> list[EquipoOut]:
    """CU-09: lista equipos del club aplicando aislamiento multi-inquilino."""
    stmt = del_club(Equipo, usuario)
    if activos:
        stmt = stmt.where(Equipo.activo)
    stmt = stmt.order_by(Equipo.id)
    res = await db.execute(stmt)
    equipos = res.scalars().all()

    conteo = await _contar_jugadores_activos(
        db, usuario.club_id, [e.id for e in equipos]
    )

    return [
        EquipoOut(
            id=e.id,
            club_id=e.club_id,
            nombre=e.nombre,
            categoria=e.categoria,
            temporada=e.temporada,
            color_local=e.color_local,
            color_visitante=e.color_visitante,
            color_arquero=e.color_arquero,
            activo=e.activo,
            jugadores=conteo.get(e.id, 0),
        )
        for e in equipos
    ]


async def crear_equipo(
    db: AsyncSession, usuario: UsuarioActual, datos: EquipoCrear
) -> EquipoOut:
    """CU-09: alta de equipo con pertenencia al club del usuario."""
    equipo = Equipo(
        club_id=usuario.club_id,
        nombre=datos.nombre,
        categoria=datos.categoria,
        temporada=datos.temporada,
        color_local=datos.color_local,
        color_visitante=datos.color_visitante,
        color_arquero=datos.color_arquero,
        activo=True,
    )
    db.add(equipo)
    await db.commit()
    await db.refresh(equipo)

    return EquipoOut(
        id=equipo.id,
        club_id=equipo.club_id,
        nombre=equipo.nombre,
        categoria=equipo.categoria,
        temporada=equipo.temporada,
        color_local=equipo.color_local,
        color_visitante=equipo.color_visitante,
        color_arquero=equipo.color_arquero,
        activo=equipo.activo,
        jugadores=0,
    )


async def ver_equipo(
    db: AsyncSession, usuario: UsuarioActual, equipo_id: int
) -> EquipoOut:
    """CU-09: obtiene un equipo verificando pertenencia estricta por club."""
    res = await db.execute(select(Equipo).where(Equipo.id == equipo_id))
    equipo = res.scalar_one_or_none()
    verificar_pertenencia(equipo, usuario)

    conteo = await _contar_jugadores_activos(db, usuario.club_id, [equipo.id])

    return EquipoOut(
        id=equipo.id,
        club_id=equipo.club_id,
        nombre=equipo.nombre,
        categoria=equipo.categoria,
        temporada=equipo.temporada,
        color_local=equipo.color_local,
        color_visitante=equipo.color_visitante,
        color_arquero=equipo.color_arquero,
        activo=equipo.activo,
        jugadores=conteo.get(equipo.id, 0),
    )


async def editar_equipo(
    db: AsyncSession, usuario: UsuarioActual, equipo_id: int, datos: EquipoEditar
) -> EquipoOut:
    """CU-09: edición de datos e indumentaria de un equipo."""
    res = await db.execute(select(Equipo).where(Equipo.id == equipo_id))
    equipo = res.scalar_one_or_none()
    verificar_pertenencia(equipo, usuario)

    if datos.nombre is not None:
        equipo.nombre = datos.nombre
    if datos.categoria is not None:
        equipo.categoria = datos.categoria
    if datos.temporada is not None:
        equipo.temporada = datos.temporada
    if datos.color_local is not None:
        equipo.color_local = datos.color_local
    if datos.color_visitante is not None:
        equipo.color_visitante = datos.color_visitante
    if datos.color_arquero is not None:
        equipo.color_arquero = datos.color_arquero
    if datos.activo is not None:
        equipo.activo = datos.activo

    await db.commit()
    await db.refresh(equipo)

    conteo = await _contar_jugadores_activos(db, usuario.club_id, [equipo.id])

    return EquipoOut(
        id=equipo.id,
        club_id=equipo.club_id,
        nombre=equipo.nombre,
        categoria=equipo.categoria,
        temporada=equipo.temporada,
        color_local=equipo.color_local,
        color_visitante=equipo.color_visitante,
        color_arquero=equipo.color_arquero,
        activo=equipo.activo,
        jugadores=conteo.get(equipo.id, 0),
    )


async def desactivar_equipo(
    db: AsyncSession, usuario: UsuarioActual, equipo_id: int
) -> None:
    """CU-09: baja lógica de equipo (activo=False), preservando histórico."""
    res = await db.execute(select(Equipo).where(Equipo.id == equipo_id))
    equipo = res.scalar_one_or_none()
    verificar_pertenencia(equipo, usuario)

    equipo.activo = False
    await db.commit()


async def verificar_colores_equipo(
    db: AsyncSession, usuario: UsuarioActual, equipo_id: int, color_rival: str
) -> AvisoColores:
    """CU-10: verifica el contraste entre la indumentaria local y la del rival."""
    res = await db.execute(select(Equipo).where(Equipo.id == equipo_id))
    equipo = res.scalar_one_or_none()
    verificar_pertenencia(equipo, usuario)

    distancia = calcular_distancia_hsv(equipo.color_local, color_rival)
    distancia_redondeada = round(distancia, 2)
    hay_riesgo = distancia < 40.0

    if hay_riesgo:
        mensaje = (
            f"Riesgo de confusión en visión artificial: los colores están muy "
            f"cercanos en espacio HSV (distancia {distancia_redondeada:.1f} < 40). "
            f"Se sugiere usar indumentaria alternativa."
        )
    else:
        mensaje = (
            f"Contraste adecuado: la distancia en espacio HSV ({distancia_redondeada:.1f} >= 40) "
            f"permite una diferenciación clara en el pipeline óptico."
        )

    return AvisoColores(
        hay_riesgo=hay_riesgo,
        distancia_hsv=distancia_redondeada,
        mensaje=mensaje,
    )


# ---------------- CU-13 · Competiciones y temporadas (T-046) ----------------

async def listar_competiciones(
    db: AsyncSession, usuario: UsuarioActual
) -> list[CompeticionOut]:
    """Lista las competiciones activas del club, sin exponer datos de otros clubes."""
    stmt = (
        del_club(Competicion, usuario)
        .where(Competicion.activo)
        .order_by(
            Competicion.fecha_inicio.is_(None),
            Competicion.fecha_inicio,
            Competicion.nombre,
        )
    )
    resultado = await db.execute(stmt)
    return [CompeticionOut.model_validate(item) for item in resultado.scalars().all()]


async def crear_competicion(
    db: AsyncSession, usuario: UsuarioActual, datos: CompeticionCrear
) -> CompeticionOut:
    """Crea una competicion vinculada al club del usuario autenticado."""
    competicion = Competicion(
        club_id=usuario.club_id,
        nombre=datos.nombre,
        temporada=datos.temporada,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        activo=True,
    )
    db.add(competicion)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe una competicion con ese nombre y temporada en el club",
        ) from None

    await db.refresh(competicion)
    return CompeticionOut.model_validate(competicion)


# ---------------- CU-14, CU-15, CU-16 · Partidos (T-047) ----------------

def _en_utc(fecha_hora: datetime) -> datetime:
    """Normaliza fechas para comparar y persistir de forma consistente."""
    if fecha_hora.tzinfo is None:
        return fecha_hora.replace(tzinfo=UTC)
    return fecha_hora.astimezone(UTC)


def _validar_fecha_futura(fecha_hora: datetime) -> datetime:
    normalizada = _en_utc(fecha_hora)
    if normalizada <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La fecha y hora del partido debe ser futura",
        )
    return normalizada


def _fecha_iso(valor: str | None, nombre: str) -> date | None:
    if valor is None:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"El filtro {nombre} debe tener formato AAAA-MM-DD",
        ) from None


async def _competicion_del_club(
    db: AsyncSession, usuario: UsuarioActual, competicion_id: int
) -> Competicion:
    resultado = await db.execute(
        del_club(Competicion, usuario).where(Competicion.id == competicion_id)
    )
    return verificar_pertenencia(resultado.scalar_one_or_none(), usuario)


async def _partido_del_club(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Partido:
    resultado = await db.execute(
        del_club(Partido, usuario).where(Partido.id == partido_id)
    )
    return verificar_pertenencia(resultado.scalar_one_or_none(), usuario)


async def listar_partidos(
    db: AsyncSession,
    usuario: UsuarioActual,
    equipo_id: int | None = None,
    competicion_id: int | None = None,
    estado: EstadoPartido | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> list[PartidoOut]:
    """Devuelve la agenda cronologica del club con sus filtros opcionales."""
    fecha_desde = _fecha_iso(desde, "desde")
    fecha_hasta = _fecha_iso(hasta, "hasta")
    if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La fecha desde no puede ser posterior a la fecha hasta",
        )

    stmt = del_club(Partido, usuario)
    if equipo_id is not None:
        stmt = stmt.where(Partido.equipo_id == equipo_id)
    if competicion_id is not None:
        stmt = stmt.where(Partido.competicion_id == competicion_id)
    if estado is not None:
        stmt = stmt.where(Partido.estado == estado.value)
    if fecha_desde is not None:
        inicio = datetime.combine(fecha_desde, time.min, tzinfo=UTC)
        stmt = stmt.where(Partido.fecha_hora >= inicio)
    if fecha_hasta is not None:
        fin_inclusivo = datetime.combine(fecha_hasta, time.max, tzinfo=UTC)
        stmt = stmt.where(Partido.fecha_hora <= fin_inclusivo)

    resultado = await db.execute(stmt.order_by(Partido.fecha_hora, Partido.id))
    return [PartidoOut.model_validate(item) for item in resultado.scalars().all()]


async def programar_partido(
    db: AsyncSession, usuario: UsuarioActual, datos: PartidoCrear
) -> PartidoOut:
    """Programa un partido futuro del club en estado inicial PROGRAMADO."""
    await _equipo_del_club(db, usuario, datos.equipo_id)
    if datos.competicion_id is not None:
        await _competicion_del_club(db, usuario, datos.competicion_id)

    partido = Partido(
        club_id=usuario.club_id,
        equipo_id=datos.equipo_id,
        competicion_id=datos.competicion_id,
        rival=datos.rival,
        es_local=datos.es_local,
        fecha_hora=_validar_fecha_futura(datos.fecha_hora),
        sede=datos.sede,
        estado=EstadoPartido.PROGRAMADO.value,
    )
    db.add(partido)
    await db.commit()
    await db.refresh(partido)
    return PartidoOut.model_validate(partido)


async def ver_partido(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> PartidoOut:
    partido = await _partido_del_club(db, usuario, partido_id)
    return PartidoOut.model_validate(partido)


async def reprogramar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: PartidoEditar,
) -> PartidoOut:
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.PROGRAMADO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede reprogramar un partido en estado {partido.estado}",
        )

    if datos.rival is not None:
        partido.rival = datos.rival
    if datos.es_local is not None:
        partido.es_local = datos.es_local
    if datos.fecha_hora is not None:
        partido.fecha_hora = _validar_fecha_futura(datos.fecha_hora)
    if datos.sede is not None:
        partido.sede = datos.sede
    if "competicion_id" in datos.model_fields_set:
        if datos.competicion_id is not None:
            await _competicion_del_club(db, usuario, datos.competicion_id)
        partido.competicion_id = datos.competicion_id

    await db.commit()
    await db.refresh(partido)
    return PartidoOut.model_validate(partido)


async def cancelar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: Cancelacion,
) -> PartidoOut:
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.PROGRAMADO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede cancelar un partido en estado {partido.estado}",
        )

    partido.estado = EstadoPartido.CANCELADO.value
    partido.motivo_cancelacion = datos.motivo
    await db.commit()
    await db.refresh(partido)
    return PartidoOut.model_validate(partido)


# ---------------- CU-17 · Alineación y formación (T-048) ----------------

# Con el partido terminado, la alineación ya alimentó el análisis: no se toca.
ESTADOS_ALINEACION_EDITABLE = {EstadoPartido.PROGRAMADO, EstadoPartido.EN_CURSO}


async def _alineacion_del_partido(db: AsyncSession, partido_id: int) -> Alineacion | None:
    res = await db.execute(
        select(Alineacion)
        .where(Alineacion.partido_id == partido_id)
        .options(
            selectinload(Alineacion.jugadores_alineados).selectinload(
                AlineacionJugador.jugador
            )
        )
    )
    return res.scalar_one_or_none()


def _alineacion_a_salida(alineacion: Alineacion) -> AlineacionOut:
    filas = sorted(
        alineacion.jugadores_alineados,
        key=lambda f: (not f.es_titular, f.jugador.dorsal),
    )
    return AlineacionOut(
        id=alineacion.id,
        partido_id=alineacion.partido_id,
        formacion=alineacion.formacion,
        jugadores=[
            JugadorAlineadoOut(
                jugador_id=f.jugador_id,
                es_titular=f.es_titular,
                es_capitan=f.es_capitan,
                pos_x=f.pos_x,
                pos_y=f.pos_y,
                minuto_entra=f.minuto_entra,
                minuto_sale=f.minuto_sale,
                nombre=f.jugador.nombre,
                apellido=f.jugador.apellido,
                dorsal=f.jugador.dorsal,
                posicion=f.jugador.posicion,
            )
            for f in filas
        ],
    )


async def ver_alineacion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> AlineacionOut:
    """CU-17: alineación del partido, con los datos de cada jugador."""
    await _partido_del_club(db, usuario, partido_id)
    alineacion = await _alineacion_del_partido(db, partido_id)
    if alineacion is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "El partido todavía no tiene alineación"
        )
    return _alineacion_a_salida(alineacion)


async def guardar_alineacion(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, datos: AlineacionGuardar
) -> AlineacionOut:
    """CU-17: guarda la formación, titulares, suplentes y capitán del partido.

    Si ya había una alineación, la reemplaza completa. El esquema ya validó
    11 titulares y un capitán; acá se valida lo que necesita la base: que los
    jugadores sean del plantel del equipo y que haya un único arquero titular.
    """
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado not in ESTADOS_ALINEACION_EDITABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede cambiar la alineación de un partido {partido.estado}",
        )

    ids = [j.jugador_id for j in datos.jugadores]
    res = await db.execute(
        select(Jugador).where(
            Jugador.id.in_(ids),
            Jugador.club_id == usuario.club_id,
            Jugador.equipo_id == partido.equipo_id,
            Jugador.activo,
        )
    )
    plantel = {j.id: j for j in res.scalars().all()}
    ajenos = [i for i in ids if i not in plantel]
    if ajenos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Estos jugadores no están en el plantel activo del equipo: "
            + ", ".join(map(str, ajenos)),
        )

    arqueros = [
        j for j in datos.jugadores
        if j.es_titular and plantel[j.jugador_id].posicion == Posicion.ARQUERO
    ]
    if len(arqueros) != 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Tiene que haber un solo arquero entre los titulares (hay {len(arqueros)})",
        )

    alineacion = await _alineacion_del_partido(db, partido_id)
    if alineacion is None:
        alineacion = Alineacion(club_id=usuario.club_id, partido_id=partido_id)
        db.add(alineacion)
    alineacion.formacion = datos.formacion.value
    # delete-orphan borra las filas anteriores al reemplazar la colección.
    alineacion.jugadores_alineados = [
        AlineacionJugador(
            jugador_id=j.jugador_id,
            jugador=plantel[j.jugador_id],
            es_titular=j.es_titular,
            es_capitan=j.es_capitan,
            pos_x=j.pos_x,
            pos_y=j.pos_y,
            minuto_entra=j.minuto_entra,
            minuto_sale=j.minuto_sale,
        )
        for j in datos.jugadores
    ]
    try:
        await db.commit()
    except IntegrityError:
        # Dos personas guardaron la primera alineación del partido a la vez.
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Otra persona guardó la alineación al mismo tiempo. Recarga y vuelve a intentar.",
        ) from None
    return _alineacion_a_salida(alineacion)
async def _equipo_del_club(
    db: AsyncSession, usuario: UsuarioActual, equipo_id: int
) -> Equipo:
    res = await db.execute(select(Equipo).where(Equipo.id == equipo_id))
    return verificar_pertenencia(res.scalar_one_or_none(), usuario)


async def _validar_dorsal_disponible(
    db: AsyncSession,
    club_id: int,
    equipo_id: int,
    dorsal: int,
    excluir_jugador_id: int | None = None,
) -> None:
    stmt = select(Jugador).where(
        Jugador.club_id == club_id,
        Jugador.equipo_id == equipo_id,
        Jugador.dorsal == dorsal,
        Jugador.activo,
    )
    if excluir_jugador_id is not None:
        stmt = stmt.where(Jugador.id != excluir_jugador_id)
    res = await db.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"El dorsal {dorsal} ya está en uso por otro jugador activo del equipo.",
        )


async def listar_jugadores(
    db: AsyncSession,
    usuario: UsuarioActual,
    equipo_id: int,
    activos: bool = True,
    orden: str = "dorsal",
) -> list[JugadorOut]:
    """CU-11: lista el plantel de un equipo, verificando pertenencia al club."""
    await _equipo_del_club(db, usuario, equipo_id)

    stmt = select(Jugador).where(
        Jugador.club_id == usuario.club_id, Jugador.equipo_id == equipo_id
    )
    if activos:
        stmt = stmt.where(Jugador.activo)
    stmt = stmt.order_by(_ORDEN_JUGADOR[orden])

    res = await db.execute(stmt)
    return [JugadorOut.model_validate(j) for j in res.scalars().all()]


async def crear_jugador(
    db: AsyncSession, usuario: UsuarioActual, datos: JugadorCrear
) -> JugadorOut:
    """CU-11: alta de jugador con dorsal único entre los activos del equipo."""
    await _equipo_del_club(db, usuario, datos.equipo_id)
    await _validar_dorsal_disponible(db, usuario.club_id, datos.equipo_id, datos.dorsal)

    jugador = Jugador(
        club_id=usuario.club_id,
        equipo_id=datos.equipo_id,
        nombre=datos.nombre,
        apellido=datos.apellido,
        dorsal=datos.dorsal,
        posicion=datos.posicion,
        pie_habil=datos.pie_habil,
        altura_cm=datos.altura_cm,
        peso_kg=datos.peso_kg,
        fecha_nacimiento=datos.fecha_nacimiento,
        activo=True,
    )
    db.add(jugador)
    await db.commit()
    await db.refresh(jugador)

    return JugadorOut.model_validate(jugador)


async def ver_jugador(
    db: AsyncSession, usuario: UsuarioActual, jugador_id: int
) -> JugadorOut:
    """CU-11: obtiene la ficha de un jugador verificando pertenencia al club."""
    res = await db.execute(select(Jugador).where(Jugador.id == jugador_id))
    jugador = verificar_pertenencia(res.scalar_one_or_none(), usuario)
    return JugadorOut.model_validate(jugador)


async def editar_jugador(
    db: AsyncSession, usuario: UsuarioActual, jugador_id: int, datos: JugadorEditar
) -> JugadorOut:
    """CU-11: edición parcial de la ficha, re-validando el dorsal si cambia."""
    res = await db.execute(select(Jugador).where(Jugador.id == jugador_id))
    jugador = verificar_pertenencia(res.scalar_one_or_none(), usuario)

    if datos.dorsal is not None and datos.dorsal != jugador.dorsal:
        await _validar_dorsal_disponible(
            db, usuario.club_id, jugador.equipo_id, datos.dorsal, excluir_jugador_id=jugador.id
        )
        jugador.dorsal = datos.dorsal
    if datos.nombre is not None:
        jugador.nombre = datos.nombre
    if datos.apellido is not None:
        jugador.apellido = datos.apellido
    if datos.posicion is not None:
        jugador.posicion = datos.posicion
    if datos.pie_habil is not None:
        jugador.pie_habil = datos.pie_habil
    if datos.altura_cm is not None:
        jugador.altura_cm = datos.altura_cm
    if datos.peso_kg is not None:
        jugador.peso_kg = datos.peso_kg
    if datos.fecha_nacimiento is not None:
        jugador.fecha_nacimiento = datos.fecha_nacimiento
    if datos.activo is not None:
        if datos.activo and not jugador.activo:
            await _validar_dorsal_disponible(
                db,
                usuario.club_id,
                jugador.equipo_id,
                datos.dorsal if datos.dorsal is not None else jugador.dorsal,
                excluir_jugador_id=jugador.id,
            )
        jugador.activo = datos.activo

    await db.commit()
    await db.refresh(jugador)

    return JugadorOut.model_validate(jugador)


async def baja_jugador(
    db: AsyncSession, usuario: UsuarioActual, jugador_id: int
) -> None:
    """CU-11: baja lógica del jugador, preservando sus métricas históricas."""
    res = await db.execute(select(Jugador).where(Jugador.id == jugador_id))
    jugador = verificar_pertenencia(res.scalar_one_or_none(), usuario)

    jugador.activo = False
    await db.commit()


_COLUMNAS_CSV_REQUERIDAS = {"nombre", "apellido", "dorsal", "altura_cm"}
_COLUMNAS_CSV_OPCIONALES = ("posicion", "pie_habil", "peso_kg", "fecha_nacimiento")
_COLUMNAS_CSV_ORDEN = (
    "nombre", "apellido", "dorsal", "altura_cm", "posicion", "pie_habil", "peso_kg", "fecha_nacimiento",
)
_FILA_EJEMPLO_CSV = {
    "nombre": "Marcelo",
    "apellido": "Moreno",
    "dorsal": "9",
    "altura_cm": "181",
    "posicion": "DEL",
    "pie_habil": "DER",
    "peso_kg": "78",
    "fecha_nacimiento": "1998-05-12",
}


def _detectar_delimitador(texto: str) -> str:
    """Detecta si el CSV usa coma o punto y coma (Excel en español usa ';'
    porque ',' es el separador decimal). Si no logra detectarlo, asume coma."""
    primera_linea = texto.splitlines()[0] if texto.splitlines() else ""
    try:
        return csv.Sniffer().sniff(primera_linea, delimiters=",;").delimiter
    except csv.Error:
        return ","


def generar_plantilla_csv_jugadores() -> str:
    """CU-12: CSV de ejemplo con las columnas esperadas por `importar_plantel`,
    para que el usuario lo complete y vuelva a subirlo. Se usa ';' como
    separador porque es lo que Excel/Sheets en español esperan por defecto."""
    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=_COLUMNAS_CSV_ORDEN, delimiter=";")
    escritor.writeheader()
    escritor.writerow(_FILA_EJEMPLO_CSV)
    return buffer.getvalue()


async def exportar_jugadores_csv(
    db: AsyncSession,
    usuario: UsuarioActual,
    equipo_id: int,
    activos: bool = True,
    orden: str = "dorsal",
) -> str:
    """CU-12: exporta el plantel actual a CSV con las mismas columnas que
    `importar_plantel`, para respaldo o para editarlo y volver a subirlo. Se
    usa ';' como separador porque es lo que Excel/Sheets en español esperan
    por defecto."""
    jugadores = await listar_jugadores(db, usuario, equipo_id, activos=activos, orden=orden)

    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=_COLUMNAS_CSV_ORDEN, delimiter=";")
    escritor.writeheader()
    for j in jugadores:
        escritor.writerow({
            "nombre": j.nombre,
            "apellido": j.apellido,
            "dorsal": j.dorsal,
            "altura_cm": j.altura_cm,
            "posicion": j.posicion.value,
            "pie_habil": j.pie_habil.value,
            "peso_kg": j.peso_kg if j.peso_kg is not None else "",
            "fecha_nacimiento": j.fecha_nacimiento.isoformat() if j.fecha_nacimiento else "",
        })
    return buffer.getvalue()


async def importar_plantel(
    db: AsyncSession,
    usuario: UsuarioActual,
    equipo_id: int,
    contenido: bytes,
    confirmar: bool = False,
) -> ResultadoImportacion:
    """CU-12: valida e importa un plantel desde CSV.

    Las filas válidas se importan aunque otras tengan errores. Con
    `confirmar=False` se devuelve la vista previa (nada se guarda); con
    `confirmar=True` se persisten las filas válidas. Columnas esperadas:
    nombre, apellido, dorsal, altura_cm (obligatorias) y posicion,
    pie_habil, peso_kg, fecha_nacimiento (opcionales), con los mismos
    códigos que usa la API (ARQ/DEF/MED/DEL, IZQ/DER/AMBOS, fecha ISO).
    """
    await _equipo_del_club(db, usuario, equipo_id)

    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El archivo no es un CSV de texto válido (UTF-8).",
        ) from None

    delimitador = _detectar_delimitador(texto)
    lector = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    columnas = set(lector.fieldnames or [])
    if not columnas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "El archivo CSV está vacío."
        )
    faltantes = _COLUMNAS_CSV_REQUERIDAS - columnas
    if faltantes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Faltan columnas obligatorias en el CSV: {', '.join(sorted(faltantes))}.",
        )

    res = await db.execute(
        select(Jugador.dorsal).where(
            Jugador.club_id == usuario.club_id,
            Jugador.equipo_id == equipo_id,
            Jugador.activo,
        )
    )
    dorsales_usados = set(res.scalars().all())

    detalle: list[FilaImportacion] = []
    validas: list[JugadorBase] = []

    for i, fila in enumerate(lector, start=1):
        datos_fila = {
            clave: (valor or "").strip()
            for clave, valor in fila.items()
            if clave is not None
        }

        candidato: dict = {
            "nombre": datos_fila.get("nombre", ""),
            "apellido": datos_fila.get("apellido", ""),
            "dorsal": datos_fila.get("dorsal", ""),
            "altura_cm": datos_fila.get("altura_cm", ""),
        }
        for columna in _COLUMNAS_CSV_OPCIONALES:
            if datos_fila.get(columna):
                candidato[columna] = datos_fila[columna]

        try:
            jugador_validado = JugadorBase.model_validate(candidato)
        except ValidationError as err:
            mensaje = "; ".join(e["msg"] for e in err.errors())
            detalle.append(FilaImportacion(fila=i, datos=datos_fila, error=mensaje))
            continue

        if jugador_validado.dorsal in dorsales_usados:
            detalle.append(
                FilaImportacion(
                    fila=i,
                    datos=datos_fila,
                    error=(
                        f"El dorsal {jugador_validado.dorsal} ya está en uso en el "
                        "equipo o duplicado en el archivo."
                    ),
                )
            )
            continue

        dorsales_usados.add(jugador_validado.dorsal)
        validas.append(jugador_validado)
        detalle.append(FilaImportacion(fila=i, datos=datos_fila, error=None))

    if confirmar:
        for datos_jugador in validas:
            db.add(
                Jugador(
                    club_id=usuario.club_id,
                    equipo_id=equipo_id,
                    nombre=datos_jugador.nombre,
                    apellido=datos_jugador.apellido,
                    dorsal=datos_jugador.dorsal,
                    posicion=datos_jugador.posicion,
                    pie_habil=datos_jugador.pie_habil,
                    altura_cm=datos_jugador.altura_cm,
                    peso_kg=datos_jugador.peso_kg,
                    fecha_nacimiento=datos_jugador.fecha_nacimiento,
                    activo=True,
                )
            )
        await db.commit()

    return ResultadoImportacion(
        total=len(detalle),
        importadas=len(validas),
        con_error=len(detalle) - len(validas),
        detalle=detalle,
    )
