/** Tipos del dominio de Visión por Computadora  —  P3 · CU-18 … CU-29. */

/** Coordenada 2D: píxeles en `puntos_imagen`, metros en `puntos_cancha`. */
export interface Punto {
  x: number;
  y: number;
}

/** Cuerpo de `POST /vision/partidos/{partido_id}/calibracion` (CU-19, CU-20). */
export interface CalibracionGuardar {
  puntos_imagen: Punto[];
  puntos_cancha: Punto[];
  largo_m?: number;
  ancho_m?: number;
  coef_distorsion?: number[] | null;
}

/** Respuesta de `GET` y `POST /vision/partidos/{partido_id}/calibracion`. */
export interface Calibracion {
  id: number;
  partido_id: number;
  largo_m: number;
  ancho_m: number;
  puntos_imagen: Punto[];
  puntos_cancha: Punto[];
  matriz_h: number[][] | null;
  error_medio_m: number | null;
  error_max_m: number | null;
  valida: boolean;
  coef_distorsion: number[] | null;
  creada_en: string;
}

/**
 * Respuesta de `POST /vision/partidos/{partido_id}/calibracion/validar` (CU-21).
 * Declarado para el punto de extensión de T-031; T-030 no invoca `/validar`.
 */
export interface ErrorCalibracion {
  error_medio_m: number;
  error_max_m: number;
  /** Índice base 0 sobre la lista de puntos enviada del punto con mayor residual. */
  punto_peor: number;
  valida: boolean;
  mensaje: string;
}

/** Hito predefinido sobre el plano de la cancha en metros. */
export interface HitoCancha {
  id: string;
  nombre: string;
  nombreCorto: string;
  x: number;
  y: number;
}

/** Par apareado `(punto_imagen, punto_cancha)` en el estado local de marcado. */
export interface ParCalibracion {
  id: string;
  /** Si proviene de la plantilla, guarda el id del hito; `null` si fue clic libre en cancha. */
  hitoId: string | null;
  etiqueta: string;
  /** Coordenadas en píxeles reales de la imagen original (`naturalWidth` × `naturalHeight`). */
  imagen: Punto;
  /** Coordenadas en metros sobre el plano de la cancha (`0..largo_m` × `0..ancho_m`). */
  cancha: Punto;
}

// ---------- CU-29 Versionado de modelos ----------

export type TipoModelo = "DETECCION" | "POSE";

/** Cuerpo de `POST /vision/modelos` (CU-29). */
export interface ModeloCrear {
  nombre: string;
  version: string;
  tipo: TipoModelo;
  /** El backend exige https (el worker la descarga sin autenticación propia). */
  archivo_url: string;
  map50_jugador?: number | null;
  map50_balon?: number | null;
  idf1?: number | null;
  notas?: string;
}

/** Respuesta de `GET /vision/modelos` y `POST /vision/modelos`. */
export interface Modelo extends ModeloCrear {
  id: number;
  /** A lo sumo una versión activa por club; la usa el worker en el siguiente procesamiento. */
  activo: boolean;
  entrenado_en: string;
  /** Última vez que se activó. */
  activado_en?: string | null;
  /** T-064: por qué se activó aunque tuviera métricas peores (volver atrás). */
  motivo_activacion?: string | null;
}

/**
 * Cuerpo opcional de `POST /vision/modelos/{id}/activar` (T-064). Una versión con
 * métricas peores que la activa se rechaza (409) salvo que se fuerce con un motivo.
 */
export interface ActivarModelo {
  forzar: boolean;
  motivo: string;
}

// ---------- CU-27, CU-28 Video del partido (T-060, T-061, T-062) ----------

export type EstadoVideo = "CARGANDO" | "SUBIDO" | "PROCESANDO" | "PROCESADO" | "ERROR";

/** Cuerpo de `POST /vision/partidos/{id}/videos`: se declara el archivo sin enviarlo. */
export interface VideoIniciar {
  nombre: string;
  tipo: string;
  tamano_bytes: number;
}

/** Respuesta de los endpoints de video. */
export interface Video {
  id: number;
  partido_id: number;
  modelo_id: number | null;
  archivo_url: string;
  nombre: string;
  tipo: string;
  tamano_bytes: number;
  /** Para retomar una carga cortada: el siguiente trozo empieza en este byte. */
  bytes_recibidos: number;
  duracion_s: number | null;
  fps: number | null;
  resolucion: string | null;
  estado: EstadoVideo;
  /** Progreso del PROCESAMIENTO, no de la carga. */
  progreso_pct: number;
  /** Cuándo un worker empezó a procesarlo; null mientras espera en cola. */
  iniciado_en: string | null;
  /** HU-25: null en cola o sin avance, 0 al terminar. */
  tiempo_restante_s: number | null;
  color_propio?: string | null;
  color_rival?: string | null;
  mensaje_error: string | null;
  creado_en: string;
  procesado_en: string | null;
}

/** Cuerpo de `POST /vision/videos/{id}/procesar`. */
export interface LanzarProceso {
  modelo_id?: number | null;
  /** Camiseta del equipo propio, `#RRGGBB`; si se omite, se usa la del club. */
  color_propio?: string | null;
  /** Camiseta del rival, `#RRGGBB`; sin ella el worker separa los equipos por K-means. */
  color_rival?: string | null;
}
