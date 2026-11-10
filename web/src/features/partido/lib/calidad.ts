/** Reglas deterministas de supervisión de calidad — T-073 (HU-33). */
import type { EstadoCanalVivo, IndicadorCalidad } from "../types";

export const FPS_ESPERADO = 5;
export const TRACKS_ESPERADOS_REFERENCIA = 23;
export const UMBRAL_FPS_BAJO = 3;
export const UMBRAL_JUGADORES_BAJO = 16;
export const DURACION_JUGADORES_BAJO_MS = 10_000;
export const DURACION_BALON_AUSENTE_MS = 30_000;

/**
 * Con 5 Hz se esperan muestras cada 200 ms. Se usan 3 s de tolerancia para
 * evitar falsos positivos por una pausa breve del navegador o de la red.
 */
export const CADUCIDAD_TELEMETRIA_MS = 3_000;

export type CodigoAlertaCalidad =
  "WORKER_DESCONECTADO" | "FPS_BAJO" | "JUGADORES_BAJOS" | "BALON_AUSENTE" | "WORKER_DEGRADADO";

export interface AlertaCalidad {
  codigo: CodigoAlertaCalidad;
  titulo: string;
  detalle: string;
}

export interface MuestraSupervisionCalidad {
  canal: EstadoCanalVivo;
  calidad: IndicadorCalidad | null;
  recibidaEnMs: number | null;
  tracksActivos: number | null;
  latenciaWsMs: number | null;
}

export interface EstadoSupervisionCalidad {
  jugadoresBajosDesdeMs: number | null;
  balonAusenteDesdeMs: number | null;
  workerConectado: boolean;
  alertas: AlertaCalidad[];
}

export function crearEstadoSupervisionCalidad(): EstadoSupervisionCalidad {
  return {
    jugadoresBajosDesdeMs: null,
    balonAusenteDesdeMs: null,
    workerConectado: false,
    alertas: [],
  };
}

export function calcularLatenciaWsMs(enviadoEnMs: number, recibidoEnMs: number): number {
  return Math.max(0, recibidoEnMs - enviadoEnMs);
}

export function contarTracksActivos(datos: unknown): number | null {
  if (typeof datos !== "object" || datos === null) return null;
  const mensaje = datos as Record<string, unknown>;
  if (!Array.isArray(mensaje["jugadores"])) return null;
  const ids = new Set<number>();
  for (const jugador of mensaje["jugadores"]) {
    if (typeof jugador !== "object" || jugador === null) continue;
    const tid = (jugador as Record<string, unknown>)["tid"];
    if (typeof tid === "number") ids.add(tid);
  }
  const balon = mensaje["balon"];
  if (typeof balon === "object" && balon !== null) {
    const tid = (balon as Record<string, unknown>)["tid"];
    if (typeof tid === "number") ids.add(tid);
  }
  return ids.size;
}

export function evaluarSupervisionCalidad(
  anterior: EstadoSupervisionCalidad,
  muestra: MuestraSupervisionCalidad,
  ahoraMs: number,
): EstadoSupervisionCalidad {
  const telemetriaVigente =
    muestra.recibidaEnMs !== null && ahoraMs - muestra.recibidaEnMs <= CADUCIDAD_TELEMETRIA_MS;
  const workerConectado =
    muestra.canal === "CONECTADO" &&
    telemetriaVigente &&
    muestra.calidad?.worker_conectado === true;

  if (!workerConectado || muestra.calidad === null) {
    return {
      jugadoresBajosDesdeMs: null,
      balonAusenteDesdeMs: null,
      workerConectado: false,
      alertas: [
        {
          codigo: "WORKER_DESCONECTADO",
          titulo: "Worker desconectado",
          detalle: "No se reciben muestras recientes del procesamiento de visión.",
        },
      ],
    };
  }

  const calidad = muestra.calidad;
  const jugadoresBajosDesdeMs =
    calidad.jugadores_detectados < UMBRAL_JUGADORES_BAJO
      ? (anterior.jugadoresBajosDesdeMs ?? ahoraMs)
      : null;
  const balonAusenteDesdeMs = !calidad.balon_visible
    ? (anterior.balonAusenteDesdeMs ?? ahoraMs)
    : null;
  const alertas: AlertaCalidad[] = [];

  if (calidad.fps < UMBRAL_FPS_BAJO) {
    alertas.push({
      codigo: "FPS_BAJO",
      titulo: "FPS por debajo del mínimo",
      detalle: `${calidad.fps.toFixed(1)} FPS; el mínimo operativo es ${UMBRAL_FPS_BAJO}.`,
    });
  }
  if (
    jugadoresBajosDesdeMs !== null &&
    ahoraMs - jugadoresBajosDesdeMs >= DURACION_JUGADORES_BAJO_MS
  ) {
    alertas.push({
      codigo: "JUGADORES_BAJOS",
      titulo: "Pocos jugadores detectados",
      detalle: `${calidad.jugadores_detectados} jugadores durante al menos 10 segundos; se esperan 16 o más.`,
    });
  }
  if (balonAusenteDesdeMs !== null && ahoraMs - balonAusenteDesdeMs >= DURACION_BALON_AUSENTE_MS) {
    alertas.push({
      codigo: "BALON_AUSENTE",
      titulo: "Balón no detectado",
      detalle: "El balón lleva más de 30 segundos sin aparecer en la telemetría.",
    });
  }
  if (calidad.degradado) {
    alertas.push({
      codigo: "WORKER_DEGRADADO",
      titulo: "Degradación reportada por el worker",
      detalle: calidad.motivo ?? "El worker marcó la muestra como degradada.",
    });
  }

  return {
    jugadoresBajosDesdeMs,
    balonAusenteDesdeMs,
    workerConectado: true,
    alertas,
  };
}
