"""Lógica de negocio de Operación del Partido  —  CU-30 … CU-39.

Este módulo no conoce FastAPI: recibe una sesión y datos, devuelve objetos o
lanza excepciones de dominio. Así se prueba sin levantar el servidor.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import func, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import UsuarioActual
from app.core.tenancy import del_club, verificar_pertenencia
from app.deportivo.models import Alineacion, AlineacionJugador, Jugador, Partido, Posicion
from app.deportivo.schemas import Direccion, EstadoPartido
from app.partido.models import AsignacionTrack, RelojPartido
from app.partido.models import EventoManual as EventoManualModelo
from app.partido.schemas import (
    AsignarTrack,
    Descuento,
    EquipoDetectado,
    EstadoEnVivo,
    EventoManualCrear,
    IndicadorCalidad,
    IniciarPartido,
    Lado,
    MensajeWorker,
    TipoEventoManual,
    TrackDetectado,
)
from app.vision.models import Calibracion

log = logging.getLogger(__name__)

SEGUNDOS_PRIMER_TIEMPO = 45 * 60.0

RelojSistema = Callable[[], datetime]


def ahora_utc() -> datetime:
    """Reloj por defecto del servidor en UTC."""
    return datetime.now(UTC)


def obtener_reloj() -> RelojSistema:
    """Dependencia de FastAPI para inyectar el reloj en pruebas sin usar sleep."""
    return ahora_utc


def _en_utc(instante: datetime) -> datetime:
    """Normaliza marcas de tiempo leídas de SQLite (sin tzinfo) o PostgreSQL a UTC."""
    if instante.tzinfo is None:
        return instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC)


# ---------------- CU-31 · Normalización espacial por dirección de ataque ----------------


def normalizar_coordenadas(
    x_m: float,
    y_m: float,
    largo_m: float,
    ancho_m: float,
    ataca_hacia: Direccion | str,
    parte: int,
) -> tuple[float, float]:
    """CU-31: lleva cualquier punto (x_m, y_m) a la convención «nuestro equipo ataca hacia +x».

    `ataca_hacia` es la dirección de ataque en el PRIMER tiempo (`DER` = +x, `IZQ` = -x).
    En el segundo tiempo los equipos cambian de arco:
    - Parte 1 y `DER`: no cambia `(x_m, y_m)`.
    - Parte 1 e `IZQ`: rota 180° `(largo_m - x_m, ancho_m - y_m)`.
    - Parte 2 y `DER`: rota 180° `(largo_m - x_m, ancho_m - y_m)`.
    - Parte 2 e `IZQ`: no cambia `(x_m, y_m)`.
    """
    if parte not in (1, 2):
        raise ValueError(f"La parte debe ser 1 o 2 (recibido: {parte!r})")
    try:
        direccion = Direccion(ataca_hacia)
    except ValueError as e:
        raise ValueError(f"Dirección de ataque inválida: {ataca_hacia!r}") from e

    invertir = (
        direccion == Direccion.IZQUIERDA
        if parte == 1
        else direccion == Direccion.DERECHA
    )
    if invertir:
        return (largo_m - x_m, ancho_m - y_m)
    return (x_m, y_m)


# ---------------- CU-30, CU-31 · Control del partido y cronómetro (T-065) ----------------


def segundos_transcurridos(reloj: RelojPartido | None, ahora: datetime) -> float:
    """Tiempo del cronómetro en segundos: `acumulado_s + (ahora - inicio_utc)` si corre."""
    if reloj is None:
        return 0.0
    total = float(reloj.acumulado_s)
    if reloj.en_curso and reloj.inicio_utc is not None:
        delta = (_en_utc(ahora) - _en_utc(reloj.inicio_utc)).total_seconds()
        if delta > 0:
            total += delta
    return max(0.0, total)


def _construir_estado_en_vivo(
    partido: Partido, reloj: RelojPartido | None, ahora: datetime
) -> EstadoEnVivo:
    if reloj is None:
        parte = partido.parte
        minuto = partido.minuto_actual
        segundo = 0
        en_curso = False
    else:
        total_s = int(segundos_transcurridos(reloj, ahora))
        parte = reloj.parte
        minuto = total_s // 60
        segundo = total_s % 60
        en_curso = reloj.en_curso

    return EstadoEnVivo(
        partido_id=partido.id,
        parte=parte,
        minuto=minuto,
        segundo=segundo,
        en_curso=en_curso,
        goles_favor=partido.goles_favor,
        goles_contra=partido.goles_contra,
        posesion_local_pct=None,
        calidad=IndicadorCalidad(worker_conectado=False),
    )


async def _partido_del_club(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> Partido:
    stmt = del_club(Partido, usuario).where(Partido.id == partido_id)
    partido = (await db.execute(stmt)).scalar_one_or_none()
    return verificar_pertenencia(partido, usuario)


async def _reloj_del_partido(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> RelojPartido | None:
    stmt = del_club(RelojPartido, usuario).where(RelojPartido.partido_id == partido_id)
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------- CU-36, CU-37, CU-38 · Eventos manuales (T-066) ----------------


def _lado_propio(partido: Partido) -> Lado:
    return Lado.LOCAL if partido.es_local else Lado.VISITANTE


async def _exigir_jugador_alineado(
    db: AsyncSession, partido: Partido, jugador_id: int
) -> Jugador:
    stmt = (
        select(Jugador)
        .join(AlineacionJugador, AlineacionJugador.jugador_id == Jugador.id)
        .join(Alineacion, Alineacion.id == AlineacionJugador.alineacion_id)
        .where(
            Alineacion.partido_id == partido.id,
            Jugador.id == jugador_id,
            Jugador.club_id == partido.club_id,
            Jugador.equipo_id == partido.equipo_id,
        )
    )
    jugador = (await db.execute(stmt)).scalar_one_or_none()
    if jugador is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El jugador no pertenece a la alineacion de este partido",
        )
    return jugador


async def _validar_jugadores(
    db: AsyncSession, partido: Partido, datos: EventoManualCrear
) -> None:
    es_equipo_propio = datos.equipo == _lado_propio(partido)
    if not es_equipo_propio:
        if datos.jugador_id is not None or datos.jugador_entra_id is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "El rival no tiene un plantel registrado; no se aceptan ids del equipo propio",
            )
        return

    if datos.jugador_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "El evento del equipo propio requiere jugador_id",
        )
    await _exigir_jugador_alineado(db, partido, datos.jugador_id)

    if datos.tipo == TipoEventoManual.SUSTITUCION:
        if datos.jugador_entra_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "La sustitucion del equipo propio requiere jugador_entra_id",
            )
        await _exigir_jugador_alineado(db, partido, datos.jugador_entra_id)


async def _evento_por_uuid(
    db: AsyncSession, usuario: UsuarioActual, uuid: str
) -> EventoManualModelo | None:
    stmt = del_club(EventoManualModelo, usuario).where(EventoManualModelo.uuid == uuid)
    return (await db.execute(stmt)).scalar_one_or_none()


def _mismo_evento(
    existente: EventoManualModelo, partido_id: int, datos: EventoManualCrear
) -> bool:
    return (
        existente.partido_id == partido_id
        and existente.tipo == datos.tipo.value
        and existente.equipo == datos.equipo.value
        and existente.jugador_id == datos.jugador_id
        and existente.jugador_entra_id == datos.jugador_entra_id
        and (datos.minuto is None or existente.minuto == datos.minuto)
    )


async def listar_eventos_manuales(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> list[EventoManualModelo]:
    await _partido_del_club(db, usuario, partido_id)
    stmt = (
        del_club(EventoManualModelo, usuario)
        .where(
            EventoManualModelo.partido_id == partido_id,
            EventoManualModelo.anulado_en.is_(None),
        )
        .order_by(EventoManualModelo.minuto, EventoManualModelo.creado_en, EventoManualModelo.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def registrar_evento_manual(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: EventoManualCrear,
    ahora: RelojSistema = ahora_utc,
) -> EventoManualModelo:
    """Registra un evento una sola vez y toma el minuto del reloj persistente."""
    uuid = str(datos.uuid)
    existente = await _evento_por_uuid(db, usuario, uuid)
    if existente is not None:
        if not _mismo_evento(existente, partido_id, datos):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El UUID ya fue utilizado por un evento diferente",
            )
        return existente

    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se pueden registrar eventos en un partido {partido.estado}",
        )
    await _validar_jugadores(db, partido, datos)

    instante = _en_utc(ahora())
    capturado_en = (
        _en_utc(datos.capturado_en) if datos.capturado_en is not None else instante
    )
    # Un cliente no puede adelantar el reloj del partido con una fecha futura.
    instante_juego = min(capturado_en, instante)
    reloj = await _reloj_del_partido(db, usuario, partido.id)
    minuto_reloj = (
        int(segundos_transcurridos(reloj, instante_juego)) // 60
        if reloj is not None
        else partido.minuto_actual
    )
    minuto = minuto_reloj if datos.minuto is None else datos.minuto
    convertida_en_roja = False
    if datos.tipo == TipoEventoManual.AMARILLA and datos.jugador_id is not None:
        amarillas = await db.scalar(
            select(func.count())
            .select_from(EventoManualModelo)
            .where(
                EventoManualModelo.club_id == usuario.club_id,
                EventoManualModelo.partido_id == partido.id,
                EventoManualModelo.jugador_id == datos.jugador_id,
                EventoManualModelo.tipo == TipoEventoManual.AMARILLA.value,
                EventoManualModelo.anulado_en.is_(None),
            )
        )
        convertida_en_roja = bool(amarillas)

    evento = EventoManualModelo(
        club_id=usuario.club_id,
        partido_id=partido.id,
        uuid=uuid,
        tipo=datos.tipo.value,
        equipo=datos.equipo.value,
        jugador_id=datos.jugador_id,
        jugador_entra_id=datos.jugador_entra_id,
        minuto=minuto,
        origen="MANUAL",
        convertida_en_roja=convertida_en_roja,
        capturado_en=capturado_en,
        creado_en=instante,
        creado_por_id=usuario.id,
    )
    db.add(evento)

    if datos.tipo == TipoEventoManual.GOL:
        if datos.equipo == _lado_propio(partido):
            partido.goles_favor += 1
        else:
            partido.goles_contra += 1

    await db.commit()
    await db.refresh(evento)
    return evento


async def sincronizar_eventos_manuales(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    eventos: list[EventoManualCrear],
    ahora: RelojSistema = ahora_utc,
) -> list[EventoManualModelo]:
    """Procesa la cola offline en orden de captura y conserva la idempotencia.

    Cada elemento se confirma de manera independiente. Si la conexión se corta
    después de una confirmación, el móvil puede reenviar toda la cola: el UUID
    hace que los ya procesados devuelvan el mismo evento sin duplicarlo.
    """
    ordenados = sorted(
        enumerate(eventos),
        key=lambda par: (
            _en_utc(par[1].capturado_en)
            if par[1].capturado_en is not None
            else datetime.max.replace(tzinfo=UTC),
            par[0],
        ),
    )
    sincronizados: list[EventoManualModelo] = []
    for _, datos in ordenados:
        sincronizados.append(
            await registrar_evento_manual(
                db,
                usuario,
                partido_id,
                datos,
                ahora=ahora,
            )
        )
    return sincronizados


async def deshacer_evento_manual(
    db: AsyncSession,
    usuario: UsuarioActual,
    evento_id: int,
    ahora: RelojSistema = ahora_utc,
) -> None:
    stmt = del_club(EventoManualModelo, usuario).where(
        EventoManualModelo.id == evento_id,
        EventoManualModelo.anulado_en.is_(None),
    )
    evento = (await db.execute(stmt)).scalar_one_or_none()
    evento = verificar_pertenencia(evento, usuario)

    ultimo_stmt = (
        del_club(EventoManualModelo, usuario)
        .where(
            EventoManualModelo.partido_id == evento.partido_id,
            EventoManualModelo.anulado_en.is_(None),
        )
        .order_by(EventoManualModelo.creado_en.desc(), EventoManualModelo.id.desc())
        .limit(1)
    )
    ultimo = (await db.execute(ultimo_stmt)).scalar_one()
    if ultimo.id != evento.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se puede deshacer el ultimo evento activo del partido",
        )

    instante = _en_utc(ahora())
    edad_s = (instante - _en_utc(evento.creado_en)).total_seconds()
    if edad_s > 60:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El plazo de 60 segundos para deshacer el evento ya vencio",
        )

    partido = await _partido_del_club(db, usuario, evento.partido_id)
    if evento.tipo == TipoEventoManual.GOL.value:
        lado = Lado(evento.equipo)
        if lado == _lado_propio(partido):
            partido.goles_favor = max(0, partido.goles_favor - 1)
        else:
            partido.goles_contra = max(0, partido.goles_contra - 1)

    evento.anulado_en = instante
    evento.anulado_por_id = usuario.id
    await db.commit()


async def _exigir_calibracion_valida(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int
) -> None:
    stmt = select(Calibracion).where(
        Calibracion.club_id == usuario.club_id,
        Calibracion.partido_id == partido_id,
    )
    calibracion = (await db.execute(stmt)).scalar_one_or_none()
    if calibracion is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede iniciar el partido: no hay calibración para este partido",
        )
    if not calibracion.valida:
        detalle_error = (
            f"{calibracion.error_medio_m:.2f} m"
            if calibracion.error_medio_m is not None
            else "desconocido"
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede iniciar el partido: calibración no válida, error medio {detalle_error}",
        )


async def iniciar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: IniciarPartido,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30, CU-31: inicia el primer tiempo exigiendo calibración válida y dirección de ataque."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.PROGRAMADO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede iniciar un partido en estado {partido.estado}",
        )

    await _exigir_calibracion_valida(db, usuario, partido_id)

    instante = _en_utc(ahora())
    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None:
        reloj = RelojPartido(club_id=usuario.club_id, partido_id=partido.id)
        db.add(reloj)

    reloj.parte = 1
    reloj.en_curso = True
    reloj.inicio_utc = instante
    reloj.acumulado_s = 0.0
    reloj.descuento_1_min = 0
    reloj.descuento_2_min = 0

    partido.estado = EstadoPartido.EN_CURSO.value
    partido.ataca_hacia = datos.ataca_hacia.value
    partido.parte = 1
    partido.minuto_actual = 0

    limpiar_memoria_tracks(usuario.club_id, partido.id)

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def entretiempo_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: en dos llamadas, pausa el 1er tiempo y luego arranca el 2do tiempo en el min 45."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede gestionar el entretiempo de un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None or reloj.parte != 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El entretiempo solo aplica durante o al cierre del primer tiempo",
        )

    instante = _en_utc(ahora())
    if reloj.en_curso:
        # 1.ª llamada: pausa el reloj al cerrar el primer tiempo (parte=1, en_curso=False)
        reloj.acumulado_s = segundos_transcurridos(reloj, instante)
        reloj.inicio_utc = None
        reloj.en_curso = False
        reloj.parte = 1
        partido.parte = 1
        partido.minuto_actual = int(reloj.acumulado_s) // 60
    else:
        # 2.ª llamada: con parte=1 pausado, arranca el segundo tiempo en el minuto 45
        reloj.parte = 2
        reloj.en_curso = True
        reloj.acumulado_s = SEGUNDOS_PRIMER_TIEMPO
        reloj.inicio_utc = instante
        partido.parte = 2
        partido.minuto_actual = 45

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def registrar_descuento(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    datos: Descuento,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: agrega tiempo de descuento a la parte en curso (solo con el reloj corriendo)."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede agregar descuento a un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    if reloj is None or not reloj.en_curso:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se puede agregar tiempo de descuento con el reloj corriendo",
        )

    instante = _en_utc(ahora())
    if reloj.parte == 1:
        reloj.descuento_1_min = datos.minutos
    else:
        reloj.descuento_2_min = datos.minutos

    partido.minuto_actual = int(segundos_transcurridos(reloj, instante)) // 60

    await db.commit()
    await db.refresh(partido)
    await db.refresh(reloj)
    return _construir_estado_en_vivo(partido, reloj, instante)


async def finalizar_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30: detiene el cronómetro y pasa el partido a FINALIZADO."""
    partido = await _partido_del_club(db, usuario, partido_id)
    if partido.estado != EstadoPartido.EN_CURSO.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede finalizar un partido en estado {partido.estado}",
        )

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    instante = _en_utc(ahora())
    if reloj is not None:
        reloj.acumulado_s = segundos_transcurridos(reloj, instante)
        reloj.inicio_utc = None
        reloj.en_curso = False
        partido.parte = reloj.parte
        partido.minuto_actual = int(reloj.acumulado_s) // 60

    partido.estado = EstadoPartido.FINALIZADO.value

    t_cierre = calcular_t_actual(usuario.club_id, partido.id, reloj, instante)
    await _cerrar_tracks_vigentes(db, usuario.club_id, partido.id, t_cierre)

    await db.commit()
    await db.refresh(partido)
    if reloj is not None:
        await db.refresh(reloj)
    await cerrar_partido(partido.id)  # T-076 (Alejandra): cierra el último intervalo como parcial
    return _construir_estado_en_vivo(partido, reloj, instante)


