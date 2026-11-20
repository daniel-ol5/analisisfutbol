/** Contrato del asistente de uso (backend: app/asistente/schemas.py). */

export type Plataforma = "web" | "movil";

export interface PasoProgreso {
  clave: string;
  titulo: string;
  estado: "hecho" | "pendiente";
  ruta: string | null;
  solo_web: boolean;
  disponible: boolean;
  tu_rol_puede: boolean;
  nota: string | null;
}

export interface Progreso {
  plataforma: Plataforma;
  partido_id: number | null;
  pasos: PasoProgreso[];
  siguiente: PasoProgreso | null;
  asistente_activo: boolean;
}

export interface MensajeHistorial {
  rol: "usuario" | "asistente";
  texto: string;
}

export interface Accion {
  texto: string;
  ruta: string;
}

export interface Respuesta {
  respuesta: string;
  acciones: Accion[];
}

export interface Pregunta {
  pregunta: string;
  pantalla_actual: string;
  plataforma: Plataforma;
  historial: MensajeHistorial[];
}

/** Mensaje del chat tal como se muestra (con sus acciones, si las tiene). */
export interface MensajeChat extends MensajeHistorial {
  id: string;
  acciones?: Accion[];
}
