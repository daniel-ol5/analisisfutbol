/**
 * Llamadas al backend de Visión por Computadora  —  P3.
 *
 * Endpoints bajo /api/vision. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type { Calibracion, CalibracionGuardar } from "./types";

export async function ping() {
  const { data } = await api.get("/vision/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-19 · Obtener la calibración vigente de un partido. */
export async function obtenerCalibracion(partidoId: number): Promise<Calibracion> {
  const { data } = await api.get<Calibracion>(`/vision/partidos/${partidoId}/calibracion`);
  return data;
}

/** CU-19, CU-20 · Guardar o actualizar (upsert) la calibración y medidas de cancha. */
export async function guardarCalibracion(
  partidoId: number,
  datos: CalibracionGuardar,
): Promise<Calibracion> {
  const { data } = await api.post<Calibracion>(`/vision/partidos/${partidoId}/calibracion`, datos);
  return data;
}
