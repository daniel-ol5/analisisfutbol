/**
 * Pruebas extremo a extremo  —  T-093.
 *
 * Corren contra un backend y una web ya levantados (la CI los levanta en el job
 * `e2e`; en local, ver e2e/README.md). Comparten una base de datos sembrada con
 * backend/scripts/sembrar_e2e.py, así que van de a una (workers: 1).
 *
 * Variables:
 *   E2E_WEB_URL  web          (por defecto http://127.0.0.1:5180)
 *   E2E_API_URL  API          (por defecto http://127.0.0.1:8100/api)
 *   E2E_DATOS    JSON con los ids sembrados (obligatoria)
 *   E2E_CANAL    opcional: "chromium" para usar el Chromium completo sin cabeza
 */
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // `.e2e.ts` y no `.spec.ts`: así vitest (npm test) no las toma.
  testMatch: /.*\.e2e\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  // Fuera del repo: no hace falta tocar .gitignore.
  outputDir: process.env.E2E_SALIDA ?? join(tmpdir(), "areatecnica-e2e"),
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL: process.env.E2E_WEB_URL ?? "http://127.0.0.1:5180",
    locale: "es-BO",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // E2E_CANAL=chromium usa el Chromium completo en modo sin cabeza: sirve si solo
        // está instalado ese y no el «headless shell» (por ejemplo, con mala conexión).
        ...(process.env.E2E_CANAL ? { channel: process.env.E2E_CANAL } : {}),
      },
    },
  ],
});
