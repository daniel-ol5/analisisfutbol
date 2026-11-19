"""Prepara y verifica el escenario reproducible de la demostración del Sprint 4.

Uso desde ``backend``::

    python -m scripts.demo_sprint4 verificar
    python -m scripts.demo_sprint4 preparar --duracion 12

La contraseña se lee de ``DEMO_ADMIN_PASSWORD``. ``preparar`` modifica solo
datos del club autenticado y, por seguridad, acepta únicamente una API local a
menos que se indique ``--permitir-host-remoto`` explícitamente.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from argparse import Namespace
from collections.abc import Iterable
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

from scripts.emisor_simulado import correr

EMAIL_DEMO = "admin@club-demo.example.com"
RIVAL_PRINCIPAL = "Club Rival Uno"
HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "10.0.2.2"}


class ErrorDemo(RuntimeError):
    """Error accionable al preparar o verificar la demostración."""


def calibracion_sintetica() -> dict:
    """Calibración exacta 1050 x 680 px -> 105 x 68 m para el emisor simulado.

    No representa una cámara física. Solo permite recorrer el flujo de software
    local sin afirmar precisión geométrica de cancha.
    """
    imagen = [
        (0, 0), (525, 0), (1050, 0), (1050, 340),
        (1050, 680), (525, 680), (0, 680), (0, 340),
    ]
    cancha = [(x / 10, y / 10) for x, y in imagen]
    return {
        "modo": "MANUAL",
        "referencia": {
            "tipo": "DIRECTO",
            "fuente_id": "demo-sprint4-simulada",
            "ancho_px": 1050,
            "alto_px": 680,
        },
        "puntos_imagen": [{"x": x, "y": y} for x, y in imagen],
        "puntos_cancha": [{"x": x, "y": y} for x, y in cancha],
        "largo_m": 105,
        "ancho_m": 68,
    }


def validar_destino_mutable(api_url: str, permitir_host_remoto: bool) -> None:
    """Impide que el preparador escriba por accidente sobre una API remota."""
    host = urlparse(api_url).hostname
    if host not in HOSTS_LOCALES and not permitir_host_remoto:
        raise ErrorDemo(
            f"Se rechazó preparar datos en el host remoto {host!r}. "
            "Usa una API local o agrega --permitir-host-remoto tras verificar el entorno."
        )


def ordenar_candidatos(partidos: Iterable[dict], partido_id: int | None = None) -> list[dict]:
    """Prioriza el partido demo en curso y luego el programado con alineación esperada."""
    candidatos = list(partidos)
    if partido_id is not None:
        return [p for p in candidatos if p.get("id") == partido_id]

    estados = {"EN_CURSO": 0, "PROGRAMADO": 1}
    candidatos = [p for p in candidatos if p.get("estado") in estados]
    return sorted(
        candidatos,
        key=lambda p: (
            estados[p["estado"]],
            0 if p.get("rival") == RIVAL_PRINCIPAL else 1,
            p.get("fecha_hora", ""),
            p.get("id", 0),
        ),
    )


def _detalle(respuesta: httpx.Response) -> str:
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return respuesta.text.strip() or "respuesta vacía"
    if isinstance(cuerpo, dict) and "detail" in cuerpo:
        return str(cuerpo["detail"])
    return str(cuerpo)


def _exigir(
    respuesta: httpx.Response,
    esperados: int | set[int],
    paso: str,
) -> httpx.Response:
    codigos = {esperados} if isinstance(esperados, int) else esperados
    if respuesta.status_code not in codigos:
        raise ErrorDemo(
            f"{paso}: HTTP {respuesta.status_code} · {_detalle(respuesta)}"
        )
    return respuesta


def _ok(nombre: str, detalle: str = "") -> None:
    sufijo = f" · {detalle}" if detalle else ""
    print(f"[OK] {nombre}{sufijo}")


def _aviso(nombre: str, detalle: str) -> None:
    print(f"[AVISO] {nombre} · {detalle}")


def iniciar_sesion(http: httpx.Client, email: str, password: str) -> dict[str, str]:
    respuesta = _exigir(
        http.post("/seguridad/login", json={"email": email, "password": password}),
        200,
        "Inicio de sesión",
    )
    _ok("Inicio de sesión", email)
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def seleccionar_partido(
    http: httpx.Client,
    headers: dict[str, str],
    partidos: list[dict],
    partido_id: int | None,
) -> tuple[dict, dict]:
    candidatos = ordenar_candidatos(partidos, partido_id)
    if not candidatos:
        solicitado = f" con id {partido_id}" if partido_id is not None else ""
        raise ErrorDemo(f"No hay un partido PROGRAMADO o EN_CURSO{solicitado}")

    for partido in candidatos:
        respuesta = http.get(
            f"/deportivo/partidos/{partido['id']}/alineacion", headers=headers
        )
        if respuesta.status_code == 200:
            return partido, respuesta.json()
        if partido_id is not None:
            raise ErrorDemo(
                f"El partido {partido_id} no tiene una alineación lista: {_detalle(respuesta)}"
            )
    raise ErrorDemo("No hay un partido PROGRAMADO o EN_CURSO con alineación guardada")


def contexto_basico(
    http: httpx.Client,
    email: str,
    password: str,
    partido_id: int | None,
) -> tuple[dict[str, str], dict, dict]:
    salud = _exigir(http.get("/salud"), 200, "Salud de la API").json()
    _ok("API disponible", salud.get("version", "sin versión"))
    headers = iniciar_sesion(http, email, password)

    equipos = _exigir(
        http.get("/deportivo/equipos", headers=headers), 200, "Consulta de equipos"
    ).json()
    competiciones = _exigir(
        http.get("/deportivo/competiciones", headers=headers),
        200,
        "Consulta de competiciones",
    ).json()
    partidos = _exigir(
        http.get("/deportivo/partidos", headers=headers), 200, "Agenda de partidos"
    ).json()
    if not equipos or not partidos:
        raise ErrorDemo("El seed no creó equipos y partidos; reinicia la API y revisa sus logs")
    _ok("Gestión deportiva", f"{len(equipos)} equipo(s), {len(partidos)} partido(s)")
    if competiciones:
        _ok("Competiciones", f"{len(competiciones)} disponible(s)")
    else:
        _aviso("Competiciones", "no hay competiciones; vuelve a ejecutar el seed actualizado")

    partido, alineacion = seleccionar_partido(http, headers, partidos, partido_id)
    titulares = sum(1 for jugador in alineacion.get("jugadores", []) if jugador.get("es_titular"))
    _ok(
        "Partido demostrable",
        f"#{partido['id']} vs. {partido['rival']} · {partido['estado']} · {titulares} titulares",
    )
    return headers, partido, alineacion


def asegurar_calibracion(
    http: httpx.Client, headers: dict[str, str], partido_id: int
) -> dict:
    ruta = f"/vision/partidos/{partido_id}/calibracion"
    actual = http.get(ruta, headers=headers)
    if actual.status_code == 200:
        datos = actual.json()
        if datos.get("valida") and datos.get("modo") == "MANUAL":
            _ok("Calibración", "ya era válida")
            return datos
    elif actual.status_code != 404:
        _exigir(actual, 200, "Consulta de calibración")

    guardada = _exigir(
        http.post(ruta, headers=headers, json=calibracion_sintetica()),
        {200, 201},
        "Preparación de calibración sintética",
    ).json()
    if not guardada.get("valida"):
        raise ErrorDemo("La calibración sintética no fue aceptada como válida")
    _ok("Calibración sintética", f"error medio {guardada['error_medio_m']:.4f} m")
    return guardada


def iniciar_si_corresponde(
    http: httpx.Client,
    headers: dict[str, str],
    partido: dict,
    ataca_hacia: str,
) -> None:
    if partido["estado"] == "EN_CURSO":
        _ok("Control del partido", "ya estaba EN_CURSO")
        return
    _exigir(
        http.post(
            f"/partido/{partido['id']}/iniciar",
            headers=headers,
            json={"ataca_hacia": ataca_hacia},
        ),
        200,
        "Inicio del partido",
    )
    partido["estado"] = "EN_CURSO"
    _ok("Control del partido", f"iniciado hacia {ataca_hacia}")


def registrar_evento_critico(
    http: httpx.Client,
    headers: dict[str, str],
    partido: dict,
    alineacion: dict,
) -> None:
    identificador = uuid5(NAMESPACE_URL, f"area-tecnica-demo-sprint4:{partido['id']}:roja")
    equipo_propio = "LOCAL" if partido.get("es_local", True) else "VISITANTE"
    titular = next(
        (jugador for jugador in alineacion.get("jugadores", []) if jugador.get("es_titular")),
        None,
    )
    if titular is None:
        raise ErrorDemo("La alineación no contiene un titular para registrar el evento crítico")
    respuesta = _exigir(
        http.post(
            f"/partido/{partido['id']}/eventos",
            headers=headers,
            json={
                "uuid": str(identificador),
                "tipo": "ROJA",
                "minuto": 5,
                "equipo": equipo_propio,
                "jugador_id": titular["jugador_id"],
            },
        ),
        {200, 201},
        "Registro del evento manual crítico",
    )
    _ok("Evento manual idempotente", f"ROJA #{respuesta.json()['id']}")


def token_ingesta(http: httpx.Client, headers: dict[str, str], partido_id: int) -> str:
    respuesta = _exigir(
        http.post(f"/partido/{partido_id}/token-ingesta", headers=headers),
        201,
        "Token de ingesta",
    )
    return respuesta.json()["token"]


def verificar_funciones(
    http: httpx.Client,
    headers: dict[str, str],
    partido: dict,
    *,
    exigir_preparado: bool,
) -> int:
    partido_id = partido["id"]
    estado = _exigir(
        http.get(f"/partido/{partido_id}/estado", headers=headers),
        200,
        "Estado del partido",
    ).json()
    _ok("Estado en vivo", f"parte {estado['parte']} · {estado['minuto']:02d}:{estado['segundo']:02d}")

    calibracion = http.get(f"/vision/partidos/{partido_id}/calibracion", headers=headers)
    if calibracion.status_code == 200 and (
        calibracion.json().get("valida") or calibracion.json().get("modo") == "AUTOMATICA"
    ):
        _ok("Calibración disponible", calibracion.json().get("modo", ""))
    elif exigir_preparado:
        raise ErrorDemo("El partido preparado no tiene una calibración utilizable")
    else:
        _aviso("Calibración", "falta ejecutar el subcomando preparar")

    reglas = _exigir(
        http.get("/asistencia/reglas?activas=true", headers=headers),
        200,
        "Catálogo de reglas",
    ).json()
    if not reglas:
        raise ErrorDemo("El catálogo global de reglas está vacío")
    _ok("Reglas tácticas", f"{len(reglas)} activas")

    metricas = _exigir(
        http.get(f"/analisis/partidos/{partido_id}/metricas", headers=headers),
        200,
        "Métricas del partido",
    ).json()
    posesion_local = metricas.get("acumulado_local", {}).get("posesion_pct", 0)
    _ok("Métricas", f"posesión local {posesion_local:.1f} %")

    recomendaciones = _exigir(
        http.get(
            f"/asistencia/partidos/{partido_id}/recomendaciones?solo_activas=true",
            headers=headers,
        ),
        200,
        "Recomendaciones",
    ).json()
    if recomendaciones:
        prioridades = ", ".join(r["prioridad"] for r in recomendaciones)
        _ok("Recomendaciones", f"{len(recomendaciones)} visible(s): {prioridades}")
    elif exigir_preparado:
        raise ErrorDemo(
            "No se generaron recomendaciones; revisa los logs de ingesta y del motor táctico"
        )
    else:
        _aviso("Recomendaciones", "aún no hay; ejecutar preparar genera una crítica")
    return len(recomendaciones)


def verificar(args: argparse.Namespace) -> int:
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=15) as http:
        headers, partido, _ = contexto_basico(
            http, args.email, args.password, args.partido
        )
        verificar_funciones(http, headers, partido, exigir_preparado=False)
    print("\nVerificación terminada. Los avisos indican preparación pendiente, no un fallo de la API.")
    return 0


def preparar(args: argparse.Namespace) -> int:
    validar_destino_mutable(args.url, args.permitir_host_remoto)
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=15) as http:
        headers, partido, alineacion = contexto_basico(
            http, args.email, args.password, args.partido
        )
        asegurar_calibracion(http, headers, partido["id"])
        iniciar_si_corresponde(http, headers, partido, args.ataca_hacia)
        if not args.sin_evento_critico:
            registrar_evento_critico(http, headers, partido, alineacion)
        token = token_ingesta(http, headers, partido["id"])

        emisor = Namespace(
            url=args.url,
            partido=partido["id"],
            duracion=args.duracion,
            frecuencia=args.frecuencia,
            token=token,
            email=None,
            password=None,
            largo=105.0,
            ancho=68.0,
            semilla=args.semilla,
            inicio_t=args.inicio_t,
            iniciar_partido=False,
            ataca_hacia=args.ataca_hacia,
        )
        if asyncio.run(correr(emisor)) != 0:
            raise ErrorDemo("El emisor simulado informó mensajes rechazados")
        verificar_funciones(http, headers, partido, exigir_preparado=True)

    print(
        f"\nEscenario listo: abre la web y selecciona el partido #{partido['id']} "
        f"contra {partido['rival']}."
    )
    return 0


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara o verifica la demostración reproducible del Sprint 4."
    )
    parser.add_argument(
        "modo", choices=["verificar", "preparar"], help="verificar no modifica datos"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--email", default=EMAIL_DEMO)
    parser.add_argument("--password", default=os.getenv("DEMO_ADMIN_PASSWORD"))
    parser.add_argument("--partido", type=int, help="usar un partido concreto")
    parser.add_argument("--duracion", type=float, default=12.0)
    parser.add_argument("--frecuencia", type=float, default=5.0)
    parser.add_argument("--inicio-t", type=float, default=300.0)
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--ataca-hacia", choices=["IZQ", "DER"], default="DER")
    parser.add_argument(
        "--sin-evento-critico",
        action="store_true",
        help="no registrar la roja ficticia que garantiza una recomendación crítica",
    )
    parser.add_argument(
        "--permitir-host-remoto",
        action="store_true",
        help="permitir que preparar escriba fuera de localhost",
    )
    args = parser.parse_args(argv)
    if not args.password:
        parser.error("define DEMO_ADMIN_PASSWORD o pasa --password")
    if args.duracion <= 0 or args.frecuencia <= 0 or args.inicio_t < 0:
        parser.error("duración/frecuencia deben ser positivas e inicio-t no negativo")
    return args


def main(argv: list[str] | None = None) -> int:
    args = argumentos(argv)
    try:
        return preparar(args) if args.modo == "preparar" else verificar(args)
    except (ErrorDemo, httpx.HTTPError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
