/**
 * Llamadas al backend de Asistencia y Reportes  —  P6.
 *
 * Endpoints bajo /api/asistencia. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import type { Partido } from "@/features/deportivo";
import { api } from "@/shared/api/client";

import type {
  OpcionValoracion,
  Recomendacion,
  Regla,
  ReglaCrear,
  ReglaEditar,
  ResultadoPrueba,
  Valoracion,
} from "./types";

export async function ping() {
  const { data } = await api.get("/asistencia/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-50: como máximo 3 activas, priorizadas (el servidor ya las ordena). */
export async function listarRecomendaciones(partidoId: number): Promise<Recomendacion[]> {
  const { data } = await api.get<Recomendacion[]>(
    `/asistencia/partidos/${partidoId}/recomendaciones`,
    { params: { solo_activas: true } },
  );
  return data;
}

/** T-090: el cliente la mostró por primera vez. Idempotente. */
export async function marcarVista(recomendacionId: number): Promise<Recomendacion> {
  const { data } = await api.post<Recomendacion>(
    `/asistencia/recomendaciones/${recomendacionId}/vista`,
  );
  return data;
}

/** Cuerpo de la valoración para cada opción de la tarjeta (T-091). */
export function cuerpoValoracion(opcion: OpcionValoracion, comentario: string): Valoracion {
  return {
    util: opcion === "UTIL" ? true : opcion === "NO_UTIL" ? false : null,
    aplicada: opcion === "APLICADA",
    comentario: comentario.trim(),
  };
}

/** CU-51: útil, no útil o aplicada, con comentario opcional. */
export async function valorarRecomendacion(
  recomendacionId: number,
  opcion: OpcionValoracion,
  comentario: string,
): Promise<Recomendacion> {
  const { data } = await api.post<Recomendacion>(
    `/asistencia/recomendaciones/${recomendacionId}/valorar`,
    cuerpoValoracion(opcion, comentario),
  );
  return data;
}

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

/** CU-53: registra o actualiza el token FCM del navegador actual. */
export async function registrarDispositivoPush(
  instalacionId: string,
  token: string,
  plataforma: "WEB" | "ANDROID" | "IOS" = "WEB",
): Promise<void> {
  await api.post("/asistencia/dispositivos", {
    instalacion_id: instalacionId,
    token,
    plataforma,
  });
}
