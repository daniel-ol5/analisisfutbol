/**
 * Estado global mínimo del asistente: si el panel está abierto y la pregunta
 * con la que se abrió (botón «¿Cómo se usa esto?»). Es un store externo para
 * que cualquier pantalla lo abra sin envolver la app en un proveedor.
 *
 * El historial del chat vive en sessionStorage, por usuario: se conserva
 * mientras la pestaña y la sesión sigan abiertas y nunca va a localStorage.
 */
import { useSyncExternalStore } from "react";

import type { MensajeChat } from "./types";

interface EstadoPanel {
  abierto: boolean;
  /** Pregunta que se envía sola al abrir; null si no hay. */
  preguntaInicial: string | null;
}

let estado: EstadoPanel = { abierto: false, preguntaInicial: null };
const oyentes = new Set<() => void>();

function cambiar(nuevo: EstadoPanel) {
  estado = nuevo;
  oyentes.forEach((avisar) => avisar());
}

export function abrirAsistente(pregunta?: string) {
  cambiar({ abierto: true, preguntaInicial: pregunta?.trim() || null });
}

export function cerrarAsistente() {
  cambiar({ abierto: false, preguntaInicial: null });
}

/** Se llama al enviar la pregunta inicial, para no repetirla. */
export function consumirPreguntaInicial() {
  if (estado.preguntaInicial !== null) cambiar({ ...estado, preguntaInicial: null });
}

function suscribir(avisar: () => void) {
  oyentes.add(avisar);
  return () => oyentes.delete(avisar);
}

export function useEstadoAsistente(): EstadoPanel {
  return useSyncExternalStore(suscribir, () => estado);
}

// ---------- Historial de la sesión ----------

const PREFIJO_HISTORIAL = "areatecnica.asistente.";
const MAX_GUARDADOS = 40;

export function leerHistorial(usuarioId: number | undefined): MensajeChat[] {
  if (usuarioId === undefined) return [];
  try {
    const crudo = sessionStorage.getItem(`${PREFIJO_HISTORIAL}${usuarioId}`);
    const datos: unknown = crudo ? JSON.parse(crudo) : [];
    return Array.isArray(datos) ? (datos as MensajeChat[]) : [];
  } catch {
    return [];
  }
}

/** Borra el historial de todos los usuarios de esta pestaña (al cerrar sesión). */
export function borrarHistoriales() {
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i -= 1) {
      const clave = sessionStorage.key(i);
      if (clave?.startsWith(PREFIJO_HISTORIAL)) sessionStorage.removeItem(clave);
    }
  } catch {
    // Sin almacenamiento no hay nada que borrar.
  }
}

export function guardarHistorial(usuarioId: number | undefined, mensajes: MensajeChat[]) {
  if (usuarioId === undefined) return;
  try {
    sessionStorage.setItem(
      `${PREFIJO_HISTORIAL}${usuarioId}`,
      JSON.stringify(mensajes.slice(-MAX_GUARDADOS)),
    );
  } catch {
    // Sin almacenamiento, el chat sigue funcionando mientras la página esté abierta.
  }
}
