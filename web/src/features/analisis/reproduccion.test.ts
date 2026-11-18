import { expect, test } from "vitest";
import { muestraEnTiempo } from "./reproduccion";
import type { MensajeWorker } from "./types";

test("replay no arrastra posiciones durante huecos ni al volver atrás", () => {
  const muestras = [0, 0.2, 0.4, 8].map(t => ({ t }) as MensajeWorker);
  expect(muestraEnTiempo(muestras, 0.3)?.t).toBe(0.2);
  expect(muestraEnTiempo(muestras, 8.1)?.t).toBe(8);
  expect(muestraEnTiempo(muestras, 0.1)?.t).toBe(0);
  expect(muestraEnTiempo(muestras, 3)).toBeNull();
  expect(muestraEnTiempo(muestras, -1)).toBeNull();
});
