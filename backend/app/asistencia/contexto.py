"""Produce métricas confiables para CU-49 a partir de la ingesta en directo."""

from app.analisis.motor.motor import MotorPartido, porcentajes
from app.analisis.motor.muestras import Muestra, muestra_de_mensaje
from app.partido.schemas import EquipoDetectado, MensajeWorker

VENTANA_BLOQUE_S = 15
VENTANA_JUEGO_S = 30
VENTANA_RITMO_S = 30


class EstadoTactico:
    """Reutiliza el motor de análisis con su propia entrada, solo de directo.

    Una interrupción o degradación descarta la ventana, de modo que los datos de
    video diferido, recuperados tras reiniciar o sin referencia no contaminarán
    las recomendaciones. Los eventos manuales se leen por separado.
    """

    def __init__(self) -> None:
        self._motor: MotorPartido | None = None
        self._ultimo_t: float | None = None
        self._parte: int | None = None
        self._desde_campo = 0.0
        self._desde_balon: float | None = None

    def interrumpir(self) -> None:
        self._motor = None
        self._desde_balon = None

    def observar(self, mensaje: MensajeWorker, analisis: MotorPartido) -> bool:
        muestra = muestra_de_mensaje(mensaje)
        t = muestra.t
        anterior = self._ultimo_t
        if anterior is not None and t <= anterior:
            return False
        self._ultimo_t = t
        parte = 1 if t < analisis.p.segundos_primer_tiempo else 2
        if parte != self._parte or (anterior is not None and t - anterior > analisis.p.max_hueco_s + 1e-6):
            self.interrumpir()
        self._parte = parte

        calidad = mensaje.calidad
        lados = (EquipoDetectado.LOCAL, EquipoDetectado.VISITANTE)
        visibles = [len({j.tid for j in mensaje.jugadores if j.equipo == lado}) for lado in lados]
        campo_valido = (
            calidad.worker_conectado and not calidad.degradado
            and calidad.calibracion_valida is True
            and calidad.estado_calibracion not in ("PERDIDA", "SIN_REFERENCIA")
            and calidad.retraso_s <= 2
            and calidad.jugadores_detectados >= 16 and sum(visibles) >= 16 and min(visibles) >= 7
        )
        if not campo_valido:
            self.interrumpir()
            return True

        if self._motor is None:
            self._motor = MotorPartido(analisis.contexto, analisis.p, analisis.arqueros)
            self._desde_campo = t
        if self._motor.arqueros != analisis.arqueros:
            self._motor.actualizar_arqueros(analisis.arqueros)

        if not calidad.balon_visible or muestra.balon is None:
            self._desde_balon = None
            muestra = Muestra(muestra.t, muestra.jugadores, None)
        elif self._desde_balon is None:
            self._desde_balon = t
        self._motor.procesar(muestra)
        return True

    def metricas(self) -> dict[str, float]:
        motor = self._motor
        if motor is None or motor.t is None:
            return {}
        t = motor.t
        propio = motor.contexto.lado_propio
        rival = "VISITANTE" if propio == "LOCAL" else "LOCAL"
        datos: dict[str, float] = {}
        if t - self._desde_campo >= VENTANA_BLOQUE_S + 1 and motor.contexto.ataca_hacia:
            bloque = motor.ultimos(VENTANA_BLOQUE_S).equipos[propio]
            if bloque.n_altura >= 12 and bloque.altura_linea_m is not None:
                datos["altura_linea_m"] = bloque.altura_linea_m
            if bloque.n_forma >= 12:
                if bloque.amplitud_m is not None:
                    datos["amplitud_propia_m"] = bloque.amplitud_m
                if bloque.compacidad_m is not None:
                    datos["compacidad_propia_m"] = bloque.compacidad_m

        if self._desde_balon is not None and t - self._desde_balon >= VENTANA_JUEGO_S + motor.p.pase_max_hueco_s:
            juego = motor.ultimos(VENTANA_JUEGO_S)
            observados = juego.equipos[propio].posesion_s + juego.equipos[rival].posesion_s
            if observados >= 0.6 * VENTANA_JUEGO_S:
                local, visitante, _ = porcentajes(juego)
                datos["posesion_propia_pct"], datos["posesion_rival_pct"] = (
                    (local, visitante) if propio == "LOCAL" else (visitante, local)
                )
                nuestros, contrarios = juego.equipos[propio], juego.equipos[rival]
                datos["pases_intentados_propios"] = nuestros.pases_intentados
                datos["pases_completados_rival"] = contrarios.pases_completados
                if nuestros.pases_intentados:
                    datos["precision_pase_propio_pct"] = (
                        100 * nuestros.pases_completados / nuestros.pases_intentados
                    )

        if t - self._desde_campo >= VENTANA_RITMO_S + 1:
            actual = motor.ultimos(VENTANA_RITMO_S).equipos[propio]
            minimo = 6 * VENTANA_RITMO_S  # segundos de observación por jugador sumados
            if actual.tiempo_ritmo_s >= minimo:
                ritmo = 60 * actual.distancia_ritmo_m / actual.tiempo_ritmo_s
                datos["ritmo_propio_m_min"] = ritmo
                if t - self._desde_campo >= 2 * VENTANA_RITMO_S + 1:
                    ambas = motor.ultimos(2 * VENTANA_RITMO_S).equipos[propio]
                    tiempo_prev = ambas.tiempo_ritmo_s - actual.tiempo_ritmo_s
                    if tiempo_prev >= minimo:
                        anterior = 60 * (ambas.distancia_ritmo_m - actual.distancia_ritmo_m) / tiempo_prev
                        if anterior >= 20:
                            datos["caida_ritmo_propio_pct"] = 100 * (1 - ritmo / anterior)
        return datos
