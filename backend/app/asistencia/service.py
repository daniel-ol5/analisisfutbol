"""Evaluación y consulta de recomendaciones tácticas (CU-49)."""

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis import persistencia
from app.analisis.metricas import metricas_jugadores_intervalos
from app.analisis.motor.motor import MotorPartido
from app.analisis.parametros import PARAMETROS
from app.asistencia import models
from app.asistencia.alertas import Bloque, alertas_expulsion, alertas_fatiga, ordenar
from app.asistencia.alertas import Jugador as JugadorAlerta
from app.asistencia.contexto import INTERVALO_EVALUACION_S, EstadoTactico, campo_suficiente
from app.asistencia.motor import (
    ORDEN_PRIORIDAD,
    MetricaNoDisponible,
    ReglaInvalida,
    evaluar_regla,
    validar_regla,
)
from app.asistencia.push import MensajePush, ProveedorPush, ResultadoPush, obtener_proveedor_push
from app.asistencia.schemas import (
    Alerta,
    DispositivoRegistrar,
    EstadoEnvioPush,
    EstadoRecomendacion,
    Prioridad,
    PruebaRegla,
    Recomendacion,
    Regla,
    ReglaCrear,
    ReglaEditar,
    ResultadoPrueba,
)
from app.core.deps import UsuarioActual
from app.core.tenancy import verificar_pertenencia
from app.deportivo.models import Jugador as JugadorFicha
from app.deportivo.models import Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import EventoManual, RelojPartido
from app.partido.schemas import Lado, TipoEventoManual
from app.partido.service import segundos_transcurridos
from app.seguridad.models import Usuario

log = logging.getLogger(__name__)
MAX_RECOMENDACIONES_ACTIVAS = 3


async def _reglas_disponibles(
    db: AsyncSession, club_id: int, activas: bool | None
) -> list[tuple[models.ReglaTactica, bool]]:
    """Reglas globales y propias del club, con su activación EFECTIVA para ese club.

    Una regla global puede estar desactivada solo para este club (`regla_club`).
    La activación se devuelve aparte a propósito: escribirla sobre la fila de
    `regla_tactica` la cambiaría para todos los clubes al hacer commit.
    """
    tabla, por_club = models.ReglaTactica, models.ReglaClub
    efectiva = func.coalesce(por_club.activa, tabla.activa)
    stmt = (
        select(tabla, efectiva)
        .outerjoin(por_club, (por_club.regla_id == tabla.id) & (por_club.club_id == club_id))
        .where(or_(tabla.club_id.is_(None), tabla.club_id == club_id))
    )
    if activas is not None:
        stmt = stmt.where(efectiva == activas)
    return [(fila, bool(activa)) for fila, activa in (await db.execute(stmt.order_by(tabla.id))).all()]


def _a_regla(registro: models.ReglaTactica, activa: bool) -> Regla:
    return Regla.model_validate(registro).model_copy(update={"activa": activa})


async def listar_reglas(db: AsyncSession, usuario: UsuarioActual, activas: bool | None) -> list[Regla]:
    return [_a_regla(r, a) for r, a in await _reglas_disponibles(db, usuario.club_id, activas)]


# ---------------- CU-54 · Catálogo de reglas (T-092) ----------------

def _validar(condicion: dict, plantilla_mensaje: str, plantilla_justificacion: str) -> None:
    try:
        validar_regla(condicion, plantilla_mensaje, plantilla_justificacion)
    except (ReglaInvalida, MetricaNoDisponible) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Regla inválida: {e}") from None


async def crear_regla(db: AsyncSession, usuario: UsuarioActual, datos: ReglaCrear) -> Regla:
    _validar(datos.condicion, datos.plantilla_mensaje, datos.plantilla_justificacion)
    registro = models.ReglaTactica(club_id=usuario.club_id, **datos.model_dump(mode="json"))
    db.add(registro)
    await db.commit()
    return _a_regla(registro, registro.activa)


async def _regla_visible(
    db: AsyncSession, usuario: UsuarioActual, regla_id: int
) -> models.ReglaTactica:
    """Una regla global o del club del usuario; 404 si no existe o es de otro club."""
    registro = await db.get(models.ReglaTactica, regla_id)
    if registro is None or registro.club_id not in (None, usuario.club_id):
        # 404 y no 403 para no revelar reglas de otro club (igual que verificar_pertenencia).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regla no encontrada")
    return registro


