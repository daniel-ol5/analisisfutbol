import type { AristaPase, NodoPase } from "./types";

export const LARGO_CANCHA = 105;
export const ANCHO_CANCHA = 68;

export interface Punto {
  x: number;
  y: number;
}

export interface GeometriaFlecha {
  /** Tramo recto, del borde del nodo origen a la base de la cabeza */
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  /** Triángulo de la cabeza, como `points` de un polígono SVG */
  cabeza: string;
}

/** Holgura entre la flecha y la línea central del par, en metros del plano. Se suma a la mitad del grosor para que ida y vuelta no se solapen. */
const HOLGURA_SENTIDOS = 0.2;

/**
 * Flecha dirigida de `a` a `b`. Sale del borde del nodo origen, termina en el borde del destino
 * y se corre al costado derecho de su sentido: la de vuelta queda del otro lado y no la tapa.
 * Devuelve null si los nodos están tan juntos que no cabe una flecha.
 */
export function geometriaFlecha(
  a: Punto,
  b: Punto,
  radioA: number,
  radioB: number,
  grosor: number,
): GeometriaFlecha | null {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const largo = Math.hypot(dx, dy);
  const largoCabeza = 1.4 + grosor;
  const mitadCabeza = 0.7 + 0.6 * grosor;
  if (largo < radioA + radioB + largoCabeza + 0.5) return null;
  const ux = dx / largo;
  const uy = dy / largo;
  const nx = uy; // normal hacia la derecha del sentido a → b
  const ny = -ux;
  const desvio = HOLGURA_SENTIDOS + grosor / 2;
  const ox = nx * desvio;
  const oy = ny * desvio;
  const punta = { x: b.x - ux * radioB + ox, y: b.y - uy * radioB + oy };
  const base = { x: punta.x - ux * largoCabeza, y: punta.y - uy * largoCabeza };
  const p = (x: number, y: number) => `${x.toFixed(2)},${y.toFixed(2)}`;
  return {
    x1: a.x + ux * radioA + ox,
    y1: a.y + uy * radioA + oy,
    x2: base.x,
    y2: base.y,
    cabeza: [
      p(punta.x, punta.y),
      p(base.x + nx * mitadCabeza, base.y + ny * mitadCabeza),
      p(base.x - nx * mitadCabeza, base.y - ny * mitadCabeza),
    ].join(" "),
  };
}

export interface FlechaVisual extends GeometriaFlecha {
  origen_id: number;
  destino_id: number;
  pases: number;
  /** Grosor de la línea: crece con los pases completados de origen a destino */
  grosor: number;
}

/**
 * Una flecha por cada sentido con al menos `minimo` pases, ordenadas de menos a más pases
 * para que las gruesas se dibujen encima. El grosor es relativo a la conexión más fuerte.
 */
export function flechasDeRed(aristas: AristaPase[], nodos: NodoPase[], minimo = 1): FlechaVisual[] {
  const porId = new Map(nodos.map((n) => [n.jugador_id, n]));
  const maxRecibidos = Math.max(0, ...nodos.map((n) => n.pases_recibidos));
  const visibles = aristas.filter((a) => a.pases >= minimo);
  const maxPases = Math.max(0, ...visibles.map((a) => a.pases));
  const flechas: FlechaVisual[] = [];
  for (const a of [...visibles].sort((x, y) => x.pases - y.pases)) {
    const origen = porId.get(a.origen_id);
    const destino = porId.get(a.destino_id);
    if (!origen || !destino) continue;
    const grosor = grosorEnlace(a.pases, maxPases);
    const g = geometriaFlecha(
      dentroDeCancha(origen),
      dentroDeCancha(destino),
      radioNodo(origen.pases_recibidos, maxRecibidos),
      radioNodo(destino.pases_recibidos, maxRecibidos),
      grosor,
    );
    if (g)
      flechas.push({
        ...g,
        origen_id: a.origen_id,
        destino_id: a.destino_id,
        pases: a.pases,
        grosor,
      });
  }
  return flechas;
}

/** Grosor de línea en metros del plano: entre 0,3 y 2,2 según el peso relativo. */
export function grosorEnlace(total: number, maximo: number): number {
  if (maximo <= 0) return 0.3;
  return 0.3 + 1.9 * Math.min(1, total / maximo);
}

/** Radio del nodo en metros del plano: entre 1,6 y 3,4 según el volumen de pases recibidos. */
export function radioNodo(recibidos: number, maximo: number): number {
  if (maximo <= 0) return 1.6;
  return 1.6 + 1.8 * Math.min(1, recibidos / maximo);
}

/** Deja la posición media dentro de la cancha por si el dato viene con ruido de calibración. */
export function dentroDeCancha(n: Pick<NodoPase, "x_medio" | "y_medio">): { x: number; y: number } {
  return {
    x: Math.min(LARGO_CANCHA, Math.max(0, n.x_medio)),
    y: Math.min(ANCHO_CANCHA, Math.max(0, n.y_medio)),
  };
}
