/**
 * Flujo 3 (T-093): subir un video y llegar a «Procesado»; luego, el informe.
 *
 * La pantalla de videos es de Araceli y Daniel (T-060 a T-062): se usan sus
 * textos y roles existentes. El procesamiento real lo hace el worker de visión
 * con GPU (YOLO), que no corre en la CI: la prueba toma su papel con el MISMO
 * protocolo de la API (tomar trabajo → resultados → terminar).
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";

import { expect, test } from "@playwright/test";

import { API, auth, datos, iniciarSesion, token } from "./ayudas";

test("subir un video, procesarlo y verlo como procesado", async ({ page, request }) => {
  const d = datos();
  const partido = d.partidos.video;
  const t = await token(request, d);

  await iniciarSesion(page, d);
  await page.goto(`/vision/videos?partidoId=${partido}`);
  // Exacto y como combobox: el menú del rediseño (#45) tiene el link "Control de partido".
  await page.getByRole("combobox", { name: "Partido", exact: true }).selectOption(String(partido));

  // Subida desde la interfaz (el selector de archivos está oculto detrás del botón).
  const [selector] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Subir video" }).click(),
  ]);
  await selector.setFiles({
    name: basename(d.video),
    mimeType: "video/mp4",
    buffer: readFileSync(d.video),
  });
  const tarjeta = page.getByRole("listitem", { name: `Video ${basename(d.video)}` });
  await expect(tarjeta.getByText("Listo para procesar")).toBeVisible({ timeout: 30_000 });

  // Lanzar el procesamiento.
  await tarjeta.getByRole("button", { name: "Procesar video" }).click();
  // Hasta que un worker lo toma, la tarjeta dice "En cola" (T-062); "Procesando"
  // aparece recién cuando el worker de abajo pide el trabajo.
  await expect(tarjeta.getByText("En cola")).toBeVisible();

  // El worker toma el trabajo, manda un lote y termina (contrato de T-061).
  const trabajo = await request.post(`${API}/vision/trabajos/tomar`, { headers: auth(t) });
  expect(trabajo.status(), await trabajo.text()).toBe(200);
  const { video_id: videoId } = (await trabajo.json()) as { video_id: number };
  const muestra = {
    partido, t: 0.5,
    jugadores: [{ tid: 1, equipo: "LOCAL", x: 30, y: 30, conf: 0.9 }],
    balon: { tid: 0, equipo: "DESCONOCIDO", x: 31, y: 30, conf: 0.8 },
    calidad: { worker_conectado: true, fps: 10, jugadores_detectados: 1,
               balon_visible: true, retraso_s: 0, degradado: false },
  };
  const lote = await request.post(`${API}/vision/videos/${videoId}/resultados`, {
    headers: auth(t), data: { progreso_pct: 50, muestras: [muestra] },
  });
  expect(lote.ok(), await lote.text()).toBe(true);
  const fin = await request.post(`${API}/vision/videos/${videoId}/terminar`, {
    headers: auth(t), data: { ok: true },
  });
  expect(fin.ok(), await fin.text()).toBe(true);

  // La interfaz lo muestra como procesado (sondea el estado del video).
  await expect(tarjeta.getByText("Procesado", { exact: true })).toBeVisible({ timeout: 30_000 });
});

// Pendiente: depende de T-098 (informe post-partido en PDF) y T-100 (vista del
// informe en web), de Jhon. Hoy POST /asistencia/partidos/{id}/informe responde
// 501 y no hay pantalla de informe. Cuando existan, quitar el skip y completar.
test.skip("del video procesado al informe post-partido (T-098, T-100)", async () => {
  // 1. Generar el informe del partido desde la web.
  // 2. Esperar a que quede LISTO.
  // 3. Ver el porcentaje de recomendaciones útiles (T-091) en el informe.
});
