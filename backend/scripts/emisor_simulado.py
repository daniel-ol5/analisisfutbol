"""Emisor simulado de posiciones  —  T-034.

Reemplaza al worker de visión mientras no existe: se conecta a /ingesta y
publica 22 jugadores y el balón, sin GPU ni video. Desbloquea el panel en vivo
de Web y Móvil (T-077, T-078).

    cd backend
    python scripts/emisor_simulado.py --partido 1 --email admin@club.com --password ...

Ver todas las opciones con --help, o la sección "Emisor simulado" del README.

El movimiento no es aleatorio puro: cada equipo mantiene su formación (4-4-2
el local, 4-3-3 el visitante), el bloque bascula hacia el balón, el que tiene
la pelota se adelanta y el que defiende se repliega, el más cercano presiona,
y el balón circula en pases a compañeros, con pérdidas y remates. Las
velocidades y aceleraciones están acotadas a valores humanos.
"""

import argparse
import asyncio
import json
import math
import random
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# ---------------- Límites físicos ----------------

VEL_MAX = 8.0          # m/s: sprint de un jugador amateur
VEL_PRESION = 7.0      # m/s: el que va a buscar la pelota
VEL_CONDUCCION = 3.5   # m/s: con la pelota en los pies
VEL_TROTE = 3.5        # m/s: reacomodarse en la formación
ACEL_MAX = 3.5         # m/s²
REACCION_S = 1.5       # los bloques siguen al balón con este retraso, no al instante
VEL_PASE = (12.0, 22.0)
VEL_REMATE = (22.0, 28.0)

# ---------------- Formaciones ----------------
# (profundidad, ancho) como fracción de la cancha, para un equipo que ataca
# hacia x creciente. Profundidad 0 = su propio arco.

ARQUERO = (0.04, 0.50)
FORMACION_442 = [
    ARQUERO,
    (0.20, 0.15), (0.18, 0.38), (0.18, 0.62), (0.20, 0.85),   # defensa
    (0.40, 0.15), (0.38, 0.38), (0.38, 0.62), (0.40, 0.85),   # medio
    (0.58, 0.40), (0.58, 0.60),                               # delanteros
]
FORMACION_433 = [
    ARQUERO,
    (0.20, 0.15), (0.18, 0.38), (0.18, 0.62), (0.20, 0.85),
    (0.38, 0.30), (0.34, 0.50), (0.38, 0.70),
    (0.58, 0.15), (0.62, 0.50), (0.58, 0.85),
]

LOCAL, VISITANTE = "LOCAL", "VISITANTE"


@dataclass
class Jugador:
    tid: int
    equipo: str
    base: tuple[float, float]
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0

    @property
    def es_arquero(self) -> bool:
        return self.base == ARQUERO


@dataclass
class Pase:
    destino: tuple[float, float]
    receptor: Jugador
    velocidad: float