async def obtener_estado_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    ahora: RelojSistema = ahora_utc,
) -> EstadoEnVivo:
    """CU-30, CU-39: devuelve el estado actual del partido y su cronómetro."""
    partido = await _partido_del_club(db, usuario, partido_id)
    reloj = await _reloj_del_partido(db, usuario, partido_id)
    return _construir_estado_en_vivo(partido, reloj, _en_utc(ahora()))


# ---------------- CU-34, CU-35 · Identificadores y asignación (T-067) ----------------

# Registro en memoria por (club_id, partido_id) para no consultar la base a 5 Hz.
# Si el proceso se reinicia, se reconstruye desde `asignacion_track` en el primer
# mensaje posterior al reinicio.
_tracks_vistos: dict[tuple[int, int], set[int]] = {}
_ultimo_t_ingesta: dict[tuple[int, int], float] = {}

# Sesión con NullPool para escrituras puntuales desde el bucle de WebSocket (/ingesta),
# evitando compartir conexiones de aiosqlite entre distintos event loops en pruebas.
_motor_ingesta = create_async_engine(settings.database_url, poolclass=NullPool)
SesionesIngesta: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _motor_ingesta, expire_on_commit=False
)


def limpiar_memoria_tracks(
    club_id: int | None = None, partido_id: int | None = None
) -> None:
    """Limpia el caché en memoria de tracks vistos y último `t` de ingesta."""
    if club_id is None or partido_id is None:
        _tracks_vistos.clear()
        _ultimo_t_ingesta.clear()
        return
    clave = (club_id, partido_id)
    _tracks_vistos.pop(clave, None)
    _ultimo_t_ingesta.pop(clave, None)


