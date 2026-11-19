"""CU-49: reglas del catálogo y generación desde la ingesta real del backend."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from escenarios_analisis import BASE_LOCAL, BASE_VISITANTE, mensaje, punto
from partidos_prueba import (
    CLUB_A,
    CLUB_B,
    PARTIDO_A,
    PARTIDO_B,
    SesionesPrueba,
    sembrar_partidos,
)
from sqlalchemy import select
from starlette.testclient import TestClient

from app.analisis.motor.motor import ContextoPartido, MotorPartido
from app.analisis.vivo import AnalisisEnVivo, reiniciar_analisis_en_vivo
from app.asistencia import models, service
from app.asistencia.contexto import EstadoTactico
from app.asistencia.motor import ReglaInvalida, evaluar_regla
from app.asistencia.push import MensajePush, ResultadoPush
from app.asistencia.schemas import Regla
from app.core.deps import UsuarioActual
from app.core.security import token_acceso, token_ingesta
from app.deportivo.models import Partido, Posicion
from app.main import app
from app.partido.models import EventoManual, RelojPartido
from app.partido.service import (
    AnalisisDelProceso,
    PartidosEnTabla,
    PosicionesEnLote,
    limpiar_memoria_tracks,
    obtener_almacen_posiciones,
    obtener_repositorio_partidos,
)

CATALOGO = json.loads((
    Path(__file__).parents[1] / "alembic/versions/c4b7f29a6d10_reglas_iniciales.json"
).read_text(encoding="utf-8"))
CASOS = {
    "Bloque defensivo bajo": ({"minuto": 10, "altura_linea_m": 19}, "altura_linea_m", 25),
    "Ataque con poca amplitud": (
        {"minuto": 10, "amplitud_propia_m": 20, "posesion_propia_pct": 60}, "posesion_propia_pct", 40,
    ),
    "Bloque muy disperso": ({"minuto": 10, "compacidad_propia_m": 32}, "compacidad_propia_m", 21),
    "Baja posesión propia": ({"minuto": 10, "posesion_propia_pct": 21}, "posesion_propia_pct", 42),
    "Baja precisión de pase": (
        {"minuto": 10, "pases_intentados_propios": 6, "precision_pase_propio_pct": 50},
        "pases_intentados_propios", 4,
    ),
    "Posesión con poca circulación": (
        {"minuto": 10, "posesion_propia_pct": 70, "pases_intentados_propios": 2}, "pases_intentados_propios", 3,
    ),
    "Circulación rival sostenida": (
        {"minuto": 10, "posesion_rival_pct": 70, "pases_completados_rival": 7}, "pases_completados_rival", 5,
    ),
    "Presión adelantada con posesión rival": (
        {"minuto": 10, "altura_linea_m": 48, "posesion_rival_pct": 65}, "altura_linea_m", 45,
    ),
    "Carga reciente elevada": ({"minuto": 30, "ritmo_propio_m_min": 135}, "ritmo_propio_m_min", 124),
    "Descenso reciente del ritmo": ({"minuto": 65, "caida_ritmo_propio_pct": 31}, "caida_ritmo_propio_pct", 21),
    "Amonestaciones recientes": ({"amarillas_propias_10min": 2}, "amarillas_propias_10min", 1),
    "Reorganización tras una expulsión": ({"rojas_propias": 1}, "rojas_propias", 0),
}


@pytest.mark.parametrize("semilla", CATALOGO, ids=lambda r: r["nombre"])
def test_cada_regla_del_catalogo(semilla):
    regla = Regla(id=1, **semilla)
    valores, campo, valor_que_no_dispara = CASOS[regla.nombre]
    disparo = evaluar_regla(regla, valores)
    assert disparo is not None and disparo.mensaje and disparo.justificacion
    assert "{" not in disparo.justificacion
    assert any(d.metrica == campo and d.valor == valores[campo] for d in disparo.datos_soporte)
    assert evaluar_regla(regla, {**valores, campo: valor_que_no_dispara}) is None
    assert evaluar_regla(regla, {k: v for k, v in valores.items() if k != campo}) is None


def test_condiciones_y_plantillas_configurables():
    regla = Regla(id=1, nombre="Prueba", condicion={"o": [
        {">=": ["minuto", 1]}, {"<": ["dato_de_vision", 20]},
    ]}, plantilla_mensaje="Revisa la posición", plantilla_justificacion="Media {dato_de_vision:.1f}")
    assert evaluar_regla(regla, {"minuto": 5, "dato_de_vision": 22}) is not None
    assert evaluar_regla(regla, {"minuto": 5}) is None
    assert evaluar_regla(regla, {"minuto": 5, "dato_de_vision": float("nan")}) is None
    with pytest.raises(ReglaInvalida):
        evaluar_regla(regla.model_copy(update={"plantilla_justificacion": "{minuto.__class__}"}),
                     {"minuto": 5, "dato_de_vision": 22})


def _auth(club: int = CLUB_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_acceso(1, club, 'DT')}"}


def _datos(t: float, degradado: bool = False):
    jugadores = [punto(i, "LOCAL", x * 0.65, y) for i, (x, y) in enumerate(BASE_LOCAL, 1)]
    jugadores += [punto(i, "VISITANTE", x, y) for i, (x, y) in enumerate(BASE_VISITANTE, 12)]
    datos = mensaje(PARTIDO_A, t, jugadores, (63, 28))
    datos.calidad.calibracion_valida = not degradado
    datos.calidad.degradado = degradado
    return datos


def test_ritmo_colectivo_requiere_datos_y_descarta_una_ventana_degradada():
    motor = MotorPartido(ContextoPartido(PARTIDO_A))
    tactica = EstadoTactico()
    nombre_reglas = {s["nombre"]: Regla(id=i, **s) for i, s in enumerate(CATALOGO, 1)}
    carga = nombre_reglas["Carga reciente elevada"]
    descenso = nombre_reglas["Descenso reciente del ritmo"]
    for n in range(401):
        desde = n / 5
        # Todos los tracks se desplazan lateralmente. El ritmo baja a los 45 s.
        distancia = 3 * min(desde, 45) + 0.5 * max(0, desde - 45)
        avance = 15 - abs(distancia % 30 - 15)
        datos = _datos(3600 + desde)
        for j in datos.jugadores:
            if j.equipo == "LOCAL":
                j.x += avance
        tactica.observar(datos, motor)
        if n == 200:
            metricas = {"minuto": 60, **tactica.metricas()}
            assert evaluar_regla(carga, metricas) is not None
            assert evaluar_regla(descenso, metricas) is None
    assert evaluar_regla(descenso, {"minuto": 61, **tactica.metricas()}) is not None
    tactica.observar(_datos(3680.2, degradado=True), motor)
    tactica.observar(_datos(3680.4), motor)
    assert tactica.metricas() == {}


@pytest.fixture
async def partido_con_reglas(monkeypatch):
    await sembrar_partidos()
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        partido = await db.get(Partido, PARTIDO_A)
        partido.es_local = True
        partido.ataca_hacia = "DER"
        db.add(RelojPartido(club_id=CLUB_A, partido_id=PARTIDO_A, parte=1,
                           en_curso=True, inicio_utc=ahora))
        db.add_all(models.ReglaTactica(**regla) for regla in CATALOGO)
        db.add_all(models.ReglaTactica(
            club_id=club, nombre=nombre, condicion={">=": ["rojas_propias", 1]},
            plantilla_mensaje=nombre, prioridad="MEDIA", cooldown_s=30, activa=activa,
        ) for club, nombre, activa in (
            (CLUB_A, "Regla propia", True), (CLUB_A, "Regla inactiva", False),
            (CLUB_B, "Regla ajena", True),
        ))
        for i, (tipo, equipo, anulado) in enumerate((
            ("ROJA", "LOCAL", False), ("AMARILLA", "LOCAL", False),
            ("AMARILLA", "LOCAL", True), ("AMARILLA", "VISITANTE", False),
        )):
            db.add(EventoManual(club_id=CLUB_A, partido_id=PARTIDO_A, uuid=str(i), tipo=tipo,
                                equipo=equipo, minuto=5, capturado_en=ahora, creado_por_id=1,
                                anulado_en=ahora if anulado else None))
        await db.commit()

    almacen = PosicionesEnLote(Posicion, SesionesPrueba, analisis=AnalisisDelProceso())
    monkeypatch.setitem(app.dependency_overrides, obtener_almacen_posiciones, lambda: almacen)
    monkeypatch.setitem(app.dependency_overrides, obtener_repositorio_partidos,
                        lambda: PartidosEnTabla(Partido, SesionesPrueba))
    limpiar_memoria_tracks()
    reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba))
    yield almacen
    await almacen.vaciar()
    reiniciar_analisis_en_vivo()
    limpiar_memoria_tracks()


def _jugar(cliente, muestras):
    with cliente.websocket_connect(f"/api/partido/{PARTIDO_A}/ingesta") as ws:
        ws.send_json({"tipo": "auth", "token": token_ingesta(CLUB_A, PARTIDO_A)})
        assert ws.receive_json()["tipo"] == "listo"
        for m in muestras:
            ws.send_json(m.model_dump(mode="json"))
        # El error del siguiente mensaje confirma que la ingesta procesó los anteriores.
        ws.send_json({})
        assert ws.receive_json()["tipo"] == "error"


def test_ingesta_calidad_cooldown_clubes_y_consulta(partido_con_reglas):
    url = f"/api/asistencia/partidos/{PARTIDO_A}/recomendaciones"
    with TestClient(app) as cliente:
        activos = cliente.get("/api/asistencia/reglas?activas=true", headers=_auth()).json()
        reglas = {r["id"]: r["nombre"] for r in activos}
        assert len(activos) == len(CATALOGO) + 1
        assert "Regla propia" in reglas.values() and "Regla ajena" not in reglas.values()
        assert "Regla inactiva" not in reglas.values()

        # Un lote diferido pasa por el almacén y calcula métricas, sin disparar reglas en vivo.
        cliente.portal.call(partido_con_reglas.agregar, _datos(300))
        assert cliente.get(url, headers=_auth()).json() == []

        _jugar(cliente, (_datos(t, degradado=True) for t in range(301, 338)))
        disciplinarias = cliente.get(url + "?solo_activas=false", headers=_auth()).json()
        assert [reglas[r["regla_id"]] for r in disciplinarias] == [
            "Regla propia", "Regla propia", "Reorganización tras una expulsión",
        ]

        _jugar(cliente, (_datos(t) for t in range(338, 378)))
        historico = cliente.get(url + "?solo_activas=false", headers=_auth()).json()
        assert any(reglas[r["regla_id"]] == "Bloque defensivo bajo" for r in historico)
        assert any(reglas[r["regla_id"]] == "Baja posesión propia" for r in historico)
        visibles = cliente.get(url, headers=_auth()).json()
        assert len(visibles) == 3 and visibles[0]["prioridad"] == "CRITICA"
        assert len({r["regla_id"] for r in visibles}) == 3
        assert cliente.get(url, headers=_auth(CLUB_B)).status_code == 404

        reiniciar_analisis_en_vivo(AnalisisEnVivo(sesiones=SesionesPrueba))
        _jugar(cliente, (_datos(t) for t in range(378, 419)))
        despues = cliente.get(url + "?solo_activas=false", headers=_auth()).json()
        propia = next(id_regla for id_regla, nombre in reglas.items() if nombre == "Regla propia")
        assert [r for r in despues if r["regla_id"] != propia] == [
            r for r in historico if r["regla_id"] != propia
        ]


def _regla_prueba(
    nombre: str,
    prioridad: str = "MEDIA",
    cooldown_s: int = 30,
    club_id: int | None = None,
) -> models.ReglaTactica:
    return models.ReglaTactica(
        club_id=club_id,
        nombre=nombre,
        condicion={">=": ["senal", 1]},
        plantilla_mensaje=nombre,
        plantilla_justificacion="Senal {senal:.0f}",
        prioridad=prioridad,
        cooldown_s=cooldown_s,
        activa=True,
    )


async def _preparar_partidos_para_evaluar(*reglas: models.ReglaTactica) -> None:
    await sembrar_partidos()
    ahora = datetime.now(UTC)
    async with SesionesPrueba() as db:
        for partido_id, club_id in ((PARTIDO_A, CLUB_A), (PARTIDO_B, CLUB_B)):
            partido = await db.get(Partido, partido_id)
            assert partido is not None
            partido.es_local = True
            partido.ataca_hacia = "DER"
            db.add(
                RelojPartido(
                    club_id=club_id,
                    partido_id=partido_id,
                    parte=1,
                    en_curso=True,
                    inicio_utc=ahora,
                )
            )
        db.add_all(reglas)
        await db.commit()


async def _evaluar(partido_id: int, club_id: int, t: float) -> bool:
    async with SesionesPrueba() as db:
        return await service.evaluar_en_vivo(db, partido_id, club_id, t, {"senal": 1})


@pytest.mark.asyncio
async def test_cooldown_en_limite_y_aislado_por_regla_partido_y_club():
    await _preparar_partidos_para_evaluar(
        _regla_prueba("Global 30", cooldown_s=30),
        _regla_prueba("Global 60", cooldown_s=60),
        _regla_prueba("Solo A", club_id=CLUB_A),
        _regla_prueba("Solo B", club_id=CLUB_B),
    )

    assert await _evaluar(PARTIDO_A, CLUB_A, 100)
    assert await _evaluar(PARTIDO_A, CLUB_A, 129.999)
    assert await _evaluar(PARTIDO_A, CLUB_A, 130)
    assert await _evaluar(PARTIDO_B, CLUB_B, 105)

    async with SesionesPrueba() as db:
        filas = (
            await db.execute(
                select(
                    models.Recomendacion.partido_id,
                    models.ReglaTactica.nombre,
                    models.Recomendacion.t,
                )
                .join(models.ReglaTactica)
                .order_by(
                    models.Recomendacion.partido_id,
                    models.ReglaTactica.nombre,
                    models.Recomendacion.t,
                )
            )
        ).all()

    assert filas == [
        (PARTIDO_A, "Global 30", 100),
        (PARTIDO_A, "Global 30", 130),
        (PARTIDO_A, "Global 60", 100),
        (PARTIDO_A, "Solo A", 100),
        (PARTIDO_A, "Solo A", 130),
        (PARTIDO_B, "Global 30", 105),
        (PARTIDO_B, "Global 60", 105),
        (PARTIDO_B, "Solo B", 105),
    ]


@pytest.mark.asyncio
async def test_evaluaciones_concurrentes_no_duplican_recomendaciones():
    await _preparar_partidos_para_evaluar(_regla_prueba("Concurrente"))

    assert all(
        await asyncio.gather(*(_evaluar(PARTIDO_A, CLUB_A, 100) for _ in range(4)))
    )

    async with SesionesPrueba() as db:
        recomendaciones = list((await db.scalars(select(models.Recomendacion))).all())
    assert len(recomendaciones) == 1


@pytest.mark.asyncio
async def test_prioridad_limite_tres_desempate_e_historial_completo():
    await sembrar_partidos()
    reglas = [
        _regla_prueba("Critica antigua", "CRITICA"),
        _regla_prueba("Critica reciente", "CRITICA"),
        _regla_prueba("Alta", "ALTA"),
        _regla_prueba("Media", "MEDIA"),
        _regla_prueba("Baja", "BAJA"),
    ]
    async with SesionesPrueba() as db:
        db.add_all(reglas)
        await db.flush()
        tiempos = (10, 20, 30, 40, 50)
        db.add_all(
            models.Recomendacion(
                partido_id=PARTIDO_A,
                regla_id=regla.id,
                t=t,
                minuto=int(t // 60),
                mensaje=regla.nombre,
                justificacion="Prueba",
                prioridad=regla.prioridad,
                datos_soporte=[],
            )
            for regla, t in zip(reglas, tiempos, strict=True)
        )
        # La consulta activa conserva solo la ultima instancia de cada regla,
        # mientras que el historial mantiene tambien esta instancia anterior.
        db.add(
            models.Recomendacion(
                partido_id=PARTIDO_A,
                regla_id=reglas[2].id,
                t=5,
                minuto=0,
                mensaje="Alta anterior",
                justificacion="Prueba",
                prioridad="ALTA",
                datos_soporte=[],
            )
        )
        await db.commit()

        usuario = UsuarioActual(id=1, club_id=CLUB_A, rol="DT")
        activas = await service.listar_recomendaciones(db, usuario, PARTIDO_A, True)
        historico = await service.listar_recomendaciones(db, usuario, PARTIDO_A, False)

    assert [r.mensaje for r in activas] == ["Critica reciente", "Critica antigua", "Alta"]
    assert [r.prioridad.value for r in activas] == ["CRITICA", "CRITICA", "ALTA"]
    assert len(activas) == 3
    assert len(historico) == 6
    assert {r.mensaje for r in historico} == {
        "Critica antigua",
        "Critica reciente",
        "Alta",
        "Alta anterior",
        "Media",
        "Baja",
    }


class ProveedorPushPrueba:
    def __init__(
        self,
        resultados: list[ResultadoPush] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.resultados = resultados
        self.error = error
        self.llamadas: list[tuple[list[str], MensajePush]] = []

    async def enviar(
        self, tokens: list[str], mensaje_push: MensajePush
    ) -> list[ResultadoPush]:
        self.llamadas.append((tokens, mensaje_push))
        if self.error is not None:
            raise self.error
        return self.resultados or [
            ResultadoPush(enviado=True, proveedor_id=f"fcm-{i}")
            for i in range(len(tokens))
        ]


@pytest.fixture
async def usuarios_para_push():
    await sembrar_partidos()


def test_registro_dispositivo_autenticado_idempotente_y_actualizable(usuarios_para_push):
    url = "/api/asistencia/dispositivos"
    inicial = {
        "instalacion_id": "instalacion-android-1",
        "token": "token-fcm-inicial-123456",
        "plataforma": "ANDROID",
    }
    actualizado = {**inicial, "token": "token-fcm-actualizado-789"}

    async def dispositivos():
        async with SesionesPrueba() as db:
            return list((await db.scalars(select(models.DispositivoPush))).all())

    with TestClient(app) as cliente:
        assert cliente.post(url, json=inicial).status_code == 401
        assert cliente.post(
            url,
            headers=_auth(),
            json={**inicial, "usuario_id": CLUB_B},
        ).status_code == 422
        assert cliente.post(url, headers=_auth(), json=inicial).status_code == 204
        assert cliente.post(url, headers=_auth(), json=inicial).status_code == 204
        assert cliente.post(url, headers=_auth(), json=actualizado).status_code == 204
        filas = cliente.portal.call(dispositivos)

    assert len(filas) == 1
    assert filas[0].usuario_id == CLUB_A
    assert filas[0].club_id == CLUB_A
    assert filas[0].token == actualizado["token"]
    assert filas[0].activo


@pytest.mark.asyncio
async def test_solo_critica_notifica_al_club_correcto_sin_duplicar_y_con_navegacion():
    await _preparar_partidos_para_evaluar(
        _regla_prueba("Urgente", "CRITICA"),
        _regla_prueba("Ordinaria", "MEDIA"),
    )
    async with SesionesPrueba() as db:
        db.add_all([
            models.DispositivoPush(
                club_id=CLUB_A,
                usuario_id=CLUB_A,
                instalacion_id="instalacion-club-a",
                token="token-club-a-123456789",
                plataforma="ANDROID",
            ),
            models.DispositivoPush(
                club_id=CLUB_B,
                usuario_id=CLUB_B,
                instalacion_id="instalacion-club-b",
                token="token-club-b-123456789",
                plataforma="ANDROID",
            ),
        ])
        await db.commit()

    proveedor = ProveedorPushPrueba()
    async with SesionesPrueba() as db:
        assert await service.evaluar_en_vivo(
            db,
            PARTIDO_A,
            CLUB_A,
            100,
            {"senal": 1},
            proveedor,
        )
        recomendaciones = list((await db.scalars(
            select(models.Recomendacion).order_by(models.Recomendacion.id)
        )).all())
        assert await service.notificar_recomendaciones(
            db, [r.id for r in recomendaciones], proveedor
        ) == 0
        envios = list((await db.scalars(select(models.EnvioPush))).all())

    assert len(recomendaciones) == 2
    assert len(envios) == 1
    assert envios[0].estado == "ENVIADO"
    assert len(proveedor.llamadas) == 1
    tokens, mensaje_push = proveedor.llamadas[0]
    critica = next(r for r in recomendaciones if r.prioridad == "CRITICA")
    assert tokens == ["token-club-a-123456789"]
    assert mensaje_push.datos == {
        "tipo": "recomendacion_tactica",
        "recomendacion_id": str(critica.id),
        "partido_id": str(PARTIDO_A),
        "prioridad": "CRITICA",
        "ruta": (
            f"/asistencia?partido_id={PARTIDO_A}"
            f"&recomendacion_id={critica.id}"
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proveedor", "token_activo", "error_esperado"),
    [
        (
            ProveedorPushPrueba([
                ResultadoPush(
                    enviado=False,
                    error="Token no registrado",
                    token_invalido=True,
                )
            ]),
            False,
            "Token no registrado",
        ),
        (ProveedorPushPrueba(error=RuntimeError("FCM no disponible")), True, "FCM no disponible"),
    ],
    ids=("token-invalido", "error-proveedor"),
)
async def test_error_push_se_registra_y_solo_invalida_el_token_correspondiente(
    proveedor: ProveedorPushPrueba,
    token_activo: bool,
    error_esperado: str,
):
    await _preparar_partidos_para_evaluar(_regla_prueba("Urgente", "CRITICA"))
    async with SesionesPrueba() as db:
        db.add(models.DispositivoPush(
            club_id=CLUB_A,
            usuario_id=CLUB_A,
            instalacion_id="instalacion-error",
            token="token-error-123456789",
            plataforma="ANDROID",
        ))
        await db.commit()
        assert await service.evaluar_en_vivo(
            db,
            PARTIDO_A,
            CLUB_A,
            100,
            {"senal": 1},
            proveedor,
        )
        dispositivo = await db.scalar(select(models.DispositivoPush))
        envio = await db.scalar(select(models.EnvioPush))

    assert dispositivo is not None and dispositivo.activo is token_activo
    assert envio is not None and envio.estado == "ERROR"
    assert error_esperado in (envio.error or "")


@pytest.mark.asyncio
async def test_notificacion_concurrente_se_envia_una_sola_vez():
    await _preparar_partidos_para_evaluar(_regla_prueba("Urgente", "CRITICA"))
    async with SesionesPrueba() as db:
        regla_id = await db.scalar(select(models.ReglaTactica.id))
        assert regla_id is not None
        recomendacion = models.Recomendacion(
            partido_id=PARTIDO_A,
            regla_id=regla_id,
            t=100,
            minuto=1,
            mensaje="Urgente",
            justificacion="Prueba",
            prioridad="CRITICA",
            datos_soporte=[],
        )
        db.add_all([
            recomendacion,
            models.DispositivoPush(
                club_id=CLUB_A,
                usuario_id=CLUB_A,
                instalacion_id="instalacion-concurrente",
                token="token-concurrente-123456789",
                plataforma="ANDROID",
            ),
        ])
        await db.commit()
        recomendacion_id = recomendacion.id

    proveedor = ProveedorPushPrueba()

    async def notificar() -> int:
        async with SesionesPrueba() as db:
            return await service.notificar_recomendaciones(
                db, [recomendacion_id], proveedor
            )

    resultados = await asyncio.gather(notificar(), notificar(), notificar())
    async with SesionesPrueba() as db:
        envios = list((await db.scalars(select(models.EnvioPush))).all())

    assert sum(resultados) == 1
    assert len(proveedor.llamadas) == 1
    assert len(envios) == 1
