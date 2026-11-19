import type { MensajeWorker, PosicionDetectada } from "./types";

type Bbox4 = [number, number, number, number];
type DeteccionItem = NonNullable<MensajeWorker["detecciones"]>[number];

function lerp(a: number, b: number, alpha: number): number {
  return a + (b - a) * alpha;
}

function lerpBbox(a?: Bbox4 | null, b?: Bbox4 | null, alpha = 0): Bbox4 | null | undefined {
  if (!a || !b) return a;
  return [
    lerp(a[0], b[0], alpha),
    lerp(a[1], b[1], alpha),
    lerp(a[2], b[2], alpha),
    lerp(a[3], b[3], alpha),
  ];
}

function indiceEnTiempo(muestras: MensajeWorker[], t: number): number {
  let inicio = 0;
  let fin = muestras.length;
  while (inicio < fin) {
    const medio = (inicio + fin) >>> 1;
    if (muestras[medio].t <= t) inicio = medio + 1;
    else fin = medio;
  }
  return inicio - 1;
}

/** No muestra detecciones futuras o demasiado antiguas; admite búsquedas hacia atrás. */
export function muestraEnTiempo(muestras: MensajeWorker[], t: number, tolerancia = 0.35): MensajeWorker | null {
  const idx = indiceEnTiempo(muestras, t);
  const muestra = muestras[idx];
  return muestra && t - muestra.t <= tolerancia ? muestra : null;
}

/**
 * Interpola linealmente posiciones y cajas por `tid` entre dos muestras consecutivas (5 Hz)
 * para lograr movimiento fluido a 60 FPS sobre el video y el plano 2D sin inventar datos
 * a través de huecos ni cortes de calibración.
 */
export function muestraInterpoladaEnTiempo(
  muestras: MensajeWorker[],
  t: number,
  tolerancia = 0.35,
): MensajeWorker | null {
  const idx = indiceEnTiempo(muestras, t);
  const prev = muestras[idx];
  if (!prev || t - prev.t > tolerancia) return null;

  const next = muestras[idx + 1];
  if (
    !next ||
    next.t <= prev.t ||
    next.t - prev.t > 0.45 ||
    prev.calidad.calibracion_valida === false ||
    next.calidad.calibracion_valida === false
  ) {
    return prev;
  }

  const alpha = Math.min(1, Math.max(0, (t - prev.t) / (next.t - prev.t)));
  if (alpha < 0.01) return prev;
  if (alpha > 0.99) return next;

  const sigJugadores = new Map<number, PosicionDetectada>();
  for (const j of next.jugadores) sigJugadores.set(j.tid, j);

  const jugadores = prev.jugadores.map((j) => {
    const s = sigJugadores.get(j.tid);
    if (!s || Math.hypot(s.x - j.x, s.y - j.y) > 8) return j;
    return {
      ...j,
      x: lerp(j.x, s.x, alpha),
      y: lerp(j.y, s.y, alpha),
      bbox: lerpBbox(j.bbox, s.bbox, alpha),
    };
  });

  let detecciones = prev.detecciones;
  if (prev.detecciones?.length && next.detecciones?.length) {
    const sigDet = new Map<number, DeteccionItem>();
    for (const d of next.detecciones) {
      if (d.clase !== "BALON") sigDet.set(d.tid, d);
    }
    detecciones = prev.detecciones.map((d) => {
      if (d.clase === "BALON") return d;
      const s = sigDet.get(d.tid);
      if (!s) return d;
      const dx = Math.abs(s.bbox[0] - d.bbox[0]);
      const dy = Math.abs(s.bbox[1] - d.bbox[1]);
      if (dx > 12 || dy > 12 || d.bbox.length !== 4 || s.bbox.length !== 4) return d;
      return {
        ...d,
        bbox: [
          lerp(d.bbox[0], s.bbox[0], alpha),
          lerp(d.bbox[1], s.bbox[1], alpha),
          lerp(d.bbox[2], s.bbox[2], alpha),
          lerp(d.bbox[3], s.bbox[3], alpha),
        ],
      };
    });
  }

  let balon = prev.balon ?? null;
  if (prev.balon && next.balon && Math.hypot(next.balon.x - prev.balon.x, next.balon.y - prev.balon.y) <= 25) {
    balon = {
      ...prev.balon,
      x: lerp(prev.balon.x, next.balon.x, alpha),
      y: lerp(prev.balon.y, next.balon.y, alpha),
      bbox: lerpBbox(prev.balon.bbox, next.balon.bbox, alpha),
    };
  }

  return {
    ...prev,
    t,
    jugadores,
    detecciones,
    balon,
  };
}
