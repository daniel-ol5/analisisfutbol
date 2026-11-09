/**
 * Llamadas HTTP del módulo de Operación del Partido (CU-30, CU-31, T-068).
 */
import { api } from "@/shared/api/client";

import type {
  AsignarTrackPayload,
  DescuentoPayload,
  EstadoEnVivo,
  IniciarPartidoPayload,
  JugadorPlantelPartido,
  ResumenPartidoControl,
  TrackDetectado,
} from "./types";

export async function obtenerEstadoPartido(partidoId: number): Promise<EstadoEnVivo> {
  const { data } = await api.get<EstadoEnVivo>(`/partido/${partidoId}/estado`);
  return data;
}

export async function iniciarPartido(
  partidoId: number,
  cuerpo: IniciarPartidoPayload,
): Promise<EstadoEnVivo> {
  const { data } = await api.post<EstadoEnVivo>(`/partido/${partidoId}/iniciar`, cuerpo);
  return data;
}

export async function entretiempoPartido(partidoId: number): Promise<EstadoEnVivo> {
  const { data } = await api.post<EstadoEnVivo>(`/partido/${partidoId}/entretiempo`);
  return data;
}

export async function registrarDescuentoPartido(
  partidoId: number,
  cuerpo: DescuentoPayload,
): Promise<EstadoEnVivo> {
  const { data } = await api.post<EstadoEnVivo>(`/partido/${partidoId}/descuento`, cuerpo);
  return data;
}

export async function finalizarPartido(partidoId: number): Promise<EstadoEnVivo> {
  const { data } = await api.post<EstadoEnVivo>(`/partido/${partidoId}/finalizar`);
  return data;
}

export async function listarPartidosControl(): Promise<ResumenPartidoControl[]> {
  const { data } = await api.get<ResumenPartidoControl[]>("/deportivo/partidos");
  return data;
}

export async function obtenerPartidoControl(partidoId: number): Promise<ResumenPartidoControl> {
  const { data } = await api.get<ResumenPartidoControl>(`/deportivo/partidos/${partidoId}`);
  return data;
}

export async function listarTracksPartido(
  partidoId: number,
  soloActivos = true,
): Promise<TrackDetectado[]> {
  const { data } = await api.get<TrackDetectado[]>(`/partido/${partidoId}/tracks`, {
    params: { solo_activos: soloActivos },
  });
  return data;
}

export async function asignarTrackPartido(
  partidoId: number,
  trackId: number,
  cuerpo: AsignarTrackPayload,
): Promise<TrackDetectado> {
  const { data } = await api.put<TrackDetectado>(`/partido/${partidoId}/tracks/${trackId}`, cuerpo);
  return data;
}

export async function listarJugadoresPlantelPartido(
  equipoId: number,
): Promise<JugadorPlantelPartido[]> {
  const { data } = await api.get<JugadorPlantelPartido[]>(
    `/deportivo/equipos/${equipoId}/jugadores`,
    {
      params: { activos: true, orden: "dorsal" },
    },
  );
  return data;
}
