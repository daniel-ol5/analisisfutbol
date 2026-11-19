/** Recomendaciones de ejemplo para las pruebas (T-090, T-091). */
import type { Prioridad, Recomendacion } from "./types";

export function rec(
  id: number,
  prioridad: Prioridad,
  extra: Partial<Recomendacion> = {},
): Recomendacion {
  return {
    id,
    partido_id: 42,
    regla_id: id,
    t: 100 + id,
    minuto: 10,
    mensaje: `Recomendación ${id}`,
    justificacion: "",
    prioridad,
    datos_soporte: [],
    estado: "PENDIENTE",
    util: null,
    comentario: null,
    vista_en: null,
    ...extra,
  };
}
