/**
 * Llamadas al backend de Visión por Computadora  —  P3.
 *
 * Endpoints bajo /api/vision. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";
import { estadoHttp } from "@/shared/lib/errors";

import type { MensajeWorker } from "@/features/analisis/types";
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

export async function obtenerCuadroCalibracion(videoId: number, tiempoS: number): Promise<{
  imagen_base64: string; tiempo_s: number; cuadro_indice: number; ancho_px: number; alto_px: number;
}> {
  const { data } = await api.get(`/vision/videos/${videoId}/cuadro`, { params: { t_s: tiempoS } });
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

/** Detectar puntos clave de la cancha automáticamente con IA (YOLO Pose). */
export async function detectarCalibracionIA(
  partidoId: number,
  archivo: Blob | File,
  largoM: number = 105,
  anchoM: number = 68,
): Promise<{
  puntos_imagen: Array<{ x: number; y: number }>;
  puntos_cancha: Array<{ x: number; y: number }>;
  puntos_detectados: number;
  puntos_inliers: number;
  error_medio_m: number | null;
  es_valida: boolean;
  matriz_h: number[][] | null;
}> {
  const fd = new FormData();
  fd.append("archivo", archivo, "calibracion.jpg");
  fd.append("largo_m", String(largoM));
  fd.append("ancho_m", String(anchoM));
  const { data } = await api.post(`/vision/partidos/${partidoId}/calibracion/detectar-ia`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
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
  try {
    const { data } = await api.post<Video>(`/vision/videos/${videoId}/procesar`, datos);
    return data;
  } catch (error) {
    if (estadoHttp(error) === 409) {
      const actual = await verVideo(videoId).catch(() => null);
      if (actual?.estado === "PROCESANDO") return actual;
    }
    throw error;
  }
}

/** CU-27 · Cancela un procesamiento en cola o en curso. */
export async function cancelarProceso(videoId: number): Promise<void> {
  await api.delete(`/vision/videos/${videoId}/procesar`);
}

/** CU-28 · Elimina un video del partido y su archivo almacenado. */
export async function eliminarVideo(videoId: number): Promise<void> {
  await api.delete(`/vision/videos/${videoId}`);
}

const TAMANO_BLOQUE_VIDEO = 1024 * 1024;

interface BloqueVideo {
  inicio: number;
  total_bytes: number;
  tipo: string;
  contenido_base64: string;
}

/** Descarga la grabación como bloques JSON autenticados para reconstruirla en el visor. */
export async function descargarArchivoVideo(
  { id, tamano_bytes }: Pick<Video, "id" | "tamano_bytes">,
  signal: AbortSignal,
  onProgreso: (porcentaje: number) => void,
): Promise<Blob> {
  if (tamano_bytes <= 0) throw new Error("El video está vacío.");

  const partes: BlobPart[] = [];
  const ruta = `/vision/videos/${id}/archivo/bloque`;
  let tipo = "";
  for (let inicio = 0; inicio < tamano_bytes; inicio += TAMANO_BLOQUE_VIDEO) {
    const cantidad = Math.min(TAMANO_BLOQUE_VIDEO, tamano_bytes - inicio);
    const pedir = () =>
      api.get<BloqueVideo>(ruta, { params: { inicio, cantidad }, signal });
    const { data } = await pedir().catch((error: unknown) => {
      const estado = estadoHttp(error);
      if (signal.aborted || (estado !== undefined && estado < 500)) throw error;
      return pedir();
    });
    const binario = atob(data.contenido_base64);
    if (data.inicio !== inicio || data.total_bytes !== tamano_bytes || binario.length !== cantidad) {
      throw new Error("La descarga del video quedó incompleta.");
    }
    const bytes = new Uint8Array(cantidad);
    for (let i = 0; i < cantidad; i++) bytes[i] = binario.charCodeAt(i);
    partes.push(bytes);
    tipo = data.tipo;
    onProgreso(Math.floor(((inicio + cantidad) / tamano_bytes) * 100));
  }

  return new Blob(partes, { type: tipo });
}

/** Inicia la transmisión sincronizada a 5 Hz para acompañar al video o cámara en vivo. */
export async function iniciarTransmisionVivoPartido(
  partidoId: number,
  tInicioS = 0,
  duracionS = 90,
  videoId?: number | null,
): Promise<{ ok: boolean; partido_id: number; video_id?: number | null; duracion_s: number }> {
  const params: Record<string, number> = {
    t_inicio_s: tInicioS,
    duracion_s: duracionS,
  };
  if (videoId) {
    params.video_id = videoId;
  }
  const { data } = await api.post<{ ok: boolean; partido_id: number; video_id?: number | null; duracion_s: number }>(
    `/vision/partidos/${partidoId}/transmitir-vivo`,
    null,
    { params },
  );
  return data;
}

/** Pausa la transmisión sincronizada para congelar el radar 2D cuando el video se pausa. */
export async function pausarTransmisionVivoPartido(
  partidoId: number,
): Promise<{ ok: boolean; partido_id: number; estado: string }> {
  const { data } = await api.post<{ ok: boolean; partido_id: number; estado: string }>(
    `/vision/partidos/${partidoId}/pausar-vivo`,
  );
  return data;
}

/** CU-24, CU-40, CU-41 · Descargar telemetría persistida del video para sincronización directa sin retardo. */
export async function obtenerMuestrasVideo(videoId: number, signal?: AbortSignal): Promise<MensajeWorker[]> {
  const { data } = await api.get<MensajeWorker[]>(`/vision/videos/${videoId}/muestras`, { signal });
  return data;
}

/** CU-24, CU-40 · Enviar fotograma en vivo (webcam o video local) para inferencia instantánea de YOLO + Color. */
export async function analizarCuadroEnVivo(
  blob: Blob,
  colorLocal: string,
  colorRival: string,
  partidoId = 1,
  tActual = 0,
): Promise<MensajeWorker> {
  const formData = new FormData();
  formData.append("archivo", blob, "cuadro.jpg");
  formData.append("color_local", colorLocal);
  formData.append("color_rival", colorRival);
  formData.append("partido_id", String(partidoId));
  formData.append("t_actual", String(tActual));

  const { data } = await api.post<MensajeWorker>("/vision/vivo/analizar-cuadro", formData);
  return data;
}

