/**
 * Llamadas al backend de Seguridad y Administración  —  P1.
 *
 * Endpoints bajo /api/seguridad. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/seguridad/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
