/**
 * Sesión del usuario: único módulo que guarda y lee { access_token, usuario }.
 *
 * TODO: revisar dónde guardar la sesión cuando exista el endpoint de refresh.
 * localStorage es legible por cualquier script de la página (riesgo XSS); hoy
 * se acepta porque el access token dura 15 min y no hay refresh.
 */
import { useSyncExternalStore } from "react";

import { registrarAdaptadorAuth } from "@/shared/api/client";

import type { Sesion, SesionGuardada } from "./types";

const CLAVE_SESION = "areatecnica.sesion";
const RUTA_LOGIN = "/login";
const RUTA_REGISTRO = "/registro";

const oyentes = new Set<() => void>();

function notificar(): void {
  oyentes.forEach((oyente) => oyente());
}

function esRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null;
}

function esSesionGuardada(valor: unknown): valor is SesionGuardada {
  return (
    esRegistro(valor) && typeof valor["access_token"] === "string" && esRegistro(valor["usuario"])
  );
}

function parsear(crudo: string | null): SesionGuardada | null {
  if (crudo === null) return null;
  try {
    const valor: unknown = JSON.parse(crudo);
    return esSesionGuardada(valor) ? valor : null;
  } catch {
    return null;
  }
}

// useSyncExternalStore exige que obtenerSesion devuelva la MISMA referencia
// mientras nada cambie; por eso se cachea el último valor leído.
let crudoCache: string | null = null;
let sesionCache: SesionGuardada | null = null;

export function obtenerSesion(): SesionGuardada | null {
  const crudo = localStorage.getItem(CLAVE_SESION);
  if (crudo !== crudoCache) {
    crudoCache = crudo;
    sesionCache = parsear(crudo);
  }
  return sesionCache;
}

export function iniciarSesion(sesion: Sesion): void {
  const guardada: SesionGuardada = {
    access_token: sesion.access_token,
    usuario: sesion.usuario,
  };
  localStorage.setItem(CLAVE_SESION, JSON.stringify(guardada));
  notificar();
}

export function cerrarSesion(): void {
  localStorage.removeItem(CLAVE_SESION);
  notificar();
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  // Mantiene sincronizadas las demás pestañas.
  const alCambiarStorage = (evento: StorageEvent) => {
    if (evento.key === null || evento.key === CLAVE_SESION) oyente();
  };
  window.addEventListener("storage", alCambiarStorage);
  return () => {
    oyentes.delete(oyente);
    window.removeEventListener("storage", alCambiarStorage);
  };
}

/** Sesión actual (o null) y re-render cuando cambia. */
export function useSesion(): SesionGuardada | null {
  return useSyncExternalStore(suscribir, obtenerSesion);
}

function irAlLogin(): void {
  const ruta = window.location.pathname;
  // Evita bucles de recarga si ya se está en una pantalla pública.
  if (ruta === RUTA_LOGIN || ruta === RUTA_REGISTRO) return;
  window.location.assign(RUTA_LOGIN);
}

registrarAdaptadorAuth({
  obtenerToken: () => obtenerSesion()?.access_token ?? null,
  alSesionCaida: () => {
    cerrarSesion();
    irAlLogin();
  },
});

/**
 * Reemplaza solo el usuario de la sesión (p. ej. tras editar el perfil),
 * conserva el token y avisa a useSesion(). Sin sesión, no hace nada.
 */
export function actualizarUsuario(usuario: SesionGuardada["usuario"]): void {
  const actual = obtenerSesion();
  if (actual === null) return;
  const guardada: SesionGuardada = { access_token: actual.access_token, usuario };
  localStorage.setItem(CLAVE_SESION, JSON.stringify(guardada));
  notificar();
}
