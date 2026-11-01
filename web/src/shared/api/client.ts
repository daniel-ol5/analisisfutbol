/**
 * Cliente HTTP único de la aplicación.
 *
 * Toda llamada al backend pasa por acá. El interceptor adjunta el token de
 * acceso automáticamente, así ninguna feature tiene que acordarse de hacerlo.
 *
 * Este módulo NO sabe dónde se guarda la sesión: `shared/` no puede importar
 * de una feature. La feature `seguridad` registra un adaptador con
 * `registrarAdaptadorAuth` y el cliente le pregunta el token y le avisa
 * cuando la sesión cae.
 */
import axios, { isAxiosError } from "axios";

import { env } from "@/shared/config/env";

export const api = axios.create({
  baseURL: env.apiUrl,
  headers: { "Content-Type": "application/json" },
});

export interface AdaptadorAuth {
  /** Token de acceso vigente, o null si no hay sesión. */
  obtenerToken: () => string | null;
  /** Se invoca ante un 401 en una ruta protegida. */
  alSesionCaida: () => void;
}

let adaptador: AdaptadorAuth | null = null;

export function registrarAdaptadorAuth(nuevo: AdaptadorAuth): void {
  adaptador = nuevo;
}

/**
 * Rutas donde un 401 significa «credenciales inválidas» y no «sesión caída»:
 * el error debe mostrarse en el formulario, no redirigir.
 */
const RUTAS_PUBLICAS = [
  "/seguridad/login",
  "/seguridad/registro",
  "/seguridad/password/olvido",
  "/seguridad/password/restablecer",
];

function esRutaPublica(url: string | undefined): boolean {
  if (!url) return false;
  const ruta = url.split("?")[0] ?? "";
  return RUTAS_PUBLICAS.some((publica) => ruta.endsWith(publica));
}

api.interceptors.request.use((config) => {
  const token = adaptador?.obtenerToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: unknown) => {
    // No existe endpoint de refresh en el backend: un 401 en una ruta
    // protegida es sesión caída. TODO: renovar con el refresh token cuando
    // el backend lo implemente, en vez de cerrar la sesión.
    if (
      isAxiosError(error) &&
      error.response?.status === 401 &&
      !esRutaPublica(error.config?.url)
    ) {
      adaptador?.alSesionCaida();
    }
    return Promise.reject(error);
  },
);
