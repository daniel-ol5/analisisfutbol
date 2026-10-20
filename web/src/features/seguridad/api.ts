/**
 * Llamadas al backend de Seguridad y Administración  —  P1.
 *
 * Endpoints bajo /api/seguridad. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type { Credenciales, RegistroClub, Sesion } from "./types";

export async function ping() {
  const { data } = await api.get("/seguridad/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-01 · Registrar club y cuenta administradora. */
export async function registrar(datos: RegistroClub): Promise<Sesion> {
  const { data } = await api.post<Sesion>("/seguridad/registro", datos);
  return data;
}

/** CU-02 · Iniciar sesión. */
export async function login(credenciales: Credenciales): Promise<Sesion> {
  const { data } = await api.post<Sesion>("/seguridad/login", credenciales);
  return data;
}

/** CU-03 · Cerrar sesión en el servidor (hoy no invalida el refresh token). */
export async function logout(): Promise<void> {
  await api.post("/seguridad/logout");
}