class Simulacion:
    """Estado del partido simulado. `paso(dt)` avanza y devuelve un
    MensajeWorker como diccionario. No usa la red: se prueba directo."""

    def __init__(self, partido: int, largo: float = 105.0, ancho: float = 68.0,
                 frecuencia: float = 5.0, semilla: int | None = None, t0: float = 0.0):
        self.partido = partido
        self.largo, self.ancho = largo, ancho
        self.frecuencia = frecuencia
        self.rng = random.Random(semilla)
        self.t = t0

        self.jugadores: list[Jugador] = []
        for i, base in enumerate(FORMACION_442, start=1):
            self.jugadores.append(self._nuevo(i, LOCAL, base))
        for i, base in enumerate(FORMACION_433, start=12):
            self.jugadores.append(self._nuevo(i, VISITANTE, base))

        self.balon = [largo / 2, ancho / 2]
        self._balon_suave = [largo / 2, ancho / 2]   # lo que "lee" el bloque
        self.poseedor: Jugador | None = self.jugadores[6]   # un volante local
        self.pase: Pase | None = None
        self._proxima_decision = self.t + self.rng.uniform(1.0, 2.5)
        self._balon_oculto_hasta = -1.0

    # ---------- geometría ----------

    def _sentido(self, equipo: str) -> int:
        return 1 if equipo == LOCAL else -1

    def _absoluta_x(self, equipo: str, xr: float) -> float:
        """De profundidad relativa al equipo a coordenada de cancha."""
        return xr if equipo == LOCAL else self.largo - xr

    def _nuevo(self, tid: int, equipo: str, base: tuple[float, float]) -> Jugador:
        x = self._absoluta_x(equipo, base[0] * self.largo)
        return Jugador(tid, equipo, base, x, base[1] * self.ancho)

    def _acotar(self, x: float, y: float) -> tuple[float, float]:
        return min(max(x, 0.0), self.largo), min(max(y, 0.0), self.ancho)

    def equipo_con_posesion(self) -> str | None:
        if self.poseedor:
            return self.poseedor.equipo
        if self.pase:
            return self.pase.receptor.equipo
        return None

    # ---------- objetivos tácticos ----------

    def _objetivo(self, j: Jugador, posesion: str | None) -> tuple[float, float]:
        bx, by = self._balon_suave
        s = self._sentido(j.equipo)
        balon_r = bx if s > 0 else self.largo - bx   # balón medido desde su arco

        if j.es_arquero:
            xr = min(3.0 + 0.08 * balon_r, 14.0)
            return self._absoluta_x(j.equipo, xr), self.ancho / 2 + 0.25 * (by - self.ancho / 2)

        ataca = j.equipo == posesion
        # El bloque acompaña al balón a lo largo; con posesión se adelanta. La
        # profundidad de la formación se comprime hacia el centro: los dos
        # bloques se superponen en el medio, no esperan cada uno en su campo.
        profundidad = (0.22 + 0.55 * j.base[0]) * self.largo
        xr = profundidad + 0.5 * (balon_r - self.largo / 2) + (8.0 if ataca else -4.0)
        xr = min(max(xr, 6.0), self.largo - 6.0)
        # A lo ancho: bascula hacia el balón; sin posesión se cierra.
        abierto = 1.0 if ataca else 0.75
        y = self.ancho / 2 + (j.base[1] * self.ancho - self.ancho / 2) * abierto
        y += 0.35 * (by - self.ancho / 2)
        return self._acotar(self._absoluta_x(j.equipo, xr), y)

    def _mas_cercano(self, equipo: str, x: float, y: float,
                     excluir: Jugador | None = None) -> Jugador:
        candidatos = [j for j in self.jugadores
                      if j.equipo == equipo and not j.es_arquero and j is not excluir]
        return min(candidatos, key=lambda j: math.hypot(j.x - x, j.y - y))

    # ---------- física ----------

    def _mover(self, j: Jugador, tx: float, ty: float, vmax: float, dt: float) -> None:
        dx, dy = tx - j.x, ty - j.y
        d = math.hypot(dx, dy)
        # Velocidad deseada: llegar en ~1 s, frenando al acercarse; a menos de
        # medio metro del objetivo, quieto (si no, tiemblan sin parar)
        v_des = min(vmax, max(0.0, d - 0.5))
        dvx = (dx / d * v_des if d > 1e-6 else 0.0) - j.vx
        dvy = (dy / d * v_des if d > 1e-6 else 0.0) - j.vy
        # Pequeña variación individual para que no se muevan como robots
        dvx += self.rng.gauss(0, 0.1)
        dvy += self.rng.gauss(0, 0.1)

        dv = math.hypot(dvx, dvy)
        if dv > ACEL_MAX * dt:
            dvx, dvy = dvx / dv * ACEL_MAX * dt, dvy / dv * ACEL_MAX * dt
        j.vx += dvx
        j.vy += dvy

        v = math.hypot(j.vx, j.vy)
        if v > VEL_MAX:
            j.vx, j.vy = j.vx / v * VEL_MAX, j.vy / v * VEL_MAX

        nx, ny = self._acotar(j.x + j.vx * dt, j.y + j.vy * dt)
        if nx != j.x + j.vx * dt:
            j.vx = 0.0
        if ny != j.y + j.vy * dt:
            j.vy = 0.0
        j.x, j.y = nx, ny

    # ---------- decisiones con la pelota ----------

    def _decidir(self) -> None:
        p = self.poseedor
        assert p is not None
        s = self._sentido(p.equipo)
        avance_r = p.x if s > 0 else self.largo - p.x

        if avance_r > self.largo - 22 and self.rng.random() < 0.5:
            # Remate: va al arco y lo recibe el arquero rival
            arquero = next(j for j in self.jugadores if j.equipo != p.equipo and j.es_arquero)
            arco_x = self.largo if s > 0 else 0.0
            destino = (arco_x - s * 0.5, self.ancho / 2 + self.rng.uniform(-3.5, 3.5))
            self._lanzar(destino, arquero, self.rng.uniform(*VEL_REMATE))
            return

        companeros = [j for j in self.jugadores if j.equipo == p.equipo and j is not p]

        def peso(j: Jugador) -> float:
            d = math.hypot(j.x - p.x, j.y - p.y)
            adelante = s * (j.x - p.x) > 0
            w = math.exp(-(((d - 18.0) / 12.0) ** 2)) * (1.6 if adelante else 1.0)
            return w * (0.15 if j.es_arquero else 1.0)

        receptor = self.rng.choices(companeros, weights=[peso(j) for j in companeros])[0]
        velocidad = self.rng.uniform(*VEL_PASE)
        vuelo = math.hypot(receptor.x - p.x, receptor.y - p.y) / velocidad
        destino = self._acotar(receptor.x + receptor.vx * vuelo, receptor.y + receptor.vy * vuelo)

        if self.rng.random() < 0.15:
            # Interceptado: lo corta el rival más cercano a la mitad del pase
            mx, my = (p.x + destino[0]) / 2, (p.y + destino[1]) / 2
            rival = self._mas_cercano(VISITANTE if p.equipo == LOCAL else LOCAL, mx, my)
            destino = self._acotar(p.x + 0.6 * (destino[0] - p.x), p.y + 0.6 * (destino[1] - p.y))
            receptor = rival
        self._lanzar(destino, receptor, velocidad)

    def _lanzar(self, destino: tuple[float, float], receptor: Jugador, velocidad: float) -> None:
        self.pase = Pase(destino, receptor, velocidad)
        self.poseedor = None

    def _recibir(self, jugador: Jugador) -> None:
        self.poseedor = jugador
        self.pase = None
        self._proxima_decision = self.t + self.rng.uniform(0.8, 3.0)

    # ---------- un paso ----------

    def paso(self, dt: float | None = None) -> dict:
        dt = dt if dt is not None else 1.0 / self.frecuencia
        self.t += dt
        posesion = self.equipo_con_posesion()
        defensor = VISITANTE if posesion == LOCAL else LOCAL
        presionador = self._mas_cercano(defensor, *self.balon) if posesion else None

        for j in self.jugadores:
            if j is self.poseedor:
                s = self._sentido(j.equipo)
                tx, ty, vmax = j.x + s * 6.0, j.y + 0.1 * (self.ancho / 2 - j.y), VEL_CONDUCCION
            elif self.pase and j is self.pase.receptor:
                (tx, ty), vmax = self.pase.destino, VEL_PRESION
            elif j is presionador:
                (tx, ty), vmax = self.balon, VEL_PRESION
            else:
                (tx, ty), vmax = self._objetivo(j, posesion), VEL_TROTE
            self._mover(j, tx, ty, vmax, dt)

        self._mover_balon(presionador, dt)
        alfa = min(1.0, dt / REACCION_S)
        self._balon_suave = [s + alfa * (b - s) for s, b in zip(self._balon_suave, self.balon,
                                                                 strict=True)]
        return self.mensaje()

    def _mover_balon(self, presionador: Jugador | None, dt: float) -> None:
        if self.pase:
            dx = self.pase.destino[0] - self.balon[0]
            dy = self.pase.destino[1] - self.balon[1]
            d = math.hypot(dx, dy)
            avance = self.pase.velocidad * dt
            if d <= avance:
                self.balon = list(self.pase.destino)
                self._recibir(self.pase.receptor)
            else:
                self.balon = [self.balon[0] + dx / d * avance, self.balon[1] + dy / d * avance]
            return

        p = self.poseedor
        if p is None:
            return
        s = self._sentido(p.equipo)
        self.balon = list(self._acotar(p.x + s * 0.6, p.y))

        if presionador and math.hypot(presionador.x - p.x, presionador.y - p.y) < 1.5 \
                and self.rng.random() < 0.6 * dt:
            self._recibir(presionador)          # le roban la pelota
        elif self.t >= self._proxima_decision:
            self._decidir()

    # ---------- lo que "ve" la cámara ----------

    def mensaje(self) -> dict:
        def medido(x: float, y: float) -> tuple[float, float]:
            # Error de detección y homografía, de unos centímetros
            return self._acotar(x + self.rng.gauss(0, 0.1), y + self.rng.gauss(0, 0.1))

        jugadores = []
        for j in self.jugadores:
            x, y = medido(j.x, j.y)
            jugadores.append({"tid": j.tid, "equipo": j.equipo, "x": round(x, 2),
                              "y": round(y, 2), "conf": round(self.rng.uniform(0.80, 0.98), 2)})

        # De vez en cuando el balón se pierde de vista (tapado, en el aire)
        if self.t >= self._balon_oculto_hasta and self.rng.random() < 0.01:
            self._balon_oculto_hasta = self.t + self.rng.uniform(0.4, 1.6)
        visible = self.t >= self._balon_oculto_hasta
        balon = None
        if visible:
            x, y = medido(*self.balon)
            conf = self.rng.uniform(0.45, 0.70) if self.pase else self.rng.uniform(0.60, 0.92)
            balon = {"tid": 0, "equipo": "DESCONOCIDO", "x": round(x, 2), "y": round(y, 2),
                     "conf": round(conf, 2)}

        return {
            "partido": self.partido,
            "t": round(self.t, 2),
            "jugadores": jugadores,
            "balon": balon,
            "calidad": {"worker_conectado": True, "fps": self.frecuencia,
                        "jugadores_detectados": len(jugadores), "balon_visible": visible,
                        "retraso_s": round(self.rng.uniform(0.15, 0.40), 2), "degradado": False},
        }


