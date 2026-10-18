/**
 * Tema claro/oscuro. El oscuro es el predeterminado; la elección se recuerda.
 * El atributo data-theme de <html> lo fija también un script en index.html
 * antes de pintar, para evitar el parpadeo.
 */
import { useSyncExternalStore } from "react";

export type Tema = "dark" | "light";

const CLAVE_TEMA = "areatecnica.tema";
const oyentes = new Set<() => void>();

export function obtenerTema(): Tema {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function guardar(tema: Tema): void {
  try {
    localStorage.setItem(CLAVE_TEMA, tema);
  } catch {
    // Sin almacenamiento disponible: el tema solo dura la sesión de la pestaña.
  }
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.setAttribute("data-theme", tema);
  guardar(tema);
  oyentes.forEach((oyente) => oyente());
}

export function alternarTema(): void {
  aplicarTema(obtenerTema() === "dark" ? "light" : "dark");
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => {
    oyentes.delete(oyente);
  };
}

export function useTema(): Tema {
  return useSyncExternalStore(suscribir, obtenerTema);
}
