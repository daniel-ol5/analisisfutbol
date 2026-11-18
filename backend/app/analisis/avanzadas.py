"""Línea de tiempo y red de pases  —  T-103 (CU-47, CU-48).

Los pases salen del mismo motor que las métricas (`MotorPartido.pases`) y de ellos
salen los eventos de la tabla `evento_derivado` (ver `eventos.py`). Así lo que muestra
la línea de tiempo coincide con los pases intentados/completados de CU-42. La red de
pases (CU-48) usa los pases del motor: en vivo, el motor en memoria; si no, pasar por
el motor las filas de `posicion` (igual que el recálculo de CU-46).

Línea de tiempo (CU-47), dos orígenes distintos que no se mezclan:
- CAMARA: lo inferido, leído de `evento_derivado` (en vivo, del motor en memoria). Un
  pase completado es PASE; uno que cae en un rival es PERDIDA del que pasó y
  RECUPERACION del rival.
- MANUAL: lo cargado por el cuerpo técnico (gol, tarjetas, sustituciones),
  sin los anulados. Solo tienen minuto: se ubican en `minuto * 60`.

Red de pases (CU-48): solo pases COMPLETADOS entre jugadores con track asignado
(CU-34/35). Un track sin jugador no aparece, como en CU-43. Cada jugador asignado que
estuvo a la vista en el rango es un nodo, tenga o no pases: va en su posición media
(`MotorPartido.posiciones`), con pases enviados y recibidos. Se marcan los que más
reciben (`mayor_recepcion`) y los desconectados del circuito (`aislado`).
"""

from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analisis import eventos, persistencia
from app.analisis.eventos import EventoCamara
from app.analisis.eventos import jugador_en as _jugador_en
from app.analisis.eventos import tramos_por_track as _tramos_por_track
from app.analisis.metricas import (
    _jugadores,
    _lado,
    motor_desde_tabla,
    motor_en_vivo,
    partido_del_club,
)
from app.analisis.motor.bloque import direccion_de
from app.analisis.motor.motor import MotorPartido
from app.analisis.parametros import PARAMETROS
from app.analisis.schemas import (
    AristaPase,
    ItemLineaTiempo,
    LineaTiempo,
    NodoPase,
    RedPases,
    TipoEventoDerivado,
)
from app.core.deps import UsuarioActual
from app.deportivo.models import Jugador, Partido
from app.partido import service as partido_service
from app.partido.models import AsignacionTrack
from app.partido.schemas import Lado, TipoEventoManual
from app.partido.service import normalizar_coordenadas

TIPOS_DERIVADOS = {t.value for t in TipoEventoDerivado}
TIPOS_LINEA_TIEMPO = TIPOS_DERIVADOS | {t.value for t in TipoEventoManual}


async def _motor(db: AsyncSession, partido: Partido) -> MotorPartido:
    motor = motor_en_vivo(partido.id)
    return motor if motor is not None else await motor_desde_tabla(db, partido)


def _nombre(j: Jugador | None, track_id: int) -> str:
    return f"{j.nombre} {j.apellido}" if j else f"#{track_id}"


def _tipo(tipo: str | None) -> str | None:
    if tipo is None:
        return None
    valor = tipo.upper()
    if valor not in TIPOS_LINEA_TIEMPO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"tipo debe ser uno de: {', '.join(sorted(TIPOS_LINEA_TIEMPO))}")
    return valor


# ---------------- CU-47 · Línea de tiempo ----------------


async def _eventos_camara(db: AsyncSession, partido: Partido) -> list[EventoCamara]:
    """Los eventos de cámara del partido.

    En juego: los del motor en memoria (la tabla solo tiene lo ya cerrado). Si no, los de
    `evento_derivado`. Un partido de antes de que existiera la tabla no tiene filas: se
    derivan de sus posiciones, como hace el recálculo.
    """
    vivo = motor_en_vivo(partido.id)
    if vivo is not None:
        return eventos.de_pases(vivo.pases)
    guardados = await eventos.leer(db, partido.id)
    if guardados:
        return guardados
    return eventos.de_pases((await motor_desde_tabla(db, partido)).pases)


def _item_de_evento(e: EventoCamara, origen_id: int | None, destino_id: int | None,
                    nombres: dict[int, str]) -> ItemLineaTiempo:
    """Un evento de `evento_derivado` como ítem de la línea de tiempo (origen CAMARA)."""
    def quien(jugador_id: int | None, track_id: int | None) -> str:
        return (nombres.get(jugador_id) if jugador_id is not None else None) or f"#{track_id}"

    origen, destino = quien(origen_id, e.track_origen), quien(destino_id, e.track_destino)
    if e.tipo == TipoEventoDerivado.PASE.value:
        texto = f"Pase de {origen} a {destino}"
    elif e.tipo == TipoEventoDerivado.PERDIDA.value:
        texto = f"Pérdida de {origen}: el balón llegó a {destino} (rival)"
    elif e.tipo == TipoEventoDerivado.RECUPERACION.value:
        texto = f"Recuperación de {origen}"
    else:
        texto = f"{e.tipo.capitalize()} de {origen}"
    return ItemLineaTiempo(
        t=e.t, minuto=e.minuto, tipo=e.tipo, equipo=Lado(e.equipo), jugador_id=origen_id,
        descripcion=texto, origen=eventos.CAMARA)