async def probar_regla(
    db: AsyncSession, usuario: UsuarioActual, regla_id: int, datos: PruebaRegla
) -> ResultadoPrueba:
    """Cuántas veces se habría disparado la regla en un partido ya registrado.

    Reproduce las posiciones guardadas con el mismo estado táctico y la misma
    cadencia que en vivo, y respeta el cooldown de la regla. La regla se prueba
    aunque esté desactivada: es justamente para decidir si conviene activarla.
    No guarda nada.
    """
    registro = await _regla_visible(db, usuario, regla_id)
    partido = verificar_pertenencia(await db.get(Partido, datos.partido_id), usuario)
    regla = _a_regla(registro, activa=True)

    tarjetas = await _tarjetas_propias(db, partido)
    equipos = persistencia.equipos_de(await persistencia.tramos_de(db, partido))
    analisis = MotorPartido(await persistencia.contexto_de(db, partido), PARAMETROS,
                            await persistencia.arqueros_de(db, partido))
    tactica = EstadoTactico()
    ultima_evaluacion = ultimo_disparo = float("-inf")
    evaluaciones, minutos = 0, []
    async for muestra in persistencia.muestras_de(db, partido.id, equipos):
        if not tactica.observar_muestra(muestra, analisis, campo_suficiente(muestra)):
            continue
        t = muestra.t
        if t - ultima_evaluacion < INTERVALO_EVALUACION_S:
            continue
        ultima_evaluacion, evaluaciones = t, evaluaciones + 1
        minuto = int(t // 60)
        metricas = {**tactica.metricas(), **contar_disciplina(tarjetas, minuto), "minuto": minuto}
        try:
            disparo = evaluar_regla(regla, metricas)
        except ReglaInvalida as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Regla inválida: {e}") from None
        if disparo is not None and t - ultimo_disparo >= regla.cooldown_s:
            ultimo_disparo = t
            minutos.append(minuto)
    return ResultadoPrueba(disparos=len(minutos), minutos=minutos, evaluaciones=evaluaciones)


async def editar_regla(
    db: AsyncSession, usuario: UsuarioActual, regla_id: int, datos: ReglaEditar
) -> Regla:
    """Edita una regla propia, o activa/desactiva una global solo para este club."""
    registro = await _regla_visible(db, usuario, regla_id)
    # Un campo enviado como null cuenta como "no cambiar".
    cambios = {k: v for k, v in datos.model_dump(mode="json", exclude_unset=True).items()
               if v is not None}
    if registro.club_id is None:
        await _activar_global_para_club(db, usuario.club_id, regla_id, cambios)
    elif cambios:
        await _editar_propia(db, registro, cambios)

    activa = next(a for r, a in await _reglas_disponibles(db, usuario.club_id, None)
                  if r.id == regla_id)
    return _a_regla(registro, activa)


async def _activar_global_para_club(
    db: AsyncSession, club_id: int, regla_id: int, cambios: dict
) -> None:
    if set(cambios) - {"activa"}:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Las reglas globales solo se pueden activar o desactivar para tu club. "
            "Para cambiar su contenido, crea una regla propia.",
        )
    if "activa" not in cambios:
        return
    await db.execute(
        pg_insert(models.ReglaClub)
        .values(club_id=club_id, regla_id=regla_id, activa=cambios["activa"])
        .on_conflict_do_update(constraint="uq_regla_club", set_={"activa": cambios["activa"]})
    )
    await db.commit()


async def _editar_propia(db: AsyncSession, registro: models.ReglaTactica, cambios: dict) -> None:
    _validar(
        cambios.get("condicion", registro.condicion),
        cambios.get("plantilla_mensaje", registro.plantilla_mensaje),
        cambios.get("plantilla_justificacion", registro.plantilla_justificacion),
    )
    for campo, valor in cambios.items():
        setattr(registro, campo, valor)
    await db.commit()


async def _tarjetas_propias(db: AsyncSession, partido: Partido) -> list[tuple[str, int]]:
    """(tipo, minuto) de las tarjetas propias registradas y no anuladas del partido."""
    equipo = Lado.LOCAL.value if partido.es_local else Lado.VISITANTE.value
    e = EventoManual
    filas = await db.execute(
        select(e.tipo, e.minuto).where(
            e.club_id == partido.club_id, e.partido_id == partido.id, e.equipo == equipo,
            e.anulado_en.is_(None),
            e.tipo.in_((TipoEventoManual.AMARILLA.value, TipoEventoManual.ROJA.value)),
        )
    )
    return [(tipo, minuto) for tipo, minuto in filas.all()]


