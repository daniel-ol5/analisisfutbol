/**
 * Llamadas al backend de Visión por Computadora  —  P3.
 *
 * Endpoints bajo /api/vision. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/vision/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