def _item_manual(e, nombres: dict[int, str]) -> ItemLineaTiempo:
    quien = nombres.get(e.jugador_id) if e.jugador_id else None
    if e.tipo == TipoEventoManual.SUSTITUCION.value:
        entra = nombres.get(e.jugador_entra_id) if e.jugador_entra_id else None
        texto = f"Sustitución: sale {quien or '—'}, entra {entra or '—'}"
    else:
        texto = e.tipo.capitalize() + (f" de {quien}" if quien else "")
        if e.convertida_en_roja:
            texto += " (segunda amarilla)"
    return ItemLineaTiempo(
        # Con segundo exacto (minuto tomado del cronómetro) el plano 2D salta a esa jugada;
        # si solo se indicó el minuto, al inicio de ese minuto.
        t=float(e.segundo if e.segundo is not None else e.minuto * 60),
        minuto=e.minuto, tipo=e.tipo, equipo=Lado(e.equipo),
        jugador_id=e.jugador_id, descripcion=texto, origen="MANUAL")


async def linea_tiempo(db: AsyncSession, usuario: UsuarioActual, partido_id: int,
                       tipo: str | None, equipo: str | None) -> LineaTiempo:
    """CU-47: cronología ordenada por tiempo, con filtros por tipo y equipo."""
    tipo_f, lado = _tipo(tipo), _lado(equipo)
    partido = await partido_del_club(db, usuario, partido_id)
    manuales = await partido_service.listar_eventos_manuales(db, usuario, partido.id)
    if tipo_f is not None and tipo_f not in TIPOS_DERIVADOS:
        manuales = [e for e in manuales if e.tipo == tipo_f]

    de_camara: list[EventoCamara] = []
    tramos: dict[int, list[AsignacionTrack]] = {}
    if tipo_f is None or tipo_f in TIPOS_DERIVADOS:
        de_camara = await _eventos_camara(db, partido)
        tramos = _tramos_por_track(await persistencia.tramos_de(db, partido))

    # El jugador se resuelve por track con las asignaciones de hoy: una reasignación
    # posterior a haber guardado los eventos se refleja igual.
    por_evento = [(_jugador_en(tramos, e.track_origen, e.t), _jugador_en(tramos, e.track_destino, e.t))
                  for e in de_camara]
    ids = {e.jugador_id for e in manuales if e.jugador_id} \
        | {e.jugador_entra_id for e in manuales if e.jugador_entra_id} \
        | {j for par in por_evento for j in par if j is not None}
    fichas = await _jugadores(db, ids, partido)
    nombres = {jid: f"{j.nombre} {j.apellido}" for jid, j in fichas.items()}

    items: list[ItemLineaTiempo] = [
        _item_de_evento(e, origen, destino, nombres)
        for e, (origen, destino) in zip(de_camara, por_evento, strict=True)]
    items += [_item_manual(e, nombres) for e in manuales]

    if tipo_f is not None:
        items = [i for i in items if i.tipo == tipo_f]
    if lado is not None:
        items = [i for i in items if i.equipo == lado]
    items.sort(key=lambda i: (i.t, i.origen != "MANUAL"))
    return LineaTiempo(partido_id=partido.id, items=items)


# ---------------- CU-48 · Red de pases ----------------


def _marcar_destacados(nodos: list[NodoPase], segundos: dict[int, float]) -> None:
    """Por equipo, marca a quienes más pases reciben y a los desconectados del circuito.

    `segundos` es el tiempo que cada jugador estuvo a la vista en el rango. Un jugador está
    aislado si su ritmo de pases (enviados + recibidos por segundo en cancha) es menos de
    `red_aislado_frac` del ritmo medio de su equipo; con menos de `red_min_presencia_s` de
    presencia no hay base para juzgarlo y no se marca.
    """
    for lado in (Lado.LOCAL, Lado.VISITANTE):
        equipo = [n for n in nodos if n.equipo == lado]
        recepciones = sorted((n.pases_recibidos for n in equipo if n.pases_recibidos > 0),
                             reverse=True)
        if recepciones:
            corte = recepciones[min(PARAMETROS.red_top_recepcion, len(recepciones)) - 1]
            for n in equipo:
                n.mayor_recepcion = n.pases_recibidos >= corte   # los empatados en el corte entran

        medibles = [n for n in equipo
                    if segundos.get(n.jugador_id, 0.0) >= PARAMETROS.red_min_presencia_s]
        tiempo = sum(segundos[n.jugador_id] for n in medibles)
        total = sum(n.pases + n.pases_recibidos for n in medibles)
        if tiempo <= 0 or total <= 0:
            continue   # nadie pasó: no hay circuito del que estar desconectado
        ritmo_equipo = total / tiempo
        for n in medibles:
            ritmo = (n.pases + n.pases_recibidos) / segundos[n.jugador_id]
            n.aislado = ritmo < PARAMETROS.red_aislado_frac * ritmo_equipo