def registrar_t_ingesta(club_id: int, partido_id: int, t: float) -> None:
    """Actualiza en memoria el último `t` recibido en `/ingesta` para `(club_id, partido_id)`."""
    clave = (club_id, partido_id)
    previo = _ultimo_t_ingesta.get(clave, 0.0)
    if t >= previo:
        _ultimo_t_ingesta[clave] = float(t)


def calcular_t_actual(
    club_id: int,
    partido_id: int,
    reloj: RelojPartido | None,
    ahora: datetime,
    *,
    base_minima: float = 0.0,
) -> float:
    """Calcula `t_actual` para abrir o cerrar tramos de `AsignacionTrack` (T-067).

    Elección:
    1. Si `/ingesta` ya reportó muestras para `(club_id, partido_id)`, usa el último
       `t` visto en `/ingesta`, porque todos los `desde_t` nacen en la línea de tiempo
       del worker (`MensajeWorker.t`).
    2. Si aún no hay muestras de `/ingesta` en memoria, usa `segundos_transcurridos`
       del `RelojPartido` (T-065).
    3. Nunca devuelve un valor menor que `base_minima` (`desde_t` del tramo que se
       cierra), garantizando `hasta_t >= desde_t`.
    """
    clave = (club_id, partido_id)
    if clave in _ultimo_t_ingesta:
        t_base = _ultimo_t_ingesta[clave]
    else:
        t_base = segundos_transcurridos(reloj, ahora)
    return max(float(base_minima), float(t_base))


