/**
 * Llamadas al backend de Asistencia y Reportes  —  P6.
 *
 * Endpoints bajo /api/asistencia. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/asistencia/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
