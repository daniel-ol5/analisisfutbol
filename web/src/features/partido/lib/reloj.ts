/**
 * Lógica pura del cronómetro, fases de control y ordenamiento de partidos
 * (CU-30, CU-31, T-068). Sin dependencias de React.
 */
import type { EstadoEnVivo, EstadoPartidoAgenda, ResumenPartidoControl } from "../types";

/** Intervalo de refresco HTTP de `GET /partido/{id}/estado` en la Fase 2A (5 s). */
export const INTERVALO_REFRESCO_ESTADO_MS = 5_000;

/** Intervalo de actualización del reloj local con `performance.now()` (250 ms). */
export const INTERVALO_TICK_RELOJ_MS = 250;

/** Segundos reglamentarios al cierre del primer tiempo (45:00). */
export const SEGUNDOS_PRIMER_TIEMPO = 45 * 60;

/** Segundos reglamentarios al cierre del segundo tiempo (90:00). */
export const SEGUNDOS_SEGUNDO_TIEMPO = 90 * 60;

/** Rango permitido para minutos de descuento según el contrato (`0..15`). */
export const MIN_DESCUENTO_MIN = 0;
export const MAX_DESCUENTO_MIN = 15;

/**
 * Tolerancia máxima (1 s) para no retroceder el segundero local cuando el
 * servidor devuelve `int(segundos_transcurridos)` dentro del mismo `(parte, en_curso)`.
 */
export const TOLERANCIA_NO_RETROCESO_S = 1;

export interface AnclaReloj {
  partidoId: number;
  parte: number;
  enCurso: boolean;
  baseSegundos: number;
  marcaMonotonicaMs: number;
}

export type FaseControlPartido =
  "NO_INICIADO" | "PRIMER_TIEMPO" | "ENTRETIEMPO" | "SEGUNDO_TIEMPO" | "CERRADO";

export function calcularSegundosActuales(ancla: AnclaReloj | null, ahoraMs: number): number {
  if (!ancla) return 0;
  if (!ancla.enCurso) return ancla.baseSegundos;
  const transcurridoS = Math.max(0, Math.floor((ahoraMs - ancla.marcaMonotonicaMs) / 1000));
  return ancla.baseSegundos + transcurridoS;
}

/**
 * Reconcilia el estado remoto con el ancla monotónica local:
 * - Si cambia `partido_id`, `parte` o `en_curso`, re-ancla de inmediato.
 * - Si el reloj está corriendo en la misma `parte` y el servidor trae el mismo
 *   segundo o hasta 1 s menos (por truncamiento entero), no retrocede el segundero.
 * - Si la diferencia es mayor a 1 s o el servidor va por delante, re-ancla.
 */
export function reconciliarAnclaReloj(
  anclaActual: AnclaReloj | null,
  estadoRemoto: EstadoEnVivo,
  ahoraMs: number,
): AnclaReloj {
  const segundosServidor = Math.max(0, estadoRemoto.minuto * 60 + estadoRemoto.segundo);

  if (
    !anclaActual ||
    anclaActual.partidoId !== estadoRemoto.partido_id ||
    anclaActual.parte !== estadoRemoto.parte ||
    anclaActual.enCurso !== estadoRemoto.en_curso ||
    !estadoRemoto.en_curso
  ) {
    return {
      partidoId: estadoRemoto.partido_id,
      parte: estadoRemoto.parte,
      enCurso: estadoRemoto.en_curso,
      baseSegundos: segundosServidor,
      marcaMonotonicaMs: ahoraMs,
    };
  }

  const segundosLocales = calcularSegundosActuales(anclaActual, ahoraMs);
  const diferencia = segundosLocales - segundosServidor;

  // Mismo segundo: conserva el ancla para no reiniciar la fracción de segundo en curso.
  if (diferencia === 0) {
    return anclaActual;
  }

  // El servidor lleva 1 s menos por truncamiento: congela la base en el segundo local actual
  // sin retroceder el segundero.
  if (diferencia > 0 && diferencia <= TOLERANCIA_NO_RETROCESO_S) {
    return {
      partidoId: estadoRemoto.partido_id,
      parte: estadoRemoto.parte,
      enCurso: true,
      baseSegundos: segundosLocales,
      marcaMonotonicaMs: ahoraMs,
    };
  }

  return {
    partidoId: estadoRemoto.partido_id,
    parte: estadoRemoto.parte,
    enCurso: true,
    baseSegundos: segundosServidor,
    marcaMonotonicaMs: ahoraMs,
  };
}

function formatearMmSs(segundosTotales: number): string {
  const s = Math.max(0, Math.floor(segundosTotales));
  const minutos = Math.floor(s / 60);
  const segundos = s % 60;
  return `${String(minutos).padStart(2, "0")}:${String(segundos).padStart(2, "0")}`;
}

/**
 * Formatea el cronómetro en `MM:SS`, mostrando `45:00 +MM:SS` en el 1.er tiempo
 * y `90:00 +MM:SS` en el 2.º tiempo cuando supera el tiempo reglamentario.
 */
export function formatearCronometroPartido(segundosTotales: number, parte: number): string {
  const seg = Math.max(0, Math.floor(segundosTotales));
  if (parte === 1 && seg > SEGUNDOS_PRIMER_TIEMPO) {
    return `45:00 +${formatearMmSs(seg - SEGUNDOS_PRIMER_TIEMPO)}`;
  }
  if (parte === 2 && seg > SEGUNDOS_SEGUNDO_TIEMPO) {
    return `90:00 +${formatearMmSs(seg - SEGUNDOS_SEGUNDO_TIEMPO)}`;
  }
  return formatearMmSs(seg);
}

export function determinarFaseControl(
  estadoVivo: EstadoEnVivo | undefined,
  estadoAgenda: EstadoPartidoAgenda | undefined,
): FaseControlPartido {
  if (estadoAgenda === "FINALIZADO" || estadoAgenda === "CANCELADO") {
    return "CERRADO";
  }
  if (!estadoVivo) {
    return "NO_INICIADO";
  }
  if (estadoVivo.parte === 0) {
    return "NO_INICIADO";
  }
  if (estadoVivo.parte === 1) {
    return estadoVivo.en_curso ? "PRIMER_TIEMPO" : "ENTRETIEMPO";
  }
  if (estadoVivo.parte === 2) {
    return estadoVivo.en_curso ? "SEGUNDO_TIEMPO" : "CERRADO";
  }
  return "NO_INICIADO";
}

export function rolPuedeOperarPartido(rol: string | null): boolean {
  return rol === "ADMIN" || rol === "ANALISTA";
}

const PESO_ESTADO_PARTIDO: Record<EstadoPartidoAgenda, number> = {
  EN_CURSO: 0,
  PROGRAMADO: 1,
  FINALIZADO: 2,
  CANCELADO: 3,
};

/**
 * Ordena los partidos priorizando `EN_CURSO` y `PROGRAMADO` primero, y luego
 * por fecha más reciente.
 */
export function ordenarPartidosParaSelector(
  partidos: readonly ResumenPartidoControl[],
): ResumenPartidoControl[] {
  return [...partidos].sort((a, b) => {
    const pesoDiff = PESO_ESTADO_PARTIDO[a.estado] - PESO_ESTADO_PARTIDO[b.estado];
    if (pesoDiff !== 0) return pesoDiff;
    return b.fecha_hora.localeCompare(a.fecha_hora);
  });
}

export function esErrorDeCalibracion409(status: number | null, mensaje: string): boolean {
  if (status !== 409) return false;
  const normalizado = mensaje.toLowerCase();
  return normalizado.includes("calibraci");
}
