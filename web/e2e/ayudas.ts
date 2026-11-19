/** Utilidades compartidas por los flujos extremo a extremo (T-093). */
import { readFileSync } from "node:fs";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

export interface DatosE2E {
  email: string;
  password: string;
  club_id: number;
  jugador_id: number;
  partidos: { calibracion: number; vivo: number; video: number };
  rivales: { calibracion: string; vivo: string; video: string };
  video: string;
}

export function datos(): DatosE2E {
  const ruta = process.env.E2E_DATOS;
  if (!ruta) throw new Error("Define E2E_DATOS con el JSON que escribe backend/scripts/sembrar_e2e.py");
  return JSON.parse(readFileSync(ruta, "utf-8")) as DatosE2E;
}

export const API = (process.env.E2E_API_URL ?? "http://127.0.0.1:8100/api").replace(/\/+$/, "");

/** Inicia sesión desde la pantalla de login, como lo haría una persona. */
export async function iniciarSesion(page: Page, d: DatosE2E): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Correo electrónico").fill(d.email);
  await page.getByLabel("Contraseña").fill(d.password);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page).toHaveURL(/\/$/);
}

/** Token de acceso para preparar datos por la API (lo que no es parte del flujo probado). */
export async function token(request: APIRequestContext, d: DatosE2E): Promise<string> {
  const r = await request.post(`${API}/seguridad/login`, {
    data: { email: d.email, password: d.password },
  });
  expect(r.ok(), await r.text()).toBe(true);
  return ((await r.json()) as { access_token: string }).access_token;
}

export function auth(t: string): Record<string, string> {
  return { Authorization: `Bearer ${t}` };
}
