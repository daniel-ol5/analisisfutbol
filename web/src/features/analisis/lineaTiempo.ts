import type { ItemLineaTiempo, LadoPartido, TipoEventoLinea } from "./types";

/** Tipos inferidos por la cámara; el resto los carga el cuerpo técnico a mano. */
export const TIPOS_CAMARA: TipoEventoLinea[] = ["PASE", "PERDIDA", "RECUPERACION"];
export const TIPOS_MANUALES: TipoEventoLinea[] = ["GOL", "TIRO", "AMARILLA", "ROJA", "SUSTITUCION"];
/** Los pases son cientos: arrancan ocultos para que los hitos se vean. */
export const TIPOS_INICIALES: TipoEventoLinea[] = ["PERDIDA", "RECUPERACION", ...TIPOS_MANUALES];

export const ETIQUETA_TIPO: Record<TipoEventoLinea, string> = {
  PASE: "Pases",
  PERDIDA: "Pérdidas",
  RECUPERACION: "Recuperaciones",
  TIRO: "Tiros",
  FUERA: "Fueras",
  GOL: "Goles",
  AMARILLA: "Amarillas",
  ROJA: "Rojas",
  SUSTITUCION: "Cambios",
};

/** Ícono de cada tipo en la cronología horizontal. */
export const ICONO_TIPO: Record<TipoEventoLinea, string> = {
  PASE: "➜",
  PERDIDA: "✖",
  RECUPERACION: "↺",
  TIRO: "🎯",
  FUERA: "🚩",
  GOL: "⚽",
  AMARILLA: "🟨",
  ROJA: "🟥",
  SUSTITUCION: "🔄",
};

/** El eje llega como mínimo a 90'; si hay eventos en el descuento, se extiende («90+»). */
export const MINUTOS_REGLAMENTARIOS = 90;

/** Largo del eje en minutos: 90 o, con eventos pasados el 90, hasta el minuto del último. */
export function duracionEje(items: ItemLineaTiempo[]): number {
  const ultimo = items.reduce((max, i) => Math.max(max, i.t), 0);
  return Math.max(MINUTOS_REGLAMENTARIOS, Math.ceil((ultimo + 1) / 60));
}

/** Posición horizontal (0–100 %) de un instante en el eje de `duracion` minutos. */
export function porcentajeEnEje(t: number, duracion: number): number {
  if (duracion <= 0) return 0;
  return Math.min(100, Math.max(0, (t / (duracion * 60)) * 100));
}

export interface MarcaEje {
  minuto: number;
  etiqueta: string;
}

/** Marcas cada 15 minutos; el 90 se rotula «90+» cuando el eje se extiende más allá. */
export function marcasEje(duracion: number): MarcaEje[] {
  const marcas: MarcaEje[] = [];
  for (let m = 0; m <= duracion; m += 15) {
    marcas.push({
      minuto: m,
      etiqueta: m === MINUTOS_REGLAMENTARIOS && duracion > m ? "90+" : `${m}'`,
    });
  }
  return marcas;
}

/**
 * Reparte marcas en filas para que no se tapen: cada una va a la primera fila donde
 * la última marca queda a `separacion` (% del eje) o más. Pasadas `maxFilas`, se apilan en la última.
 * `posiciones` debe venir ordenado de menor a mayor.
 */
export function asignarFilas(posiciones: number[], separacion: number, maxFilas: number): number[] {
  const ultimaPorFila: number[] = [];
  return posiciones.map((pos) => {
    let fila = ultimaPorFila.findIndex((ultima) => pos - ultima >= separacion);
    if (fila === -1) fila = ultimaPorFila.length < maxFilas ? ultimaPorFila.length : maxFilas - 1;
    ultimaPorFila[fila] = pos;
    return fila;
  });
}

/** Segundos de partido como MM:SS (pasa de 99 minutos sin romperse). */
export function formatoTiempo(t: number): string {
  const total = Math.max(0, Math.floor(t));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function filtrarItems(
  items: ItemLineaTiempo[],
  tipos: ReadonlySet<TipoEventoLinea>,
  equipo: LadoPartido | null,
): ItemLineaTiempo[] {
  return items.filter((i) => tipos.has(i.tipo) && (equipo === null || i.equipo === equipo));
}

export function contarPorTipo(items: ItemLineaTiempo[]): Map<TipoEventoLinea, number> {
  const cuenta = new Map<TipoEventoLinea, number>();
  for (const i of items) cuenta.set(i.tipo, (cuenta.get(i.tipo) ?? 0) + 1);
  return cuenta;
}

/** Índice del último evento que ya ocurrió en `t` (-1 si todavía no hubo ninguno). Items por t. */
export function indiceActivo(items: ItemLineaTiempo[], t: number | null | undefined): number {
  if (t == null) return -1;
  let inicio = 0;
  let fin = items.length;
  while (inicio < fin) {
    const medio = (inicio + fin) >>> 1;
    if (items[medio].t <= t) inicio = medio + 1;
    else fin = medio;
  }
  return inicio - 1;
}
