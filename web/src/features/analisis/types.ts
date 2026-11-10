/** Tipos del dominio de Análisis Táctico  —  P5 · CU-40 … CU-48. */

export type EquipoDetectado = "LOCAL" | "VISITANTE" | "ARBITRO" | "DESCONOCIDO";

export interface PosicionDetectada {
  /** Identificador de tracking (ByteTrack) */
  tid: number;
  /** Equipo al que pertenece la detección */
  equipo: EquipoDetectado;
  /** Coordenada X en metros sobre el largo de la cancha (0 .. 105 m) */
  x: number;
  /** Coordenada Y en metros sobre el ancho de la cancha (0 .. 68 m) */
  y: number;
  /** Nivel de confianza de la detección (0 .. 1) */
  conf: number;
  /** Número de dorsal si está asignado */
  dorsal?: number | null;
  /** Bounding box [x1, y1, x2, y2] en porcentaje (0..100) sobre el video */
  bbox?: [number, number, number, number] | null;
}

export interface IndicadorCalidad {
  /** Indica si el worker de visión o emisor simulado está transmitiendo */
  worker_conectado: boolean;
  /** Cuadros por segundo del procesamiento (esperado ~5 Hz) */
  fps: number;
  /** Cantidad de jugadores detectados en el frame actual */
  jugadores_detectados: number;
  /** Si el balón fue detectado en el frame actual */
  balon_visible: boolean;
  /** Retraso en segundos desde la captura hasta la difusión */
  retraso_s: number;
  /** True si hay menos de 16 jugadores por más de 10 s, o balón perdido > 15 s */
  degradado: boolean;
  /** Motivo de la degradación, si aplica */
  motivo?: string | null;
}

export interface MensajeWorker {
  /** Identificador del partido */
  partido: number;
  /** Segundos transcurridos desde el inicio del partido */
  t: number;
  /** Posiciones de los jugadores detectados */
  jugadores: PosicionDetectada[];
  /** Posición del balón (null si no es visible) */
  balon?: PosicionDetectada | null;
  /** Métricas de calidad y salud del flujo de visión */
  calidad: IndicadorCalidad;
}

export type MensajeWebSocketVivo =
  | { tipo: "listo"; partido: number }
  | { tipo: "pong" }
  | { tipo: "posiciones"; datos: MensajeWorker }
  | { tipo: "error"; detalle?: unknown; invalidos_seguidos?: number };

export type EstadoConexion =
  | "desconectado"
  | "conectando"
  | "conectado"
  | "reconectando"
  | "error";

export interface PuntoTrayectoria {
  x: number;
  y: number;
  t: number;
}

export interface ConfiguracionPlano2D {
  mostrarEtiquetas: "dorsal" | "tid" | "ninguno";
  mostrarEstelaBalon: boolean;
  altoContraste: boolean;
  invertirLados: boolean;
}

export interface EstadoPartidoVivo {
  partidoId: number;
  estadoConexion: EstadoConexion;
  ultimoMensaje: MensajeWorker | null;
  posesionLocalPct: number;
  posesionVisitantePct: number;
  estelaBalon: PuntoTrayectoria[];
  error: string | null;
}

// ==========================================
// CU-44 · Mapas de calor dinámicos (T-079)
// ==========================================

export type AlcanceMapaCalor = "equipo" | "linea" | "jugador";

export interface CeldaCalor {
  x: number;
  y: number;
  valor: number;
}

export interface MapaCalor {
  partido_id: number;
  alcance: AlcanceMapaCalor;
  referencia_id: number | null;
  largo_m: number;
  ancho_m: number;
  celdas: CeldaCalor[];
}

export interface FiltrosMapaCalor {
  alcance: AlcanceMapaCalor;
  referencia_id?: number | null;
  desde_minuto: number;
  hasta_minuto: number;
}

