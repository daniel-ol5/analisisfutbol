/** Tipos del dominio de Gestión Deportiva  —  P2 · CU-09 … CU-17. */

export interface Equipo {
  id: number;
  club_id: number;
  nombre: string;
  categoria: string;
  temporada: string;
  color_local: string;
  color_visitante: string;
  color_arquero: string;
  activo: boolean;
  jugadores: number;
}

export interface EquipoCrear {
  nombre: string;
  categoria?: string;
  temporada?: string;
  color_local?: string;
  color_visitante?: string;
  color_arquero?: string;
}

export interface EquipoEditar {
  nombre?: string;
  categoria?: string;
  temporada?: string;
  color_local?: string;
  color_visitante?: string;
  color_arquero?: string;
  activo?: boolean;
}

export interface AvisoColores {
  hay_riesgo: boolean;
  distancia_hsv: number;
  mensaje: string;
}

export type Posicion = "ARQ" | "DEF" | "MED" | "DEL";
export type PieHabil = "IZQ" | "DER" | "AMBOS";

export const ETIQUETAS_POSICION: Record<Posicion, string> = {
  ARQ: "Arquero",
  DEF: "Defensor",
  MED: "Mediocampista",
  DEL: "Delantero",
};

export const ETIQUETAS_PIE: Record<PieHabil, string> = {
  IZQ: "Izquierdo",
  DER: "Derecho",
  AMBOS: "Ambos",
};

export interface Jugador {
  id: number;
  equipo_id: number;
  nombre: string;
  apellido: string;
  dorsal: number;
  posicion: Posicion;
  pie_habil: PieHabil;
  altura_cm: number;
  peso_kg: number | null;
  fecha_nacimiento: string | null;
  activo: boolean;
}

export interface JugadorCrear {
  equipo_id: number;
  nombre: string;
  apellido: string;
  dorsal: number;
  posicion?: Posicion;
  pie_habil?: PieHabil;
  altura_cm: number;
  peso_kg?: number | null;
  fecha_nacimiento?: string | null;
}

export interface JugadorEditar {
  nombre?: string;
  apellido?: string;
  dorsal?: number;
  posicion?: Posicion;
  pie_habil?: PieHabil;
  altura_cm?: number;
  peso_kg?: number | null;
  fecha_nacimiento?: string | null;
  activo?: boolean;
}

export type OrdenJugadores = "dorsal" | "posicion" | "apellido";

/** CU-12: resultado de validar o importar una fila del CSV de plantel. */
export interface FilaImportacion {
  fila: number;
  datos: Record<string, string>;
  error: string | null;
}

/** CU-12: resumen de la vista previa o la importación confirmada del plantel. */
export interface ResultadoImportacion {
  total: number;
  importadas: number;
  con_error: number;
  detalle: FilaImportacion[];
}

/**
 * Convierte color hexadecimal #RRGGBB a HSV (H: 0..360, S: 0..100, V: 0..100).
 * Espejo del cálculo del backend para feedback en tiempo real en la UI.
 */
export function hexAHsv(hexColor: string): [number, number, number] | null {
  const clean = hexColor.trim().replace(/^#/, "");
  if (!/^[0-9A-Fa-f]{6}$/.test(clean)) return null;

  const r = parseInt(clean.substring(0, 2), 16) / 255.0;
  const g = parseInt(clean.substring(2, 4), 16) / 255.0;
  const b = parseInt(clean.substring(4, 6), 16) / 255.0;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  let h = 0;
  if (delta > 0) {
    if (max === r) {
      h = ((g - b) / delta) % 6;
    } else if (max === g) {
      h = (b - r) / delta + 2;
    } else {
      h = (r - g) / delta + 4;
    }
    h = Math.round(h * 60);
    if (h < 0) h += 360;
  }

  const s = max === 0 ? 0 : (delta / max) * 100;
  const v = max * 100;

  return [h, s, v];
}

/**
 * Calcula la distancia euclidiana en el espacio cilíndrico HSV.
 * Distancia < 40 se considera riesgosa para visión artificial.
 */
export function calcularDistanciaHsv(hex1: string, hex2: string): number | null {
  const hsv1 = hexAHsv(hex1);
  const hsv2 = hexAHsv(hex2);
  if (!hsv1 || !hsv2) return null;

  const [h1, s1, v1] = hsv1;
  const [h2, s2, v2] = hsv2;

  const rad1 = (h1 * Math.PI) / 180;
  const rad2 = (h2 * Math.PI) / 180;

  const x1 = s1 * Math.cos(rad1);
  const y1 = s1 * Math.sin(rad1);
  const z1 = v1;

  const x2 = s2 * Math.cos(rad2);
  const y2 = s2 * Math.sin(rad2);
  const z2 = v2;

  const dist = Math.sqrt(Math.pow(x1 - x2, 2) + Math.pow(y1 - y2, 2) + Math.pow(z1 - z2, 2));

  return Math.round(dist * 100) / 100;
}

// ---------- CU-17 · Alineación y formación (T-051) ----------

export type Formacion = "4-3-3" | "4-4-2" | "4-2-3-1" | "3-5-2";

export const FORMACIONES: readonly Formacion[] = ["4-3-3", "4-4-2", "4-2-3-1", "3-5-2"];

/**
 * Coordenadas relativas, mismos ejes que el tracking: `pos_x` es el porcentaje
 * del largo (0 = arco propio, 100 = arco rival) y `pos_y` el del ancho
 * (0 = banda izquierda, 100 = banda derecha, mirando al arco rival).
 */
export interface JugadorAlineado {
  jugador_id: number;
  es_titular: boolean;
  es_capitan: boolean;
  pos_x: number;
  pos_y: number;
  minuto_entra?: number | null;
  minuto_sale?: number | null;
}

/** Cuerpo de `PUT /deportivo/partidos/{id}/alineacion`. */
export interface AlineacionGuardar {
  formacion: Formacion;
  jugadores: JugadorAlineado[];
}

export interface JugadorAlineadoOut extends JugadorAlineado {
  nombre: string;
  apellido: string;
  dorsal: number;
  posicion: Posicion;
}

/** Respuesta de `GET` y `PUT /deportivo/partidos/{id}/alineacion`. */
export interface Alineacion {
  id: number;
  partido_id: number;
  formacion: Formacion;
  /** Primero los titulares y después los suplentes, cada grupo por dorsal. */
  jugadores: JugadorAlineadoOut[];
}