# ---------------- Envío ----------------

@dataclass
class Resumen:
    enviados: int = 0
    errores: int = 0
    primer_error: str | None = None


async def emitir(enviar: Callable[[str], Awaitable[None]], sim: Simulacion, duracion: float,
                 tiempo_real: bool = True,
                 al_avanzar: Callable[[Resumen, Simulacion], None] | None = None,
                 resumen: Resumen | None = None) -> Resumen:
    """Envía `duracion` segundos de partido a `sim.frecuencia` mensajes por segundo.

    Con `tiempo_real` respeta el reloj (con un reloj monotónico, sin acumular
    desfase); sin él, envía todo de corrido (pruebas).
    """
    resumen = resumen or Resumen()
    total = round(duracion * sim.frecuencia)
    dt = 1.0 / sim.frecuencia
    inicio = time.monotonic()
    for n in range(1, total + 1):
        await enviar(json.dumps(sim.paso(dt)))
        resumen.enviados += 1
        if al_avanzar and n % round(sim.frecuencia * 5) == 0:
            al_avanzar(resumen, sim)
        if tiempo_real:
            await asyncio.sleep(max(0.0, inicio + n * dt - time.monotonic()))
    return resumen


def url_ws(api: str, partido: int) -> str:
    """http://host:8000/api -> ws://host:8000/api/partido/{id}/ingesta"""
    base = api.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return f"{base}/partido/{partido}/ingesta"