def _a_track_detectado(fila: AsignacionTrack) -> TrackDetectado:
    return TrackDetectado(
        track_id=fila.track_id,
        equipo_detectado=EquipoDetectado(fila.equipo_detectado),
        jugador_id=fila.jugador_id,
        desde_t=fila.desde_t,
        hasta_t=fila.hasta_t,
        confianza=fila.confianza,
    )


async def _cerrar_tracks_vigentes(
    db: AsyncSession, club_id: int, partido_id: int, t_cierre: float
) -> None:
    """Cierra todos los tramos con `hasta_t IS NULL` al finalizar el partido."""
    stmt = select(AsignacionTrack).where(
        AsignacionTrack.club_id == club_id,
        AsignacionTrack.partido_id == partido_id,
        AsignacionTrack.hasta_t.is_(None),
    )
    vigentes = (await db.execute(stmt)).scalars().all()
    for tramo in vigentes:
        tramo.hasta_t = max(float(tramo.desde_t), float(t_cierre))


async def _cerrar_otros_tramos_del_jugador(
    db: AsyncSession,
    club_id: int,
    partido_id: int,
    jugador_id: int,
    track_id_destino: int,
    t_cierre: float,
) -> None:
    """CU-35: si el jugador tenía un tramo vigente en otro track (oclusión), lo cierra en `t_cierre`."""
    stmt = select(AsignacionTrack).where(
        AsignacionTrack.club_id == club_id,
        AsignacionTrack.partido_id == partido_id,
        AsignacionTrack.jugador_id == jugador_id,
        AsignacionTrack.track_id != track_id_destino,
        AsignacionTrack.hasta_t.is_(None),
    )
    anteriores = (await db.execute(stmt)).scalars().all()
    for anterior in anteriores:
        anterior.hasta_t = max(float(anterior.desde_t), float(t_cierre))


