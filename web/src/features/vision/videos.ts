/**
 * Lógica de la carga y el procesamiento de video  —  CU-27, CU-28 (T-062).
 *
 * Sin React: validación del archivo, subida por trozos reanudable y formatos.
 * La subida recibe la API como parámetro para probarla sin red.
 */
import type { Partido } from "@/features/deportivo";
import { estadoHttp } from "@/shared/lib/errors";

import type { EstadoVideo, Video } from "./types";

/** Mismos formatos que valida el backend (`FORMATOS_VIDEO`). */
export const FORMATOS: Record<string, readonly string[]> = {
  ".mp4": ["video/mp4"],
  ".mov": ["video/quicktime"],
  ".mkv": ["video/x-matroska", "video/matroska"],
};

/** Para el `accept` del selector de archivos. */
export const ACEPTA = [...Object.keys(FORMATOS), ...Object.values(FORMATOS).flat()].join(",");

/** 8 MiB por trozo: si se corta la red se pierde poco, y son pocos pedidos. */
export const TAMANO_TROZO = 8 * 1024 * 1024;

/** Roles que el backend deja subir y procesar desde esta pantalla. */
export const ROLES_SUBEN: readonly string[] = ["ADMIN", "ANALISTA", "ASISTENTE"];
export const ROLES_PROCESAN: readonly string[] = ["ADMIN", "ANALISTA"];

export function extension(nombre: string): string {
  const punto = nombre.lastIndexOf(".");
  return punto <= 0 ? "" : nombre.slice(punto).toLowerCase();
}

/**
 * HU-24 · Criterio 1: el formato se valida ANTES de subir nada. Devuelve el
 * motivo del rechazo, o null si el archivo sirve. El backend vuelve a validar.
 */
export function problemaDelArchivo(archivo: {
  name: string;
  type: string;
  size: number;
}): string | null {
  const ext = extension(archivo.name);
  const soportados = Object.keys(FORMATOS)
    .map((e) => e.slice(1).toUpperCase())
    .join(", ");
  if (!(ext in FORMATOS)) {
    return `Formato no soportado (${ext || "sin extensión"}). Se aceptan ${soportados}.`;
  }
  const tipo = archivo.type.toLowerCase();
  if (tipo && tipo !== "application/octet-stream" && !FORMATOS[ext].includes(tipo)) {
    return `El archivo dice ser ${tipo}, que no corresponde a un video ${ext.slice(1).toUpperCase()}.`;
  }
  if (archivo.size === 0) return "El archivo está vacío.";
  return null;
}

/** Al retomar una carga, el archivo elegido tiene que ser el mismo que se empezó a subir. */
export function esElMismoArchivo(archivo: { name: string; size: number }, video: Video): boolean {
  return archivo.name === video.nombre && archivo.size === video.tamano_bytes;
}

// ---------------- Subida por trozos ----------------

export interface ApiSubida {
  enviarTrozo: (
    videoId: number,
    trozo: Blob,
    inicio: number,
    total: number,
    onBytes?: (enviados: number) => void,
    signal?: AbortSignal,
  ) => Promise<Video>;
  verVideo: (videoId: number) => Promise<Video>;
}

export interface OpcionesSubida {
  /** Bytes que ya están en el servidor más lo que va saliendo del trozo actual. */
  onProgreso?: (bytes: number) => void;
  signal?: AbortSignal;
  tamanoTrozo?: number;
  /** Reintentos seguidos ante errores de red o del servidor (5xx). */
  reintentos?: number;
  esperar?: (ms: number) => Promise<void>;
}

export class SubidaPausada extends Error {
  constructor() {
    super("Subida pausada");
  }
}

const esperarMs = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function esCancelacion(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof Error && error.name === "CanceledError");
}

/** Error que vale la pena reintentar: sin respuesta (red caída) o falla del servidor. */
function esTransitorio(error: unknown): boolean {
  const estado = estadoHttp(error);
  return estado === undefined || estado >= 500;
}

/**
 * Sube `archivo` desde donde quedó `video.bytes_recibidos` hasta el final.
 *
 * - Ante un corte de red o un 5xx reintenta con espera creciente.
 * - Ante un 409 (el servidor tiene otra cuenta, por ejemplo porque el trozo
 *   llegó pero la respuesta se perdió) pregunta el estado y sigue desde ahí.
 * - Si `signal` se aborta, lanza `SubidaPausada`: se retoma llamando de nuevo.
 *
 * Devuelve el video al terminar: SUBIDO, o ERROR si el archivo no se pudo leer.
 */
