/**
 * Llamadas al backend de Visión por Computadora  —  P3.
 *
 * Endpoints bajo /api/vision. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type {
  Calibracion,
  CalibracionGuardar,
  ErrorCalibracion,
  Modelo,
  ModeloCrear,
} from "./types";

export async function ping() {
  const { data } = await api.get("/vision/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-19 · Obtener la calibración vigente de un partido. */
export async function obtenerCalibracion(partidoId: number): Promise<Calibracion> {
  const { data } = await api.get<Calibracion>(`/vision/partidos/${partidoId}/calibracion`);
  return data;
}

/** CU-19, CU-20 · Guardar o actualizar (upsert) la calibración y medidas de cancha. */
export async function guardarCalibracion(
  partidoId: number,
  datos: CalibracionGuardar,
): Promise<Calibracion> {
  const { data } = await api.post<Calibracion>(`/vision/partidos/${partidoId}/calibracion`, datos);
  return data;
}

/**
 * CU-21 · Calcular el error de reproyección SIN guardar nada (cualquier usuario
 * autenticado). `signal` permite cancelar la petición si el cuerpo ya cambió.
 */
export async function validarCalibracion(
  partidoId: number,
  datos: CalibracionGuardar,
  signal?: AbortSignal,
): Promise<ErrorCalibracion> {
  const { data } = await api.post<ErrorCalibracion>(
    `/vision/partidos/${partidoId}/calibracion/validar`,
    datos,
    { signal },
  );
  return data;
}

/** CU-29 · Listar las versiones del modelo registradas en el club, más nueva primero. */
export async function listarModelos(): Promise<Modelo[]> {
  const { data } = await api.get<Modelo[]>("/vision/modelos");
  return data;
}

/** CU-29 · Registrar una versión ya entrenada (nunca activa por defecto). */
export async function registrarModelo(datos: ModeloCrear): Promise<Modelo> {
  const { data } = await api.post<Modelo>("/vision/modelos", datos);
  return data;
}

/** CU-29 · Activar una versión; el backend desactiva cualquier otra del mismo club. */
export async function activarModelo(modeloId: number): Promise<Modelo> {
  const { data } = await api.post<Modelo>(`/vision/modelos/${modeloId}/activar`);
  return data;
}