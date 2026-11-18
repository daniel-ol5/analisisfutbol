import type { MensajeWorker } from "./types";

/** No muestra detecciones futuras o demasiado antiguas; admite búsquedas hacia atrás. */
export function muestraEnTiempo(muestras: MensajeWorker[], t: number, tolerancia = 0.35): MensajeWorker | null {
  let inicio = 0;
  let fin = muestras.length;
  while (inicio < fin) {
    const medio = (inicio + fin) >>> 1;
    if (muestras[medio].t <= t) inicio = medio + 1;
    else fin = medio;
  }
  const muestra = muestras[inicio - 1];
  return muestra && t - muestra.t <= tolerancia ? muestra : null;
}