def contar_disciplina(tarjetas: list[tuple[str, int]], minuto: int) -> dict[str, float]:
    """Amarillas de los últimos 10 minutos y rojas hasta `minuto`, incluido."""
    vigentes = [(tipo, m) for tipo, m in tarjetas if m <= minuto]
    return {
        "amarillas_propias_10min": sum(1 for tipo, m in vigentes
                                       if tipo == TipoEventoManual.AMARILLA.value and m >= minuto - 9),
        "rojas_propias": sum(1 for tipo, _ in vigentes if tipo == TipoEventoManual.ROJA.value),
    }


async def _disciplina(db: AsyncSession, partido: Partido, minuto: int) -> dict[str, float]:
    """Cuenta tarjetas propias registradas y vigentes, incluida una segunda amarilla como roja."""
    return contar_disciplina(await _tarjetas_propias(db, partido), minuto)


async def registrar_dispositivo(
    db: AsyncSession, usuario: UsuarioActual, datos: DispositivoRegistrar
) -> None:
    """Registra o rota el token de una instalacion para el usuario autenticado."""
    tabla = models.DispositivoPush
    dispositivo = await db.scalar(
        select(tabla).where(tabla.instalacion_id == datos.instalacion_id).with_for_update()
    )

    # Un token FCM identifica una sola instalacion activa. Al iniciar sesion en
    # otro usuario o regenerarse la instalacion se desactiva la asociacion vieja.
    asociados = list((await db.scalars(
        select(tabla).where(tabla.token == datos.token, tabla.activo.is_(True)).with_for_update()
    )).all())
    for anterior in asociados:
        if dispositivo is None or anterior.id != dispositivo.id:
            anterior.activo = False
            anterior.ultimo_error = "Token reasignado a otra instalacion autenticada"
            anterior.actualizado_en = datetime.now(UTC)
    if asociados:
        await db.flush()

    if dispositivo is None:
        dispositivo = tabla(instalacion_id=datos.instalacion_id)
        db.add(dispositivo)
    dispositivo.club_id = usuario.club_id
    dispositivo.usuario_id = usuario.id
    dispositivo.token = datos.token
    dispositivo.plataforma = datos.plataforma.value
    dispositivo.activo = True
    dispositivo.ultimo_error = None
    dispositivo.actualizado_en = datetime.now(UTC)
    await db.commit()


def _mensaje_push(recomendacion: models.Recomendacion) -> MensajePush:
    ruta = (
        f"/asistencia?partido_id={recomendacion.partido_id}"
        f"&recomendacion_id={recomendacion.id}"
    )
    return MensajePush(
        titulo="Recomendacion tactica critica",
        cuerpo=recomendacion.mensaje,
        datos={
            "tipo": "recomendacion_tactica",
            "recomendacion_id": str(recomendacion.id),
            "partido_id": str(recomendacion.partido_id),
            "prioridad": recomendacion.prioridad,
            "ruta": ruta,
        },
    )


async def notificar_recomendaciones(
    db: AsyncSession,
    recomendacion_ids: list[int],
    proveedor: ProveedorPush | None = None,
) -> int:
    """Envia una vez cada recomendacion critica a dispositivos del mismo club."""
    proveedor = proveedor or obtener_proveedor_push()
    if proveedor is None or not recomendacion_ids:
        return 0

    filas = (await db.execute(
        select(models.Recomendacion, Partido.club_id)
        .join(Partido, Partido.id == models.Recomendacion.partido_id)
        .where(models.Recomendacion.id.in_(recomendacion_ids))
        .with_for_update(of=models.Recomendacion)
    )).all()
    enviados = 0
    for recomendacion, club_id in filas:
        if recomendacion.prioridad != Prioridad.CRITICA.value:
            continue

        dispositivos = list((await db.scalars(
            select(models.DispositivoPush)
            .join(Usuario, Usuario.id == models.DispositivoPush.usuario_id)
            .where(
                models.DispositivoPush.club_id == club_id,
                models.DispositivoPush.activo.is_(True),
                Usuario.activo.is_(True),
            )
            .order_by(models.DispositivoPush.id)
        )).all())
        ya_reclamados = set((await db.scalars(
            select(models.EnvioPush.dispositivo_id).where(
                models.EnvioPush.recomendacion_id == recomendacion.id
            )
        )).all())
        dispositivos = [d for d in dispositivos if d.id not in ya_reclamados]
        if not dispositivos:
            continue

        intentos = [
            models.EnvioPush(
                recomendacion_id=recomendacion.id,
                dispositivo_id=dispositivo.id,
            )
            for dispositivo in dispositivos
        ]
        db.add_all(intentos)
        # La confirmacion previa reclama estos destinos y evita dobles envios
        # si dos procesos intentan notificar la misma recomendacion a la vez.
        await db.commit()

        try:
            resultados = await proveedor.enviar(
                [dispositivo.token for dispositivo in dispositivos],
                _mensaje_push(recomendacion),
            )
            if len(resultados) != len(intentos):
                raise RuntimeError("El proveedor devolvio una cantidad de resultados invalida")
        except Exception as exc:
            log.exception("Fallo el proveedor push para la recomendacion %s", recomendacion.id)
            resultados = [ResultadoPush(enviado=False, error=str(exc)[:400])] * len(intentos)

        instante = datetime.now(UTC)
        for intento, dispositivo, resultado in zip(
            intentos, dispositivos, resultados, strict=True
        ):
            if resultado.enviado:
                intento.estado = EstadoEnvioPush.ENVIADO.value
                intento.proveedor_id = resultado.proveedor_id
                intento.enviado_en = instante
                enviados += 1
            else:
                intento.estado = EstadoEnvioPush.ERROR.value
                intento.error = resultado.error or "Error no especificado por el proveedor"
            if resultado.token_invalido:
                dispositivo.activo = False
                dispositivo.ultimo_error = intento.error or "Token FCM invalido"
                dispositivo.actualizado_en = instante
        await db.commit()
    return enviados


