/**
 * Llamadas al backend de Operación del Partido  —  P4.
 *
 * Endpoints bajo /api/partido. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/partido/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
