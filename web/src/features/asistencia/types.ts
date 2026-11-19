/** Tipos del dominio de Asistencia y Reportes  —  P6 · CU-49 … CU-58. */

// ---------- CU-49, CU-54 Reglas tácticas ----------

export type Prioridad = "CRITICA" | "ALTA" | "MEDIA" | "BAJA";

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
