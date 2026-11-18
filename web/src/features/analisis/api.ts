/**
 * Llamadas al backend de Análisis Táctico  —  P5.
 *
 * Endpoints bajo /api/analisis. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";
import type {
  FiltrosLineaTiempo,
  FiltrosMapaCalor,
  FiltrosRedPases,
  LineaTiempo,
  MapaCalor,
  MetricasMinuto,
  MetricasTacticas,
  RedPases,
} from "./types";

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

/** CU-45 · Altura de línea, amplitud y compacidad con y sin balón (T-102). */
export async function obtenerMetricasTacticas(partidoId: number): Promise<MetricasTacticas> {
  const { data } = await api.get<MetricasTacticas>(
    `/analisis/partidos/${partidoId}/metricas/tacticas`,
  );
  return data;
}

/** CU-47 · Métricas del minuto exacto de un evento (T-103). */
export async function obtenerMetricasMinuto(
  partidoId: number,
  minuto: number,
): Promise<MetricasMinuto> {
  const { data } = await api.get<MetricasMinuto>(
    `/analisis/partidos/${partidoId}/metricas/minuto/${minuto}`,
  );
  return data;
}

/** CU-47 · Cronología de eventos de cámara y manuales (T-103). */
export async function obtenerLineaTiempo(
  partidoId: number,
  filtros: FiltrosLineaTiempo = {},
): Promise<LineaTiempo> {
  const { data } = await api.get<LineaTiempo>(`/analisis/partidos/${partidoId}/linea-tiempo`, {
    params: { tipo: filtros.tipo ?? undefined, equipo: filtros.equipo ?? undefined },
  });
  return data;
}

/** CU-48 · Grafo de pases completados entre jugadores (T-103). */
export async function obtenerRedPases(
  partidoId: number,
  filtros: FiltrosRedPases,
): Promise<RedPases> {
  const { data } = await api.get<RedPases>(`/analisis/partidos/${partidoId}/red-pases`, {
    params: {
      desde_minuto: filtros.desde_minuto,
      hasta_minuto: filtros.hasta_minuto,
      equipo: filtros.equipo ?? undefined,
    },
  });
  return data;
}
