/**
 * Flujo 1 (T-093): iniciar sesión, calibrar la cámara y ver el plano 2D.
 *
 * Usa las pantallas de Jhon y Daniel (CU-23 a CU-26, T-078) con sus
 * aria-label existentes: no se agregó nada a esas pantallas.
 */
import { expect, test } from "@playwright/test";

import { datos, iniciarSesion } from "./ayudas";

test("calibrar la cámara de un partido y ver el plano 2D", async ({ page }) => {
  const d = datos();
  await iniciarSesion(page, d);

  // Calibración con cámara en directo y reconocimiento automático.
  await page.goto(`/vision/calibracion?partidoId=${d.partidos.calibracion}`);
  await expect(page.getByRole("heading", { name: "Calibración y seguimiento de cancha" })).toBeVisible();
  await page.getByRole("combobox", { name: "Partido", exact: true }).selectOption(String(d.partidos.calibracion));
  await page.getByRole("combobox", { name: "Fuente", exact: true }).selectOption("DIRECTO");
  await page.getByRole("button", { name: "Reconocimiento automático" }).click();
  await page.getByRole("button", { name: "Guardar configuración" }).click();
  await expect(page.getByRole("status")).toContainText("Configuración automática guardada");

  // Desde ahí, al análisis: el plano 2D de la cancha.
  await page.getByRole("link", { name: "Abrir análisis" }).click();
  await expect(page).toHaveURL(/\/analisis/);
  const plano = page.getByRole("region", { name: "Posiciones sobre la cancha" });
  await expect(plano).toBeVisible();
  await expect(plano.getByRole("heading", { name: "Plano de cancha" })).toBeVisible();
  await expect(plano.locator("svg, canvas").first()).toBeVisible();
});
