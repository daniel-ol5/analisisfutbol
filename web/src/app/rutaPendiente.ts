/**
 * Recuerda la ruta que se intentó abrir sin sesión, para volver a ella tras
 * iniciar sesión. El login siempre navega a "/", así que RetornoTrasLogin
 * (en "/") es quien consume esta ruta. Vive en sessionStorage: solo dura la
 * pestaña.
 */
const CLAVE = "areatecnica.ruta_pendiente";

export function guardarRutaPendiente(ruta: string): void {
  try {
    sessionStorage.setItem(CLAVE, ruta);
  } catch {
    // Sin almacenamiento: tras el login se cae en Inicio.
  }
}

export function leerRutaPendiente(): string | null {
  try {
    return sessionStorage.getItem(CLAVE);
  } catch {
    return null;
  }
}

export function borrarRutaPendiente(): void {
  try {
    sessionStorage.removeItem(CLAVE);
  } catch {
    // Nada que borrar.
  }
}
