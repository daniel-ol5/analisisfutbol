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
  calibracion_valida?: boolean | null;
  campo_visible?: number[][] | null;
  largo_m?: number;
  ancho_m?: number;
  estado_calibracion?: "SIN_REFERENCIA" | "VERIFICADA" | "SIGUIENDO" | "PERDIDA" | null;
  ultimo_anclaje_t?: number | null;
  error_lineas_px?: number | null;
  lineas_imagen?: number[][][];
}

export interface MensajeWorker {
  detecciones?: { tid: number; clase: string; conf: number; bbox: number[] }[];
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
  | {
      tipo: "posesion";
      datos: { acumulado: { local_pct: number; visitante_pct: number; disputa_pct: number } };
    }
  | { tipo: "error"; detalle?: unknown; invalidos_seguidos?: number };

export type EstadoConexion = "desconectado" | "conectando" | "conectado" | "reconectando" | "error";

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

// ==========================================
// CU-45 · Métricas tácticas colectivas (T-102)
// ==========================================

export interface BloqueFase {
  /** Distancia de la última línea defensiva al arco propio, en metros */
  altura_linea_m: number | null;
  /** Ancho del equipo: distancia entre los dos jugadores más abiertos, en metros */
  amplitud_m: number | null;
  /** Área del polígono envolvente de los jugadores de campo, en m² (menos = más junto) */
  compacidad_m2: number | null;
  /** Segundos de partido sobre los que se promedió; 0 = sin datos en la fase */
  muestras: number;
}

export interface MetricaTactica {
  equipo: "LOCAL" | "VISITANTE";
  total: BloqueFase;
  con_balon: BloqueFase;
  sin_balon: BloqueFase;
}

export interface IntervaloTactico {
  minuto_desde: number;
  minuto_hasta: number;
  local: MetricaTactica;
  visitante: MetricaTactica;
}

export interface MetricasTacticas {
  partido_id: number;
  local: MetricaTactica;
  visitante: MetricaTactica;
  intervalos: IntervaloTactico[];
}

/** Métricas de un equipo en un minuto exacto (CU-47: se filtran al elegir un evento). */
export interface MetricaEquipoMinuto {
  equipo: LadoPartido;
  posesion_pct: number;
  pases_intentados: number;
  pases_completados: number;
  distancia_m: number;
  altura_linea_m: number | null;
  amplitud_m: number | null;
  compacidad_m2: number | null;
}

export interface MetricasMinuto {
  minuto_desde: number;
  minuto_hasta: number;
  local: MetricaEquipoMinuto;
  visitante: MetricaEquipoMinuto;
  /** Tiempo con el balón lejos de todos; local + visitante + disputa = 100 */
  posesion_disputa_pct: number;
}

// ==========================================
// CU-47 · Línea de tiempo (T-103)
// ==========================================

export type TipoEventoLinea =
  | "PASE"
  | "PERDIDA"
  | "RECUPERACION"
  | "TIRO"
  | "FUERA"
  | "GOL"
  | "AMARILLA"
  | "ROJA"
  | "SUSTITUCION";
export type LadoPartido = "LOCAL" | "VISITANTE";

export interface ItemLineaTiempo {
  /** Segundos de partido: es el instante al que salta el plano 2D */
  t: number;
  minuto: number;
  tipo: TipoEventoLinea;
  equipo: LadoPartido | null;
  jugador_id: number | null;
  descripcion: string;
  /** CAMARA = inferido; MANUAL = cargado por el cuerpo técnico */
  origen: "CAMARA" | "MANUAL";
}

export interface LineaTiempo {
  partido_id: number;
  items: ItemLineaTiempo[];
}

export interface FiltrosLineaTiempo {
  tipo?: TipoEventoLinea | null;
  equipo?: LadoPartido | null;
}

// ==========================================
// CU-48 · Red de pases (T-103)
// ==========================================

export interface NodoPase {
  jugador_id: number;
  nombre: string;
  dorsal: number | null;
  equipo: LadoPartido | null;
  /** Posición media normalizada por dirección de ataque (el equipo ataca hacia +x) */
  x_medio: number;
  y_medio: number;
  /** Pases completados que envió */
  pases: number;
  /** Pases completados que recibió */
  pases_recibidos: number;
  /** Está entre los que más pases reciben de su equipo */
  mayor_recepcion: boolean;
  /** Desconectado del circuito: casi no pasa ni recibe respecto al promedio de su equipo */
  aislado: boolean;
}

export interface AristaPase {
  origen_id: number;
  destino_id: number;
  pases: number;
}

export interface RedPases {
  partido_id: number;
  desde_minuto: number;
  hasta_minuto: number;
  nodos: NodoPase[];
  aristas: AristaPase[];
}

export interface FiltrosRedPases {
  desde_minuto: number;
  hasta_minuto: number;
  equipo?: LadoPartido | null;
}
