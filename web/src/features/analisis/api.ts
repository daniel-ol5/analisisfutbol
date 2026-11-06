/**
 * Llamadas al backend de Análisis Táctico  —  P5.
 *
 * Endpoints bajo /api/analisis. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";
import type { FiltrosMapaCalor, MapaCalor } from "./types";

export async function ping() {
  const { data } = await api.get("/analisis/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/**
 * CU-44 · Mapa de calor de ocupación espacial (T-079)
 * Coordenadas normalizadas por dirección de ataque (ataca_hacia).
 */
export async function obtenerMapaCalor(
  partidoId: number,
  filtros: Partial<FiltrosMapaCalor> = {},
): Promise<MapaCalor> {
  const params = new URLSearchParams();
  if (filtros.alcance) params.append("alcance", filtros.alcance);
  if (filtros.referencia_id !== undefined && filtros.referencia_id !== null) {
    params.append("referencia_id", String(filtros.referencia_id));
  }
  if (filtros.desde_minuto !== undefined) {
    params.append("desde_minuto", String(filtros.desde_minuto));
  }
  if (filtros.hasta_minuto !== undefined) {
    params.append("hasta_minuto", String(filtros.hasta_minuto));
  }

  const { data } = await api.get<MapaCalor>(
    `/analisis/partidos/${partidoId}/mapa-calor?${params.toString()}`,
  );
  return data;
}