async def evaluar_en_vivo(
    db: AsyncSession,
    partido_id: int,
    club_id: int,
    t: float,
    observadas: Mapping[str, float],
    proveedor_push: ProveedorPush | None = None,
) -> bool:
    """Evalúa una muestra de estado real. False indica que el reloj está detenido.

    Se bloquea la fila de partido en PostgreSQL para serializar comprobación de
    cooldown, escritura y finalización. La ingesta también serializa el acceso
    al estado táctico de este partido dentro del proceso.
    """
    partido = await db.scalar(
        select(Partido).join(RelojPartido, RelojPartido.partido_id == Partido.id)
        .where(Partido.id == partido_id, Partido.club_id == club_id,
               Partido.estado == EstadoPartido.EN_CURSO.value,
               RelojPartido.club_id == club_id, RelojPartido.en_curso.is_(True))
        .with_for_update(of=Partido)
    )
    if partido is None:
        return False

    reglas = await _reglas_disponibles(db, club_id, activas=True)
    if not reglas:
        return True
    minuto = int(t // 60)
    metricas = {**observadas, **await _disciplina(db, partido, minuto), "minuto": minuto}
    pendientes: list[models.Recomendacion] = []
    for registro, activa in reglas:
        try:
            regla = _a_regla(registro, activa)
            disparo = evaluar_regla(regla, metricas)
        except (ReglaInvalida, ValidationError) as exc:
            log.warning("Regla táctica %s inválida: %s", registro.id, exc)
            continue
        if disparo is not None:
            pendientes.append(models.Recomendacion(
                partido_id=partido.id, regla_id=regla.id, t=t, minuto=minuto,
                mensaje=disparo.mensaje, justificacion=disparo.justificacion,
                datos_soporte=[d.model_dump() for d in disparo.datos_soporte],
                prioridad=regla.prioridad.value,
            ))

    if pendientes:
        r = models.Recomendacion
        cooldown = {registro.id: registro.cooldown_s for registro, _ in reglas}
        filas = (await db.execute(
            select(r.regla_id, func.max(r.t)).where(
                r.partido_id == partido.id, r.regla_id.in_([p.regla_id for p in pendientes]),
            ).group_by(r.regla_id)
        )).all()
        ultimos = {regla_id: ultimo_t for regla_id, ultimo_t in filas}
        nuevas = [
            p
            for p in pendientes
            if t - ultimos.get(p.regla_id, float("-inf")) >= cooldown[p.regla_id]
        ]
        db.add_all(nuevas)
        await db.commit()
        await notificar_recomendaciones(
            db,
            [recomendacion.id for recomendacion in nuevas],
            proveedor_push,
        )
    return True


# ---------------- CU-52 · Alertas de fatiga y riesgo de expulsión ----------------

async def _minuto_actual(db: AsyncSession, partido: Partido, bloques: dict[int, list[Bloque]]) -> int:
    """El del cronómetro si existe; nunca menos que el final del último bloque medido
    (un video procesado después del partido no tiene cronómetro corriendo)."""
    reloj = await db.scalar(select(RelojPartido).where(
        RelojPartido.club_id == partido.club_id, RelojPartido.partido_id == partido.id))
    minuto = (int(segundos_transcurridos(reloj, datetime.now(UTC))) // 60
              if reloj is not None else partido.minuto_actual)
    finales = [b.minuto_hasta for lista in bloques.values() for b in lista]
    return max([minuto, *finales])


def _situacion_propia(
    eventos: Sequence[tuple[str, str, int | None, int | None, int]],
) -> tuple[dict[int, int], set[int], dict[int, int]]:
    """De los eventos propios: amarillas por jugador, quiénes ya no están en cancha
    (sustituidos, expulsados o con doble amarilla) y en qué minuto entró cada suplente."""
    amarillas: dict[int, int] = defaultdict(int)
    fuera: set[int] = set()
    entro: dict[int, int] = {}
    for tipo, _, jugador_id, jugador_entra_id, minuto in eventos:
        if tipo == TipoEventoManual.SUSTITUCION.value and jugador_entra_id is not None:
            entro[jugador_entra_id] = minuto
        if jugador_id is None:
            continue
        if tipo == TipoEventoManual.AMARILLA.value:
            amarillas[jugador_id] += 1
        elif tipo in (TipoEventoManual.ROJA.value, TipoEventoManual.SUSTITUCION.value):
            fuera.add(jugador_id)
    fuera.update(j for j, n in amarillas.items() if n >= 2)
    return amarillas, fuera, entro


async def alertas_partido(db: AsyncSession, usuario: UsuarioActual, partido_id: int) -> list[Alerta]:
    """CU-52: alertas de los jugadores propios, calculadas al consultar (no se guardan)."""
    partido = verificar_pertenencia(await db.get(Partido, partido_id), usuario)
    propio = Lado.LOCAL.value if partido.es_local else Lado.VISITANTE.value

    por_jugador = await metricas_jugadores_intervalos(db, usuario, partido.id, propio)
    bloques = {
        m.jugador_id: [Bloque(i["minuto_desde"], i["minuto_hasta"], i["distancia_m"],
                              i["velocidad_max_kmh"], i["minutos_jugados"]) for i in m.intervalos]
        for m in por_jugador
    }

    e = EventoManual
    eventos = (await db.execute(
        select(e.tipo, e.equipo, e.jugador_id, e.jugador_entra_id, e.minuto).where(
            e.club_id == partido.club_id, e.partido_id == partido.id, e.anulado_en.is_(None))
    )).all()
    tarjetas = (TipoEventoManual.AMARILLA.value, TipoEventoManual.ROJA.value)
    tarjetas_partido = [(tipo, minuto) for tipo, _, _, _, minuto in eventos if tipo in tarjetas]
    amarillas, fuera, entro = _situacion_propia([ev for ev in eventos if ev[1] == propio])

    ids = set(bloques) | set(amarillas) | set(entro)
    fichas = {} if not ids else {j.id: j for j in (await db.scalars(
        select(JugadorFicha).where(JugadorFicha.club_id == partido.club_id,
                                   JugadorFicha.id.in_(ids)))).all()}
    jugadores = {
        jid: JugadorAlerta(
            jugador_id=jid,
            nombre=(fichas[jid].apellido or fichas[jid].nombre) if jid in fichas else None,
            dorsal=fichas[jid].dorsal if jid in fichas else None,
            entro_min=entro.get(jid, 0), en_cancha=jid not in fuera, amarillas=amarillas[jid],
        )
        for jid in ids
    }
    minuto = await _minuto_actual(db, partido, bloques)
    return ordenar([*alertas_fatiga(bloques, jugadores, minuto),
                    *alertas_expulsion(jugadores, tarjetas_partido, minuto)])


async def listar_recomendaciones(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, solo_activas: bool
) -> list[Recomendacion]:
    verificar_pertenencia(await db.get(Partido, partido_id), usuario)
    r = models.Recomendacion
    stmt = select(r).where(r.partido_id == partido_id).order_by(r.t.desc(), r.id.desc())
    if solo_activas:
        # Activas PARA ESTE CLUB: una global desactivada por el club deja de mostrarse.
        ids_activas = [regla.id for regla, _ in
                       await _reglas_disponibles(db, usuario.club_id, activas=True)]
        stmt = stmt.where(r.regla_id.in_(ids_activas))
    filas = (await db.scalars(stmt)).all()
    if not solo_activas:
        return [Recomendacion.model_validate(fila) for fila in filas]

    ultimas: dict[int, models.Recomendacion] = {}
    for fila in filas:
        ultimas.setdefault(fila.regla_id, fila)
    visibles = (
        fila for fila in ultimas.values()
        if fila.estado in (EstadoRecomendacion.PENDIENTE, EstadoRecomendacion.VISTA)
    )
    ordenadas = sorted(visibles, key=lambda f: (ORDEN_PRIORIDAD[Prioridad(f.prioridad)], -f.t, -f.id))
    return [Recomendacion.model_validate(fila) for fila in ordenadas[:MAX_RECOMENDACIONES_ACTIVAS]]
