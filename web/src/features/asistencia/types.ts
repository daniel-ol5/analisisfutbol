export type Prioridad = "CRITICA" | "ALTA" | "MEDIA" | "BAJA";

export interface Recomendacion {
  id: number;
  minuto: number;
  mensaje: string;
  justificacion: string;
  prioridad: Prioridad;
}

export interface ReglaTactica {
  id: number;
  nombre: string;
  prioridad: Prioridad;
  activa: boolean;
}
