/**
 * Llamadas al backend de Asistencia y Reportes  —  P6.
 *
 * Endpoints bajo /api/asistencia. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";
import type { Recomendacion, ReglaTactica } from "./types";

export async function ping() {
  const { data } = await api.get("/asistencia/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

export async function listarRecomendaciones(partidoId: number): Promise<Recomendacion[]> {
  const { data } = await api.get<Recomendacion[]>(`/asistencia/partidos/${partidoId}/recomendaciones`);
  return data;
}

export async function listarReglas(): Promise<ReglaTactica[]> {
  const { data } = await api.get<ReglaTactica[]>("/asistencia/reglas");
  return data;
}
