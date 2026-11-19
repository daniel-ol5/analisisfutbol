"""Evaluación y consulta de recomendaciones tácticas (CU-49)."""

import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.asistencia import models
from app.asistencia.motor import ORDEN_PRIORIDAD, ReglaInvalida, evaluar_regla
from app.asistencia.push import MensajePush, ProveedorPush, ResultadoPush, obtener_proveedor_push
from app.asistencia.schemas import (
    DispositivoRegistrar,
    EstadoEnvioPush,
    EstadoRecomendacion,
    Prioridad,
    Recomendacion,
    Regla,
)
from app.core.deps import UsuarioActual
from app.core.tenancy import verificar_pertenencia
from app.deportivo.models import Partido
from app.deportivo.schemas import EstadoPartido
from app.partido.models import EventoManual, RelojPartido
from app.partido.schemas import Lado, TipoEventoManual
from app.seguridad.models import Usuario

log = logging.getLogger(__name__)
MAX_RECOMENDACIONES_ACTIVAS = 3


async def _reglas_disponibles(
    db: AsyncSession, club_id: int, activas: bool | None
) -> list[models.ReglaTactica]:
    tabla = models.ReglaTactica
    stmt = select(tabla).where(or_(tabla.club_id.is_(None), tabla.club_id == club_id))
    if activas is not None:
        stmt = stmt.where(tabla.activa.is_(activas))
    return list((await db.scalars(stmt.order_by(tabla.id))).all())


async def listar_reglas(db: AsyncSession, usuario: UsuarioActual, activas: bool | None) -> list[Regla]:
    return [Regla.model_validate(r) for r in await _reglas_disponibles(db, usuario.club_id, activas)]


async def _disciplina(db: AsyncSession, partido: Partido, minuto: int) -> dict[str, float]:
    """Cuenta tarjetas propias registradas y vigentes, incluida una segunda amarilla como roja."""
    equipo = Lado.LOCAL.value if partido.es_local else Lado.VISITANTE.value
    e = EventoManual
    conteos = (await db.execute(
        select(
            func.count().filter(e.tipo == TipoEventoManual.AMARILLA.value, e.minuto >= minuto - 9),
            func.count().filter(e.tipo == TipoEventoManual.ROJA.value),
        ).where(e.club_id == partido.club_id, e.partido_id == partido.id, e.equipo == equipo,
                e.anulado_en.is_(None), e.minuto <= minuto)
    )).one()
    return {"amarillas_propias_10min": conteos[0], "rojas_propias": conteos[1]}


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
    for registro in reglas:
        try:
            regla = Regla.model_validate(registro)
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
        cooldown = {regla.id: regla.cooldown_s for regla in reglas}
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


async def listar_recomendaciones(
    db: AsyncSession, usuario: UsuarioActual, partido_id: int, solo_activas: bool
) -> list[Recomendacion]:
    verificar_pertenencia(await db.get(Partido, partido_id), usuario)
    r = models.Recomendacion
    stmt = select(r).where(r.partido_id == partido_id).order_by(r.t.desc(), r.id.desc())
    if solo_activas:
        ids_activas = select(models.ReglaTactica.id).where(models.ReglaTactica.activa.is_(True))
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
