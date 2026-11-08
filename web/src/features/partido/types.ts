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
