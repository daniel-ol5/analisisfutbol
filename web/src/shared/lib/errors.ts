/**
 * Normalización de errores del backend a mensajes legibles en español.
 *
 * FastAPI devuelve `{"detail": ...}` donde `detail` es un texto (errores de
 * negocio: 401, 403, 409, 422 de dominio, 501) o una lista
 * `[{type, loc, msg, input}]` (422 de validación Pydantic).
 */
import { isAxiosError } from "axios";

export const MENSAJE_RED =
  "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
export const MENSAJE_GENERICO = "Ocurrió un error inesperado. Inténtalo de nuevo.";
export const MENSAJE_SERVIDOR = "El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.";
export const MENSAJE_CREDENCIALES = "Credenciales inválidas";
export const MENSAJE_CUENTA_DESACTIVADA = "La cuenta está desactivada";
export const MENSAJE_EMAIL_DUPLICADO = "Ese email ya tiene una cuenta";

const ETIQUETAS_CAMPO: Record<string, string> = {
  nombre_club: "Nombre del club",
  ciudad: "Ciudad",
  email: "Correo electrónico",
  password: "Contraseña",
  nombre: "Nombre",
  apellido: "Apellido",
  largo_m: "Largo de la cancha",
  ancho_m: "Ancho de la cancha",
  puntos_imagen: "Puntos en la imagen",
  puntos_cancha: "Puntos en la cancha",
  coef_distorsion: "Coeficientes de distorsión",
};

function esRegistro(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null;
}

function etiquetaDeCampo(loc: unknown): string | null {
  if (!Array.isArray(loc)) return null;
  const ultimo: unknown = loc[loc.length - 1];
  if (typeof ultimo !== "string") return null;
  return ETIQUETAS_CAMPO[ultimo] ?? ultimo;
}

function textoDeDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;
  if (!Array.isArray(detail)) return null;

  const mensajes: string[] = [];
  for (const item of detail) {
    if (!esRegistro(item) || typeof item["msg"] !== "string") continue;
    const campo = etiquetaDeCampo(item["loc"]);
    mensajes.push(campo ? `${campo}: ${item["msg"]}` : item["msg"]);
  }
  return mensajes.length > 0 ? mensajes.join(" · ") : null;
}

/** Código HTTP de la respuesta, o undefined si no hubo respuesta (red). */
export function estadoHttp(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined;
}

/** Convierte cualquier error en un mensaje legible para mostrar en la UI. */
export function mensajeDeError(error: unknown): string {
  if (!isAxiosError(error)) return MENSAJE_GENERICO;
  if (!error.response) return MENSAJE_RED;

  const data: unknown = error.response.data;
  const detalle = esRegistro(data) ? textoDeDetail(data["detail"]) : null;
  if (detalle) return detalle;

  return error.response.status >= 500 ? MENSAJE_SERVIDOR : MENSAJE_GENERICO;
}

/** Mensajes específicos del formulario de login (CU-02). */
export function mensajeDeLogin(error: unknown): string {
  const estado = estadoHttp(error);
  if (estado === 401) return MENSAJE_CREDENCIALES;
  if (estado === 403) return MENSAJE_CUENTA_DESACTIVADA;
  return mensajeDeError(error);
}
