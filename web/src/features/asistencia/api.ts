/**
 * Llamadas al backend de Asistencia y Reportes  —  P6.
 *
 * Endpoints bajo /api/asistencia. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";
import type { Recomendacion, ReglaTactica } from "./types";

import type { Partido } from "@/features/deportivo";

import type { Regla, ReglaCrear, ReglaEditar, ResultadoPrueba } from "./types";

export async function ping() {
  const { data } = await api.get("/asistencia/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

export async function listarRecomendaciones(partidoId: number): Promise<Recomendacion[]> {
  const { data } = await api.get<Recomendacion[]>(`/asistencia/partidos/${partidoId}/recomendaciones`);
  return data;
}

export async function listarReglas(): Promise<ReglaTactica[]> {
  const { data } = await api.get<ReglaTactica[]>("/asistencia/reglas");
// ---------- CU-54 Catálogo de reglas (T-092) ----------

/** Reglas globales y propias del club; `activa` es la activación para el club. */
export async function listarReglas(): Promise<Regla[]> {
  const { data } = await api.get<Regla[]>("/asistencia/reglas");
  return data;
}

/** Regla propia del club (ADMIN o DT). 422 si usa una métrica que el motor no produce. */
export async function crearRegla(datos: ReglaCrear): Promise<Regla> {
  const { data } = await api.post<Regla>("/asistencia/reglas", datos);
  return data;
}

/**
 * Edita una regla propia, o activa/desactiva una global solo para el club.
 * Surte efecto en la siguiente evaluación del motor, sin desplegar.
 */
export async function editarRegla(reglaId: number, datos: ReglaEditar): Promise<Regla> {
  const { data } = await api.patch<Regla>(`/asistencia/reglas/${reglaId}`, datos);
  return data;
}

/** Reproduce un partido registrado y cuenta cuántas veces se habría disparado. No guarda nada. */
export async function probarRegla(reglaId: number, partidoId: number): Promise<ResultadoPrueba> {
  const { data } = await api.post<ResultadoPrueba>(`/asistencia/reglas/${reglaId}/probar`, {
    partido_id: partidoId,
  });
  return data;
}

/** Partidos del club, para elegir contra cuál probar una regla. */
export async function listarPartidos(): Promise<Partido[]> {
  const { data } = await api.get<Partido[]>("/deportivo/partidos");
  return data;
}
