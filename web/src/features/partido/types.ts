/**
 * Tipos del módulo de Operación del Partido en vivo (CU-30, CU-31, T-068).
 *
 * Reflejan el contrato congelado de `backend/app/partido/schemas.py` y el
 * listado básico de `GET /deportivo/partidos` sin importar de otras features.
 */

export type DireccionAtaque = "IZQ" | "DER";

export type EstadoPartidoAgenda = "PROGRAMADO" | "EN_CURSO" | "FINALIZADO" | "CANCELADO";

export interface IniciarPartidoPayload {
  ataca_hacia: DireccionAtaque;
}

export interface DescuentoPayload {
  minutos: number;
}

export interface IndicadorCalidad {
  worker_conectado: boolean;
  fps: number;
  jugadores_detectados: number;
  balon_visible: boolean;
  retraso_s: number;
  degradado: boolean;
  motivo: string | null;
}

/**
 * Estado del partido en vivo devuelto por `GET /partido/{id}/estado` y por los
 * endpoints de control (`iniciar`, `entretiempo`, `descuento`, `finalizar`).
 *
 * TODO: `EstadoEnVivo` en el contrato actual no expone `descuento_1_min` ni
 * `descuento_2_min`; por eso los minutos de descuento registrados solo se
 * muestran durante la sesión activa en memoria.
 */
export interface EstadoEnVivo {
  partido_id: number;
  parte: number;
  minuto: number;
  segundo: number;
  en_curso: boolean;
  goles_favor: number;
  goles_contra: number;
  posesion_local_pct: number | null;
  calidad: IndicadorCalidad;
}

/**
 * Proyección propia de `Partido` (`GET /deportivo/partidos` y
 * `GET /deportivo/partidos/{id}`) usada por el selector de partido y para
 * conocer `estado` y `ataca_hacia` sin importar desde `features/deportivo`.
 */
export interface ResumenPartidoControl {
  id: number;
  equipo_id: number;
  rival: string;
  fecha_hora: string;
  sede: string | null;
  es_local: boolean;
  estado: EstadoPartidoAgenda;
  ataca_hacia: DireccionAtaque | null;
  goles_favor: number | null;
  goles_contra: number | null;
}

/** Estados posibles del canal WebSocket `/api/partido/{id}/vivo` (Fase 2B). */
export type EstadoCanalVivo = "CONECTADO" | "RECONECTANDO" | "SIN_CONEXION" | "SESION_VENCIDA";

// ---------- CU-34, CU-35 · Asignación de identificadores (T-072) ----------

export type EquipoDetectado = "LOCAL" | "VISITANTE" | "ARBITRO" | "DESCONOCIDO";

export interface TrackDetectado {
  track_id: number;
  equipo_detectado: EquipoDetectado;
  jugador_id: number | null;
  desde_t: number;
  hasta_t: number | null;
  confianza: number;
}

export interface AsignarTrackPayload {
  jugador_id: number | null;
}

/**
 * Muestra ligera de un `tid` visto en vivo (para la unión con los tramos
 * vigentes de `GET /tracks?solo_activos=true` en la Fase 2B).
 */
export interface TrackEnVivoLigero {
  tid: number;
  equipo: EquipoDetectado;
  conf: number;
  t: number;
}

/**
 * Fila resultante de unir los tramos vigentes de base de datos con los `tid`
 * vistos en vivo. Un track sin tramo vigente se muestra «Sin asignar» y sigue
 * siendo asignable con `PUT /partido/{id}/tracks/{track_id}`.
 */
export interface TrackUnificadoVista {
  track_id: number;
  equipo_detectado: EquipoDetectado;
  jugador_id: number | null;
  desde_t: number | null;
  confianza: number;
  tieneTramoVigente: boolean;
}

export type PosicionJugadorPlantel = "ARQ" | "DEF" | "MED" | "DEL";

export type PieHabilJugadorPlantel = "IZQ" | "DER" | "AMBOS";

/**
 * Proyección propia de `Jugador` (`GET /deportivo/equipos/{equipo_id}/jugadores`,
 * `backend/app/deportivo/schemas.py:91-124`) para no importar tipos desde
 * `features/deportivo`.
 */
export interface JugadorPlantelPartido {
  id: number;
  equipo_id: number;
  nombre: string;
  apellido: string;
  dorsal: number;
  posicion: PosicionJugadorPlantel;
  pie_habil: PieHabilJugadorPlantel;
  altura_cm: number;
  peso_kg: number | null;
  fecha_nacimiento: string | null;
  activo: boolean;
}
