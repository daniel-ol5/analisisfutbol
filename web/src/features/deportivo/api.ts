/**
 * Llamadas al backend de Gestión Deportiva  —  P2.
 *
 * Endpoints bajo /api/deportivo. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/deportivo/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
