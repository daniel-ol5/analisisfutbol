/** Tipos del dominio de Asistencia y Reportes  —  P6 · CU-49 … CU-58.
 *
 * Escritos a mano desde docs/api/openapi.json (esquemas Recomendacion,
 * DatoSoporte y Valoracion) y docs/api/websockets.md (mensaje `recomendacion`).
 */

export type Prioridad = "CRITICA" | "ALTA" | "MEDIA" | "BAJA";

export type EstadoRecomendacion = "PENDIENTE" | "VISTA" | "APLICADA" | "DESCARTADA";

/** Cifra real que disparó la regla: el valor medido contra el umbral de la condición. */
export interface DatoSoporte {
  metrica: string;
  valor: number;
  umbral: number | null;
}

/** CU-50. GET /asistencia/partidos/{id}/recomendaciones y mensaje `recomendacion` de /vivo. */
export interface Recomendacion {
  id: number;
  partido_id: number;
  regla_id: number;
  t: number;
  minuto: number;
  mensaje: string;
  justificacion: string;
  prioridad: Prioridad;
  datos_soporte: DatoSoporte[];
  estado: EstadoRecomendacion;
  util: boolean | null;
  comentario: string | null;
  vista_en: string | null;
}

/** CU-51. Cuerpo de POST /asistencia/recomendaciones/{id}/valorar. */
export interface Valoracion {
  util: boolean | null;
  aplicada: boolean;
  comentario: string;
}

/** Lo que el usuario eligió en la tarjeta (T-091). */
export type OpcionValoracion = "UTIL" | "NO_UTIL" | "APLICADA";

// ---------- CU-49, CU-54 Reglas tácticas (T-092) ----------

/**
 * Expresión que evalúa el motor: una comparación `{"<": ["altura_linea_m", 22]}`
 * o un grupo `{"y": [...]}` / `{"o": [...]}`. Ver `backend/app/asistencia/motor.py`.
 */
export type Condicion = Record<string, unknown[]>;

export interface ReglaCrear {
  nombre: string;
  condicion: Condicion;
  plantilla_mensaje: string;
  plantilla_justificacion: string;
  prioridad: Prioridad;
  /** Segundos de partido entre dos recomendaciones de la misma regla (30 a 3600). */
  cooldown_s: number;
  activa: boolean;
}

export interface Regla extends ReglaCrear {
  id: number;
  /** null: regla global del sistema. Solo se puede activar o desactivar, y vale solo para el club. */
  club_id: number | null;
}

/** PATCH: solo se cambia lo enviado. De una regla global, solo `activa`. */
export type ReglaEditar = Partial<ReglaCrear>;

export interface ResultadoPrueba {
  disparos: number;
  /** Minuto de partido de cada disparo, en orden. */
  minutos: number[];
  /** Evaluaciones hechas (una cada 5 s con posiciones guardadas). 0: el partido no tiene datos. */
  evaluaciones: number;
}