async def listar_tracks_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    *,
    solo_activos: bool = True,
) -> list[TrackDetectado]:
    """CU-34: devuelve los tramos activos (`hasta_t IS NULL`) o el historial completo."""
    await _partido_del_club(db, usuario, partido_id)
    stmt = select(AsignacionTrack).where(
        AsignacionTrack.club_id == usuario.club_id,
        AsignacionTrack.partido_id == partido_id,
    )
    if solo_activos:
        stmt = stmt.where(AsignacionTrack.hasta_t.is_(None)).order_by(
            AsignacionTrack.track_id.asc()
        )
    else:
        stmt = stmt.order_by(
            AsignacionTrack.track_id.asc(),
            AsignacionTrack.desde_t.asc(),
            AsignacionTrack.id.asc(),
        )
    filas = (await db.execute(stmt)).scalars().all()
    return [_a_track_detectado(f) for f in filas]


async def asignar_track_partido(
    db: AsyncSession,
    usuario: UsuarioActual,
    partido_id: int,
    track_id: int,
    datos: AsignarTrack,
    ahora: RelojSistema = ahora_utc,
) -> TrackDetectado:
    """CU-34, CU-35: asigna, reasigna o desasigna un jugador a un `track_id`."""
    partido = await _partido_del_club(db, usuario, partido_id)

    if datos.jugador_id is not None:
        jugador = await db.get(Jugador, datos.jugador_id)
        if jugador is None or jugador.club_id != usuario.club_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El jugador indicado no existe en el club",
            )
        if jugador.equipo_id != partido.equipo_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El jugador indicado no pertenece al equipo del partido",
            )

    stmt_vigente = select(AsignacionTrack).where(
        AsignacionTrack.club_id == usuario.club_id,
        AsignacionTrack.partido_id == partido_id,
        AsignacionTrack.track_id == track_id,
        AsignacionTrack.hasta_t.is_(None),
    )
    tramo_vigente = (await db.execute(stmt_vigente)).scalar_one_or_none()

    reloj = await _reloj_del_partido(db, usuario, partido_id)
    instante = _en_utc(ahora())

    if tramo_vigente is None:
        stmt_hist = (
            select(AsignacionTrack)
            .where(
                AsignacionTrack.club_id == usuario.club_id,
                AsignacionTrack.partido_id == partido_id,
                AsignacionTrack.track_id == track_id,
            )
            .order_by(AsignacionTrack.desde_t.desc(), AsignacionTrack.id.desc())
            .limit(1)
        )
        ultimo_hist = (await db.execute(stmt_hist)).scalar_one_or_none()
        if ultimo_hist is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Track no encontrado en este partido",
            )
        if datos.jugador_id is None:
            return _a_track_detectado(ultimo_hist)

        base_min = (
            ultimo_hist.hasta_t
            if ultimo_hist.hasta_t is not None
            else ultimo_hist.desde_t
        )
        t_actual = calcular_t_actual(
            usuario.club_id, partido_id, reloj, instante, base_minima=base_min
        )
        await _cerrar_otros_tramos_del_jugador(
            db, usuario.club_id, partido_id, datos.jugador_id, track_id, t_actual
        )
        nuevo = AsignacionTrack(
            club_id=usuario.club_id,
            partido_id=partido_id,
            track_id=track_id,
            jugador_id=datos.jugador_id,
            equipo_detectado=ultimo_hist.equipo_detectado,
            desde_t=t_actual,
            hasta_t=None,
            confianza=ultimo_hist.confianza,
        )
        db.add(nuevo)
        await db.commit()
        await db.refresh(nuevo)
        return _a_track_detectado(nuevo)

    t_actual = calcular_t_actual(
        usuario.club_id,
        partido_id,
        reloj,
        instante,
        base_minima=tramo_vigente.desde_t,
    )

    # Desasignar: cierra el tramo vigente en t_actual
    if datos.jugador_id is None:
        tramo_vigente.hasta_t = t_actual
        await db.commit()
        await db.refresh(tramo_vigente)
        return _a_track_detectado(tramo_vigente)

    # Si el jugador viene de otro track con tramo vigente (oclusión), cierra el tramo anterior
    await _cerrar_otros_tramos_del_jugador(
        db, usuario.club_id, partido_id, datos.jugador_id, track_id, t_actual
    )

    # Primera asignación sobre un tramo sin jugador: vale desde su inicio
    if tramo_vigente.jugador_id is None:
        tramo_vigente.jugador_id = datos.jugador_id
        await db.commit()
        await db.refresh(tramo_vigente)
        return _a_track_detectado(tramo_vigente)

    # Mismo jugador: idempotente
    if tramo_vigente.jugador_id == datos.jugador_id:
        await db.commit()
        await db.refresh(tramo_vigente)
        return _a_track_detectado(tramo_vigente)

    # Reasignación a un jugador distinto: cierra en t_actual y abre tramo nuevo desde t_actual
    tramo_vigente.hasta_t = t_actual
    await db.flush()

    nuevo = AsignacionTrack(
        club_id=usuario.club_id,
        partido_id=partido_id,
        track_id=track_id,
        jugador_id=datos.jugador_id,
        equipo_detectado=tramo_vigente.equipo_detectado,
        desde_t=t_actual,
        hasta_t=None,
        confianza=tramo_vigente.confianza,
    )
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return _a_track_detectado(nuevo)


