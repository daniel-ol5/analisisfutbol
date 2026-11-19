// ---------- CU-49, CU-54 Reglas tácticas ----------

export type Prioridad = "CRITICA" | "ALTA" | "MEDIA" | "BAJA";

/** Comparación o grupo de comparaciones que evalúa el motor de reglas. */
export type Condicion = Record<string, unknown[]>;

export interface ReglaCrear {
  nombre: string;
  condicion: Condicion;
  plantilla_mensaje: string;
  plantilla_justificacion: string;
  prioridad: Prioridad;
  cooldown_s: number;
  activa: boolean;
}

export interface Regla extends ReglaCrear {
  id: number;
  /** Las reglas globales tienen club_id nulo. */
  club_id: number | null;
}

export type ReglaEditar = Partial<ReglaCrear>;

export interface ResultadoPrueba {
  disparos: number;
  minutos: number[];
  evaluaciones: number;
}

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