def pedir_token(api: str, partido: int, email: str, password: str) -> str:
    """Inicia sesión y pide un token de ingesta para el partido."""
    import httpx

    with httpx.Client(base_url=api.rstrip("/"), timeout=10) as http:
        r = http.post("/seguridad/login", json={"email": email, "password": password})
        if r.status_code != 200:
            sys.exit(f"No se pudo iniciar sesión ({r.status_code}): {r.text}")
        acceso = r.json()["access_token"]
        r = http.post(f"/partido/{partido}/token-ingesta",
                      headers={"Authorization": f"Bearer {acceso}"})
        if r.status_code != 201:
            sys.exit(f"No se pudo obtener el token de ingesta ({r.status_code}): {r.text}")
        return r.json()["token"]


async def correr(args: argparse.Namespace) -> int:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    token = args.token or pedir_token(args.url, args.partido, args.email, args.password)
    sim = Simulacion(args.partido, args.largo, args.ancho, args.frecuencia, args.semilla,
                     args.inicio_t)
    destino = url_ws(args.url, args.partido)
    resumen = Resumen()

    async with connect(destino) as ws:
        await ws.send(json.dumps({"tipo": "auth", "token": token}))
        try:
            listo = json.loads(await asyncio.wait_for(ws.recv(), 5))
        except ConnectionClosed as e:
            print(f"El servidor cerró la conexión: {e.rcvd.code if e.rcvd else '?'} "
                  f"{e.rcvd.reason if e.rcvd else ''}", file=sys.stderr)
            return 1
        if listo.get("tipo") != "listo":
            print(f"Respuesta inesperada: {listo}", file=sys.stderr)
            return 1
        print(f"Conectado a {destino} · {args.frecuencia:g} msg/s durante {args.duracion:g} s")

        async def escuchar_errores() -> None:
            async for crudo in ws:
                datos = json.loads(crudo)
                if datos.get("tipo") == "error":
                    resumen.errores += 1
                    resumen.primer_error = resumen.primer_error or json.dumps(datos["detalle"])

        def progreso(r: Resumen, s: Simulacion) -> None:
            pos = s.equipo_con_posesion() or "-"
            print(f"  t={s.t:7.1f} s · enviados {r.enviados:5d} · errores {r.errores} · "
                  f"posesión {pos}")

        oyente = asyncio.create_task(escuchar_errores())
        try:
            await emitir(ws.send, sim, args.duracion, al_avanzar=progreso, resumen=resumen)
            await asyncio.sleep(0.5)    # dar tiempo a que lleguen errores atrasados
        except ConnectionClosed as e:
            print(f"Conexión cerrada por el servidor: {e.rcvd.code if e.rcvd else '?'} "
                  f"{e.rcvd.reason if e.rcvd else ''}", file=sys.stderr)
            return 1
        finally:
            oyente.cancel()

    print(f"Listo: {resumen.enviados} mensajes enviados, {resumen.errores} rechazados.")
    if resumen.primer_error:
        print(f"Primer error: {resumen.primer_error}")
    return 0 if resumen.errores == 0 else 1


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Emisor simulado de posiciones: alimenta /ingesta sin GPU ni video.")
    p.add_argument("--url", default="http://localhost:8000/api",
                   help="Base de la API (por defecto %(default)s)")
    p.add_argument("--partido", type=int, required=True, help="Id del partido")
    p.add_argument("--duracion", type=float, default=60.0,
                   help="Segundos a emitir (por defecto %(default)s)")
    p.add_argument("--frecuencia", type=float, default=5.0,
                   help="Mensajes por segundo (por defecto %(default)s)")
    p.add_argument("--token", help="Token de ingesta, si ya se tiene uno")
    p.add_argument("--email", help="Cuenta ADMIN o ANALISTA, para pedir el token")
    p.add_argument("--password")
    p.add_argument("--largo", type=float, default=105.0, help="Metros (por defecto %(default)s)")
    p.add_argument("--ancho", type=float, default=68.0, help="Metros (por defecto %(default)s)")
    p.add_argument("--semilla", type=int, help="Para repetir exactamente la misma simulación")
    p.add_argument("--inicio-t", type=float, default=0.0,
                   help="Segundo de partido en el que empieza (por defecto %(default)s)")
    args = p.parse_args(argv)
    if not args.token and not (args.email and args.password):
        p.error("hace falta --token, o --email y --password")
    if args.frecuencia <= 0 or args.duracion <= 0:
        p.error("--frecuencia y --duracion deben ser positivas")
    return args


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(correr(argumentos())))
    except KeyboardInterrupt:
        sys.exit(130)
    except OSError as e:
        sys.exit(f"No se pudo conectar con la API: {e}")