export async function subirPorTrozos(
  archivo: Blob,
  video: Video,
  api: ApiSubida,
  {
    onProgreso,
    signal,
    tamanoTrozo = TAMANO_TROZO,
    reintentos = 5,
    esperar = esperarMs,
  }: OpcionesSubida = {},
): Promise<Video> {
  const total = video.tamano_bytes;
  let actual = video;
  let fallos = 0;
  onProgreso?.(actual.bytes_recibidos);

  while (actual.estado === "CARGANDO" && actual.bytes_recibidos < total) {
    if (signal?.aborted) throw new SubidaPausada();
    const inicio = actual.bytes_recibidos;
    const trozo = archivo.slice(inicio, Math.min(inicio + tamanoTrozo, total));
    try {
      actual = await api.enviarTrozo(
        video.id,
        trozo,
        inicio,
        total,
        (enviados) => onProgreso?.(inicio + Math.min(enviados, trozo.size)),
        signal,
      );
      fallos = 0;
      onProgreso?.(actual.bytes_recibidos);
    } catch (error) {
      if (esCancelacion(error, signal)) throw new SubidaPausada();
      if (estadoHttp(error) === 409) {
        actual = await api.verVideo(video.id);
        onProgreso?.(actual.bytes_recibidos);
        continue;
      }
      if (!esTransitorio(error) || fallos >= reintentos) throw error;
      fallos += 1;
      await esperar(Math.min(1000 * 2 ** (fallos - 1), 15_000));
      // El trozo pudo haber llegado aunque la respuesta no: se pregunta antes de reenviar.
      try {
        actual = await api.verVideo(video.id);
      } catch {
        /* sigue sin red: se reintenta el mismo trozo */
      }
    }
  }
  return actual;
}

// ---------------- Procesamiento ----------------

/** Hay que consultar el estado mientras algo esté avanzando en el servidor. */
export function hayQueSeguirConsultando(videos: readonly Video[]): boolean {
  return videos.some((v) => v.estado === "PROCESANDO");
}

/** Subido y legible: se puede procesar (o reprocesar). Mismo criterio que el backend. */
export function sePuedeProcesar(video: Video): boolean {
  if (video.estado === "SUBIDO" || video.estado === "PROCESADO") return true;
  return video.estado === "ERROR" && video.duracion_s !== null;
}

export const ETIQUETA_ESTADO: Record<EstadoVideo, string> = {
  CARGANDO: "Subida incompleta",
  SUBIDO: "Listo para procesar",
  PROCESANDO: "Procesando",
  PROCESADO: "Procesado",
  ERROR: "Error",
};

// ---------------- Formatos ----------------

export function formatearBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const unidades = ["KB", "MB", "GB", "TB"];
  let valor = bytes;
  let i = -1;
  do {
    valor /= 1024;
    i += 1;
  } while (valor >= 1024 && i < unidades.length - 1);
  return `${valor.toLocaleString("es", { maximumFractionDigits: valor < 10 ? 1 : 0 })} ${unidades[i]}`;
}

/** Duración de un video: "1:32:05" o "4:07". */
export function formatearDuracion(segundos: number): string {
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = Math.floor(segundos % 60);
  const mmss = `${String(m).padStart(h ? 2 : 1, "0")}:${String(s).padStart(2, "0")}`;
  return h ? `${h}:${mmss}` : mmss;
}

/** HU-25 · Criterio 2, para leer de un vistazo: "menos de 1 min", "~12 min", "~1 h 20 min". */
export function formatearRestante(segundos: number | null): string | null {
  if (segundos === null) return null;
  if (segundos <= 0) return "terminando";
  if (segundos < 60) return "menos de 1 min";
  const minutos = Math.round(segundos / 60);
  if (minutos < 60) return `~${minutos} min`;
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return m ? `~${h} h ${m} min` : `~${h} h`;
}

/** Porcentaje de la subida, sin redondear a 100 antes de terminar. */
export function porcentajeSubida(bytes: number, total: number): number {
  if (total <= 0) return 0;
  return bytes >= total ? 100 : Math.min(99, Math.floor((100 * bytes) / total));
}

/** Partidos en los que tiene sentido un video: los jugados primero, sin cancelados. */
export function partidosParaVideo(partidos: readonly Partido[]): Partido[] {
  return partidos
    .filter((p) => p.estado !== "CANCELADO")
    .sort((a, b) => new Date(b.fecha_hora).getTime() - new Date(a.fecha_hora).getTime());
}