async def registrar_tracks_ingesta(
    club_id: int,
    mensaje: MensajeWorker,
    sesiones: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Gancho mínimo invocado desde `/ingesta`: registra tracks nuevos sin consultar a 5 Hz.

    - Mantiene en `_tracks_vistos[(club_id, partido_id)]` los `track_id` ya vistos.
    - Si la clave no está en memoria (primer mensaje del partido o tras reinicio del
      servidor), la reconstruye una sola vez desde `asignacion_track` sin duplicar tramos.
    - Solo escribe en base de datos cuando aparece al menos un `track_id` nuevo (un único
      `INSERT` por mensaje con tracks nuevos; 0 consultas si todos los tracks ya fueron vistos).
    - Cualquier excepción se captura y registra para no interrumpir `/ingesta` ni `/vivo`.
    """
    try:
        partido_id = mensaje.partido
        registrar_t_ingesta(club_id, partido_id, mensaje.t)
        if not mensaje.jugadores:
            return

        clave = (club_id, partido_id)
        vistos = _tracks_vistos.get(clave)

        # Vía rápida a 5 Hz: si el partido ya está hidratado y ningún tid es nuevo, 0 consultas
        if vistos is not None and all(j.tid in vistos for j in mensaje.jugadores):
            return

        fabrica = sesiones or SesionesIngesta
        async with fabrica() as db:
            if vistos is None:
                stmt = select(AsignacionTrack.track_id).where(
                    AsignacionTrack.club_id == club_id,
                    AsignacionTrack.partido_id == partido_id,
                )
                existentes = set((await db.execute(stmt)).scalars().all())
                vistos = _tracks_vistos.setdefault(clave, set())
                vistos.update(existentes)

            filas_nuevas: list[dict[str, Any]] = []
            tids_nuevos: set[int] = set()
            for j in mensaje.jugadores:
                if j.tid in vistos or j.tid in tids_nuevos:
                    continue
                tids_nuevos.add(j.tid)
                filas_nuevas.append(
                    {
                        "club_id": club_id,
                        "partido_id": partido_id,
                        "track_id": j.tid,
                        "jugador_id": None,
                        "equipo_detectado": j.equipo.value,
                        "desde_t": float(mensaje.t),
                        "hasta_t": None,
                        "confianza": float(j.conf),
                    }
                )

            if not filas_nuevas:
                return

            await db.execute(insert(AsignacionTrack), filas_nuevas)
            await db.commit()
            vistos.update(tids_nuevos)
    except Exception:
        log.exception(
            "No se pudieron registrar los tracks nuevos del partido %s (club %s)",
            mensaje.partido,
            club_id,
        )


# ---------------- Acceso a partidos (T-032) ----------------
#
# Los WebSockets necesitan saber si un partido existe y es del club del
# usuario. La consulta queda detrás de esta interfaz porque un WebSocket vive
# todo el encuentro y no debe retener la sesión HTTP durante 90 minutos.
MODELO_PARTIDO: type[Any] = Partido


class RepositorioPartidos(Protocol):
    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> str | None:
        """Devuelve el estado del partido si es accesible; si no, lanza 404.

        `None` significa "estado desconocido" (solo `PartidosSinTabla`).
        """
        ...


class PartidosEnTabla:
    """Verificación real, a través de `tenancy`.

    Abre su propia sesión corta en vez de recibir la de la petición: un
    WebSocket vive todo el partido y no puede retener una conexión del pool
    durante 90 minutos.
    """

    def __init__(self, modelo: type[Any],
                 sesiones: async_sessionmaker[AsyncSession] = SessionLocal) -> None:
        self.modelo = modelo
        self.sesiones = sesiones

    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> str | None:
        async with self.sesiones() as db:
            partido = verificar_pertenencia(await db.get(self.modelo, partido_id), usuario)
            return partido.estado


class PartidosSinTabla:
    """SOLO PARA PRUEBAS: acepta cualquier `partido_id` sin consultar la base.

    Lo usan las pruebas del canal y del emisor que no necesitan sembrar
    partidos. En producción se usa siempre `PartidosEnTabla`. Aun así no hay
    fuga entre clubes: el canal del Hub lleva el `club_id` del token
    (`canal_partido`).
    """

    async def verificar(self, partido_id: int, usuario: UsuarioActual) -> str | None:
        return None


def obtener_repositorio_partidos() -> RepositorioPartidos:
    """Dependencia de FastAPI."""
    return PartidosEnTabla(MODELO_PARTIDO)


# ---------------- Persistencia de posiciones (T-033) ----------------

MODELO_POSICION: type[Any] = Posicion


def filas_de(mensaje: MensajeWorker) -> list[dict[str, Any]]:
    """Una fila por punto detectado: los jugadores y, si se ve, el balón.

    T-074: `es_balon` distingue la fila del balón, que de otro modo sería una
    fila más (lo necesita el recálculo de posesión desde la tabla).
    """
    puntos = [(p, False) for p in mensaje.jugadores]
    if mensaje.balon:
        puntos.append((mensaje.balon, True))
    return [
        {"partido_id": mensaje.partido, "t": mensaje.t, "track_id": p.tid,
         "x_m": p.x, "y_m": p.y, "confianza": p.conf, "es_balon": es_balon}
        for p, es_balon in puntos
    ]


class ObservadorPosiciones(Protocol):
    """Recibe cada mensaje que entra al almacén (T-074…T-076: el motor de métricas).

    `vaciar` guarda lo pendiente de ese partido; el observador lo usa antes de
    leer la tabla `posicion`.
    """

    async def procesar(self, mensaje: MensajeWorker,
                       vaciar: Callable[[], Any] | None = None) -> None: ...


class AnalisisDelProceso:
    """Delega en el análisis en vivo del proceso (`app/analisis/vivo.py`).

    Se resuelve en cada llamada, así una prueba puede instalar otra instancia
    después de creado el almacén. El import es tardío para no crear un ciclo
    (`app.analisis` usa `normalizar_coordenadas` de este módulo).
    """

    async def procesar(self, mensaje: MensajeWorker,
                       vaciar: Callable[[], Any] | None = None) -> None:
        from app.analisis.vivo import obtener_analisis_en_vivo
        await obtener_analisis_en_vivo().procesar(mensaje, vaciar)


async def cerrar_partido(partido_id: int) -> None:
    """T-076: al finalizar, cierra el último intervalo de métricas como parcial."""
    from app.analisis.vivo import obtener_analisis_en_vivo
    await obtener_analisis_en_vivo().cerrar_partido(partido_id)


class AlmacenPosiciones(Protocol):
    async def agregar(self, mensaje: MensajeWorker) -> None: ...

    async def vaciar(self) -> None:
        """Guarda todo lo pendiente. Se llama también al desconectarse el worker."""
        ...


class PosicionesEnLote:
    """Acumula mensajes y los inserta de a lotes, con un solo INSERT masivo.

    A 5 Hz con 23 puntos, un partido son ~620.000 filas: de a una serían horas
    (ver la nota de `posicion` en el modelo de datos). `insert(Modelo)` con una
    lista de diccionarios es la inserción masiva de SQLAlchemy 2, el equivalente
    al `bulk_create` de Django: un único `executemany` por lote.

    Hay UNA instancia por proceso (`obtener_almacen_posiciones`), con un buffer
    por partido. Así da igual cuántas veces se pida el almacén: todas las
    llamadas de un mismo partido acumulan en el mismo buffer. Un partido se
    guarda cuando:
      - junta `tamano_lote` mensajes,
      - alguien llama a `vaciar()` (fin de la ingesta, fin de un lote de video),
      - pasan `inactividad_s` segundos sin datos nuevos de ese partido, o
      - la API se apaga (`lifespan` en `app/main.py`).

    Si tiene un `analisis` (T-074…T-076), le pasa cada mensaje antes de
    guardarlo en el buffer: así el motor de métricas ve TODAS las posiciones,
    vengan de /ingesta, de /resultados o del respaldo local.
    """

    TAMANO_LOTE = 25       # mensajes: 5 s de partido, unas 575 filas
    INACTIVIDAD_S = 3.0    # sin datos durante este tiempo, se guarda lo pendiente

    def __init__(self, modelo: type[Any],
                 sesiones: async_sessionmaker[AsyncSession] = SessionLocal,
                 tamano_lote: int = TAMANO_LOTE,
                 inactividad_s: float = INACTIVIDAD_S,
                 analisis: ObservadorPosiciones | None = None) -> None:
        self.modelo = modelo
        self.analisis = analisis
        self.sesiones = sesiones
        self.tamano_lote = tamano_lote
        self.inactividad_s = inactividad_s
        self._filas: dict[int, list[dict[str, Any]]] = {}
        self._mensajes: dict[int, int] = {}
        self._temporizadores: dict[int, asyncio.TimerHandle] = {}
        self._tareas: set[asyncio.Task[None]] = set()

    def pendientes(self, partido_id: int) -> int:
        """Filas que esperan ser guardadas para ese partido."""
        return len(self._filas.get(partido_id, ()))

    async def agregar(self, mensaje: MensajeWorker) -> None:
        partido = mensaje.partido
        if self.analisis is not None:
            await self.analisis.procesar(mensaje, lambda: self._guardar(partido))
        self._filas.setdefault(partido, []).extend(filas_de(mensaje))
        self._mensajes[partido] = self._mensajes.get(partido, 0) + 1
        if self._mensajes[partido] >= self.tamano_lote:
            await self._guardar(partido)
        else:
            self._programar(partido)

    async def vaciar(self) -> None:
        for partido in list(self._filas):
            await self._guardar(partido)

    def _programar(self, partido: int) -> None:
        """(Re)inicia la cuenta de inactividad del partido."""
        self._cancelar(partido)
        loop = asyncio.get_running_loop()
        self._temporizadores[partido] = loop.call_later(
            self.inactividad_s, self._al_vencer, partido)

    def _cancelar(self, partido: int) -> None:
        temporizador = self._temporizadores.pop(partido, None)
        if temporizador is not None:
            temporizador.cancel()

    def _al_vencer(self, partido: int) -> None:
        self._temporizadores.pop(partido, None)
        tarea = asyncio.get_running_loop().create_task(self._guardar(partido))
        self._tareas.add(tarea)   # referencia viva hasta que termine
        tarea.add_done_callback(self._tareas.discard)

    async def _guardar(self, partido: int) -> None:
        self._cancelar(partido)
        # Se saca del buffer ANTES del await: otro guardado concurrente del
        # mismo partido no puede insertar las mismas filas dos veces.
        filas = self._filas.pop(partido, None)
        self._mensajes.pop(partido, None)
        if not filas:
            return
        try:
            async with self.sesiones() as db:
                await db.execute(insert(self.modelo), filas)
                await db.commit()
        except SQLAlchemyError:
            # Perder un lote es preferible a cortar la ingesta: el panel en vivo
            # sigue funcionando aunque la base falle un momento.
            log.exception("No se pudo guardar un lote de %d posiciones del partido %s",
                          len(filas), partido)


class PosicionesDescartadas:
    """SOLO PARA PRUEBAS: no guarda nada (pruebas que no miran la tabla)."""

    async def agregar(self, mensaje: MensajeWorker) -> None:
        pass

    async def vaciar(self) -> None:
        pass


_almacen: dict[str, PosicionesEnLote] = {}


def obtener_almacen_posiciones() -> AlmacenPosiciones:
    """Dependencia de FastAPI. Siempre devuelve el MISMO almacén del proceso.

    Así, llamarla en cada mensaje (como hace el procesamiento local de video)
    no pierde nada: todo cae en el buffer de su partido.
    """
    if "unico" not in _almacen:
        _almacen["unico"] = PosicionesEnLote(MODELO_POSICION, analisis=AnalisisDelProceso())
    return _almacen["unico"]


async def vaciar_almacen_posiciones() -> None:
    """Guarda lo pendiente de todos los partidos. Se llama al apagar la API."""
    almacen = _almacen.get("unico")
    if almacen is not None:
        await almacen.vaciar()


def reiniciar_almacen_posiciones() -> None:
    """Para pruebas: descarta el almacén del proceso (y su buffer)."""
    _almacen.clear()
