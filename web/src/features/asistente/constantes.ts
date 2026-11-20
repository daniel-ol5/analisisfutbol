/** Constantes del asistente compartidas por los componentes y sus pruebas. */

export const CLAVE_PROGRESO = ["asistente", "progreso"] as const;
export const AVISO_ALCANCE = "Solo respondo dudas sobre cómo usar Área Técnica.";

/** Pregunta que se envía al asistente según la pantalla («¿Cómo se usa esto?»). */
export const PREGUNTAS_PANTALLA = {
  calibracion:
    "¿Cómo se usa la pantalla de calibración de la cámara y por qué es importante calibrar?",
  partido_vivo:
    "¿Cómo se usa la pantalla de control del partido en vivo y qué necesito antes de iniciar el partido?",
} as const;

export type PantallaAyuda = keyof typeof PREGUNTAS_PANTALLA;