async def red_pases(db: AsyncSession, usuario: UsuarioActual, partido_id: int,
                    desde_minuto: int, hasta_minuto: int, equipo: str | None) -> RedPases:
    """CU-48: grafo de pases completados entre jugadores, en minutos [desde, hasta] inclusive."""
    lado = _lado(equipo)
    if hasta_minuto < desde_minuto:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "hasta_minuto no puede ser menor que desde_minuto")
    partido = await partido_del_club(db, usuario, partido_id)
    motor = await _motor(db, partido)
    ctx = motor.contexto
    tramos = _tramos_por_track(await persistencia.tramos_de(db, partido))

    aristas: dict[tuple[int, int], int] = defaultdict(int)
    enviados: dict[int, int] = defaultdict(int)
    recibidos: dict[int, int] = defaultdict(int)
    puntos: dict[int, list[tuple[float, float]]] = defaultdict(list)
    equipo_de: dict[int, str] = {}

    for p in motor.pases:
        if not p.completado or not desde_minuto <= int(p.t // 60) <= hasta_minuto:
            continue
        if lado is not None and p.equipo != lado.value:
            continue
        origen = _jugador_en(tramos, p.origen_track, p.t)
        destino = _jugador_en(tramos, p.destino_track, p.t)
        if origen is None or destino is None or origen == destino:
            continue   # sin jugador asignado: no entra a la red
        parte = 1 if p.t < PARAMETROS.segundos_primer_tiempo else 2
        direccion = direccion_de(p.equipo, ctx.lado_propio, ctx.ataca_hacia)
        aristas[(origen, destino)] += 1
        enviados[origen] += 1
        recibidos[destino] += 1
        equipo_de[origen] = equipo_de[destino] = p.equipo
        for jugador, (x, y) in ((origen, p.origen_xy), (destino, p.destino_xy)):
            puntos[jugador].append(
                normalizar_coordenadas(x, y, ctx.largo_m, ctx.ancho_m, direccion, parte))

    # Posición media y tiempo en cancha de cada jugador asignado, también de los que no pasaron.
    presencia: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for (track_id, minuto), (sx, sy, n) in motor.posiciones.items():
        if not desde_minuto <= minuto <= hasta_minuto:
            continue
        del_equipo = motor.equipo_de(track_id)
        if del_equipo is None or (lado is not None and del_equipo != lado.value):
            continue
        jugador = _jugador_en(tramos, track_id, minuto * 60 + 30.0)
        if jugador is None:
            continue
        acum = presencia[jugador]
        acum[0] += sx
        acum[1] += sy
        acum[2] += n
        equipo_de.setdefault(jugador, del_equipo)

    ids = puntos.keys() | presencia.keys()
    fichas = await _jugadores(db, ids, partido)
    nodos = []
    for jid in ids:
        j = fichas.get(jid)
        sx, sy, n = presencia.get(jid, (0.0, 0.0, 0.0))   # `get`: no crea entradas en el defaultdict
        if n > 0:
            x_medio, y_medio = sx / n, sy / n
        else:   # sin posiciones propias: la del balón en sus pases
            pts = puntos[jid]
            x_medio = sum(x for x, _ in pts) / len(pts)
            y_medio = sum(y for _, y in pts) / len(pts)
        nodos.append(NodoPase(
            jugador_id=jid, nombre=_nombre(j, jid), dorsal=j.dorsal if j else None,
            equipo=Lado(equipo_de[jid]), x_medio=round(x_medio, 2), y_medio=round(y_medio, 2),
            pases=enviados.get(jid, 0), pases_recibidos=recibidos.get(jid, 0)))
    _marcar_destacados(nodos, {jid: acum[2] for jid, acum in presencia.items()})
    nodos.sort(key=lambda n: (-n.pases, n.jugador_id))
    return RedPases(
        partido_id=partido.id, desde_minuto=desde_minuto, hasta_minuto=hasta_minuto,
        nodos=nodos,
        aristas=[AristaPase(origen_id=o, destino_id=d, pases=n)
                 for (o, d), n in sorted(aristas.items(), key=lambda kv: (-kv[1], kv[0]))])
