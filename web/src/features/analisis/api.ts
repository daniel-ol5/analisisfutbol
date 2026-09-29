/**
 * Llamadas al backend de Análisis Táctico  —  P5.
 *
 * Endpoints bajo /api/analisis. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

export async function ping() {
  const { data } = await api.get("/analisis/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}
