/**
 * Llamadas al backend de Visión por Computadora  —  P3.
 *
 * Endpoints bajo /api/vision. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type { Partido } from "@/features/deportivo";

import type {
  ActivarModelo,
  Calibracion,
  CalibracionGuardar,
  ErrorCalibracion,
  LanzarProceso,
  Modelo,
  ModeloCrear,
  Video,
  VideoIniciar,
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

/**
 * CU-29 · Activar una versión; el backend desactiva cualquier otra del mismo club.
 * T-064: si tiene métricas peores que la activa responde 409, salvo con `forzar` y motivo.
 */
export async function activarModelo(modeloId: number, datos?: ActivarModelo): Promise<Modelo> {
  const { data } = await api.post<Modelo>(`/vision/modelos/${modeloId}/activar`, datos);
  return data;
}

// ---------- CU-27, CU-28 Video del partido (T-062) ----------

/** CU-15 · Partidos del club, para elegir de cuál es el video. */
export async function listarPartidos(): Promise<Partido[]> {
  const { data } = await api.get<Partido[]>("/deportivo/partidos");
  return data;
}

/** CU-28 · Videos del partido, el más nuevo primero. */
export async function listarVideos(partidoId: number): Promise<Video[]> {
  const { data } = await api.get<Video[]>(`/vision/partidos/${partidoId}/videos`);
  return data;
}

/** CU-27, CU-28 · Estado de la carga y del procesamiento. */
export async function verVideo(videoId: number): Promise<Video> {
  const { data } = await api.get<Video>(`/vision/videos/${videoId}`);
  return data;
}

/** T-060 paso 1 · Declara el archivo; 415 si el formato no sirve, sin subir nada. */
export async function iniciarCarga(partidoId: number, datos: VideoIniciar): Promise<Video> {
  const { data } = await api.post<Video>(`/vision/partidos/${partidoId}/videos`, datos);
  return data;
}

/** T-060 paso 2 · Envía un trozo con `Content-Range`; `onBytes` informa lo que va saliendo. */
export async function enviarTrozo(
  videoId: number,
  trozo: Blob,
  inicio: number,
  total: number,
  onBytes?: (enviados: number) => void,
  signal?: AbortSignal,
): Promise<Video> {
  const fin = inicio + trozo.size - 1;
  const { data } = await api.put<Video>(`/vision/videos/${videoId}/contenido`, trozo, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Range": `bytes ${inicio}-${fin}/${total}`,
    },
    onUploadProgress: (e) => onBytes?.(e.loaded),
    signal,
  });
  return data;
}

/** CU-27 · Deja el video en la cola de procesamiento. */
export async function lanzarProceso(videoId: number, datos: LanzarProceso): Promise<Video> {
  const { data } = await api.post<Video>(`/vision/videos/${videoId}/procesar`, datos);
  return data;
}

/** CU-27 · Cancela un procesamiento en cola o en curso. */
export async function cancelarProceso(videoId: number): Promise<void> {
  await api.delete(`/vision/videos/${videoId}/procesar`);
}

/** Obtiene el binario del video subido para reproducirlo en el visor táctico en vivo. */
export async function descargarArchivoVideo(videoId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/vision/videos/${videoId}/archivo`, {
    responseType: "blob",
  });
  return data;
}

/** Inicia la transmisión sincronizada a 5 Hz para acompañar al video o cámara en vivo. */
export async function iniciarTransmisionVivoPartido(
  partidoId: number,
  duracionS = 90,
): Promise<{ ok: boolean; partido_id: number; duracion_s: number }> {
  const { data } = await api.post<{ ok: boolean; partido_id: number; duracion_s: number }>(
    `/vision/partidos/${partidoId}/transmitir-vivo`,
    null,
    { params: { duracion_s: duracionS } },
  );
  return data;
}
