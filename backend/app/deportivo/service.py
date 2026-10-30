"""Lógica de negocio de Gestión Deportiva  —  CU-09 … CU-17.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import colorsys
import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Alineacion, AlineacionJugador, Equipo, Jugador, Partido
from app.deportivo.schemas import (
    Alineacion as AlineacionOut,
)
from app.deportivo.schemas import (
    AlineacionGuardar,
    AvisoColores,
    EquipoCrear,
    EquipoEditar,
    EstadoPartido,
    JugadorAlineadoOut,
    Posicion,
)
from app.deportivo.schemas import (
    Equipo as EquipoOut,
)


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


# ---------------- CU-17 · Alineación y formación (T-048) ----------------

# Con el partido terminado, la alineación ya alimentó el análisis: no se toca.
ESTADOS_ALINEACION_EDITABLE = {EstadoPartido.PROGRAMADO, EstadoPartido.EN_CURSO}


async def _partido_del_club(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Partido:
    res = await db.execute(del_club(Partido, usuario).where(Partido.id == partido_id))
    return verificar_pertenencia(res.scalar_one_or_none(), usuario)


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
