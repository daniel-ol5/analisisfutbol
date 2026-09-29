/**
 * Cliente HTTP único de la aplicación.
 *
 * Toda llamada al backend pasa por acá. El interceptor adjunta el token de
 * acceso automáticamente, así ninguna feature tiene que acordarse de hacerlo.
 */
import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api",
  headers: { "Content-Type": "application/json" },
});

const CLAVE_TOKEN = "areatecnica.access_token";

export function guardarToken(token: string) {
  localStorage.setItem(CLAVE_TOKEN, token);
}

export function borrarToken() {
  localStorage.removeItem(CLAVE_TOKEN);
}

export function leerToken(): string | null {
  return localStorage.getItem(CLAVE_TOKEN);
}

api.interceptors.request.use((config) => {
  const token = leerToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    // TODO Pb-01: renovar con el refresh token en vez de cerrar la sesión.
    if (error.response?.status === 401) borrarToken();
    return Promise.reject(error);
  },
);
