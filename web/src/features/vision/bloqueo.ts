/**
 * ¿Esta calibración permite iniciar el partido? (CU-21 · bloqueo de inicio).
 *
 * Función PURA: sin React, sin imports de la feature ni de otras features, para
 * poder moverla tal cual a `shared/lib/` el día que la pantalla de iniciar
 * partido (T-068) la necesite (una feature no puede importar de otra).
 *
 * La fuente de verdad es el campo `valida` que calcula el servidor (error medio
 * mayor a 2 m ⇒ `valida = false`), idealmente el persistido con
 * `GET /vision/partidos/{id}/calibracion`, no el estado de una pantalla.
 */

/** Forma mínima que necesita; la cumplen `Calibracion` y `ErrorCalibracion`. */
export interface CalibracionParaInicio {
  valida: boolean;
}

export interface BloqueoInicio {
  bloqueado: boolean;
  /** Explicación en español; `null` si no hay bloqueo. */
  motivo: string | null;
}

export function evaluarBloqueoInicio(calibracion: CalibracionParaInicio | null): BloqueoInicio {
  if (calibracion === null) {
    return { bloqueado: true, motivo: "El partido todavía no tiene una calibración." };
  }
  if (!calibracion.valida) {
    return {
      bloqueado: true,
      motivo: "La calibración no es válida: el error medio supera el máximo permitido.",
    };
  }
  return { bloqueado: false, motivo: null };
}
