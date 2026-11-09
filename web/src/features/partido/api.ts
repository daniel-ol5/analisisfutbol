/**
 * Llamadas HTTP del módulo de Operación del Partido (CU-30, CU-31, T-068).
 */
import { api } from "@/shared/api/client";

import type {
  DescuentoPayload,
  EstadoEnVivo,
  IniciarPartidoPayload,
  ResumenPartidoControl,
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
