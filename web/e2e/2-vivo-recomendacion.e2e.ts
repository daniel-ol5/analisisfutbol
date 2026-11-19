/**
 * Flujo 2 (T-093): partido en vivo hasta que aparece una recomendación.
 *
 * - El emisor simulado (backend/scripts/emisor_simulado.py) inicia el partido y
 *   alimenta /ingesta a 5 Hz, como el worker de visión.
 * - Se registra una roja propia: dispara la regla CRITICA «Reorganización tras
 *   una expulsión» del catálogo (T-083) en la siguiente evaluación (≤ 5 s de
 *   partido). Las reglas de posición no se disparan con el emisor simulado: no
 *   manda `calibracion_valida` y el motor de reglas descarta esas ventanas.
 * - La tarjeta tiene que aparecer en Asistencia (T-090) por el WebSocket /vivo.
 */
import { spawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { API, auth, datos, iniciarSesion, token } from "./ayudas";

const PYTHON = process.env.E2E_PYTHON ?? "python";
const EMISOR = fileURLToPath(new URL("../../backend/scripts/emisor_simulado.py", import.meta.url));

test("con el partido en vivo, una expulsión propia llega como recomendación crítica", async ({
  page,
  request,
}) => {
  const d = datos();
  const partido = d.partidos.vivo;
  const t = await token(request, d);

  await iniciarSesion(page, d);
  await page.goto("/asistencia");
  await page.getByTestId("asistencia-partido").selectOption(String(partido));
  const pestanas = page.getByRole("navigation", { name: "Asistencia y reportes" });
  await pestanas.getByRole("link", { name: "Reglas tácticas" }).click();
  await expect(page.getByRole("region", { name: "Catálogo de reglas" })).toBeVisible();
  await expect(page.getByRole("switch").first()).toBeVisible();
  await pestanas.getByRole("link", { name: "Recomendaciones" }).click();
  await expect(page.getByTestId("asistencia-partido")).toHaveValue(String(partido));
  const lista = page.getByTestId("recomendaciones");
  await expect(lista.getByText("Sin recomendaciones activas por ahora.")).toBeVisible();

  let emisor: ChildProcess | null = null;
  let salidaEmisor = "";
  try {
    emisor = spawn(PYTHON, [
      EMISOR, "--url", API, "--partido", String(partido),
      "--email", d.email, "--password", d.password,
      "--iniciar-partido", "--ataca-hacia", "DER", "--duracion", "120", "--semilla", "93",
    ], { stdio: ["ignore", "pipe", "pipe"] });
    emisor.stdout?.on("data", (b: Buffer) => (salidaEmisor += b.toString()));
    emisor.stderr?.on("data", (b: Buffer) => (salidaEmisor += b.toString()));

    // El partido pasa a EN_CURSO (lo inicia el emisor) y la tarjeta muestra el canal en vivo.
    await expect
      .poll(async () => {
        const r = await request.get(`${API}/deportivo/partidos/${partido}`, { headers: auth(t) });
        return ((await r.json()) as { estado: string }).estado;
      }, { timeout: 30_000, message: "El emisor no inició el partido (ver el adjunto «emisor»)" })
      .toBe("EN_CURSO");
    await expect(lista.getByText("En vivo")).toBeVisible({ timeout: 30_000 });

    // Roja a un jugador propio (asistente de campo, CU-37).
    const roja = await request.post(`${API}/partido/${partido}/eventos`, {
      headers: auth(t),
      data: { uuid: randomUUID(), tipo: "ROJA", equipo: "LOCAL", jugador_id: d.jugador_id },
    });
    expect(roja.ok(), await roja.text()).toBe(true);

    // La recomendación llega por /vivo, con su prioridad y la cifra que la disparó.
    const tarjeta = lista.getByTestId("tarjeta-recomendacion").first();
    await expect(tarjeta).toBeVisible({ timeout: 30_000 });
    await expect(tarjeta).toContainText("Prioridad Crítica");
    await expect(tarjeta).toContainText("Reordena las líneas");
    await expect(tarjeta).toContainText("Expulsiones propias");

    // T-091: «Aplicada» la saca de las activas (decisión del equipo) y queda registrada.
    await tarjeta.getByRole("button", { name: "Aplicada" }).click();
    await expect(lista.getByTestId("tarjeta-recomendacion")).toHaveCount(0);
    const todas = await request.get(
      `${API}/asistencia/partidos/${partido}/recomendaciones?solo_activas=false`,
      { headers: auth(t) },
    );
    const valoradas = ((await todas.json()) as { estado: string; util: boolean | null }[]).filter(
      (r) => r.estado === "APLICADA",
    );
    expect(valoradas).toEqual([expect.objectContaining({ estado: "APLICADA", util: true })]);
  } finally {
    emisor?.kill();
    await test.info().attach("emisor", { body: salidaEmisor, contentType: "text/plain" });
  }
});
