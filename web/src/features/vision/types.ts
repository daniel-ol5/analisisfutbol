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
