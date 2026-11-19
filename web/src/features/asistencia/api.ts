/**
 * Llamadas al backend de Asistencia y Reportes  —  P6.
 *
 * Endpoints bajo /api/asistencia. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type { OpcionValoracion, Recomendacion, Valoracion } from "./types";

export async function ping() {
  const { data } = await api.get("/asistencia/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-50: como máximo 3 activas, priorizadas (el servidor ya las ordena). */
export async function listarRecomendaciones(partidoId: number): Promise<Recomendacion[]> {
  const { data } = await api.get<Recomendacion[]>(
    `/asistencia/partidos/${partidoId}/recomendaciones`,
    { params: { solo_activas: true } },
  );
  return data;
}

/** T-090: el cliente la mostró por primera vez. Idempotente. */
export async function marcarVista(recomendacionId: number): Promise<Recomendacion> {
  const { data } = await api.post<Recomendacion>(
    `/asistencia/recomendaciones/${recomendacionId}/vista`,
  );
  return data;
}

/** Cuerpo de la valoración para cada opción de la tarjeta (T-091). */
export function cuerpoValoracion(opcion: OpcionValoracion, comentario: string): Valoracion {
  return {
    util: opcion === "UTIL" ? true : opcion === "NO_UTIL" ? false : null,
    aplicada: opcion === "APLICADA",
    comentario: comentario.trim(),
  };
}

/** CU-51: útil, no útil o aplicada, con comentario opcional. */
export async function valorarRecomendacion(
  recomendacionId: number,
  opcion: OpcionValoracion,
  comentario: string,
): Promise<Recomendacion> {
  const { data } = await api.post<Recomendacion>(
    `/asistencia/recomendaciones/${recomendacionId}/valorar`,
    cuerpoValoracion(opcion, comentario),
  );
  return data;
}
