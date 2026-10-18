/**
 * Llamadas al backend de Seguridad y Administración  —  P1.
 *
 * Endpoints bajo /api/seguridad. Usar hooks de TanStack Query, no fetch suelto
 * dentro de los componentes.
 */
import { api } from "@/shared/api/client";

import type {
  ActualizarPerfil,
  ActualizarUsuario,
  CambioPassword,
  Credenciales,
  NuevoUsuario,
  RegistroClub,
  Sesion,
  Usuario,
} from "./types";

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

/** CU-04 · Listar los usuarios del club. */
export async function listarUsuarios(): Promise<Usuario[]> {
  const { data } = await api.get<Usuario[]>("/seguridad/usuarios");
  return data;
}

/** CU-04 · Crear un usuario del club. */
export async function crearUsuario(datos: NuevoUsuario): Promise<Usuario> {
  const { data } = await api.post<Usuario>("/seguridad/usuarios", datos);
  return data;
}

/** CU-05 · Datos del usuario autenticado. */
export async function obtenerPerfil(): Promise<Usuario> {
  const { data } = await api.get<Usuario>("/seguridad/yo");
  return data;
}

/**
 * CU-05 · Editar nombre y apellido propios.
 *
 * PROPUESTO, NO ESTÁ EN EL CONTRATO: PATCH /seguridad/yo. Ver
 * HABILITAR_EDICION_PERFIL en config.ts.
 */
export async function editarPerfil(cambios: ActualizarPerfil): Promise<Usuario> {
  const { data } = await api.patch<Usuario>("/seguridad/yo", cambios);
  return data;
}

/**
 * CU-05 · Cambiar la contraseña propia (cierra las demás sesiones).
 *
 * PROPUESTO, NO ESTÁ EN EL CONTRATO: POST /seguridad/yo/password. Ver
 * HABILITAR_CAMBIO_PASSWORD en config.ts.
 */
export async function cambiarPassword(datos: CambioPassword): Promise<void> {
  await api.post("/seguridad/yo/password", datos);
}

/**
 * CU-04 · Desactivar, reactivar o cambiar el rol de un usuario.
 *
 * PROPUESTO, NO ESTÁ EN EL CONTRATO: PATCH /seguridad/usuarios/{id}. Ver
 * HABILITAR_EDICION_USUARIOS en config.ts.
 */
export async function actualizarUsuario(id: number, cambios: ActualizarUsuario): Promise<Usuario> {
  const { data } = await api.patch<Usuario>(`/seguridad/usuarios/${id}`, cambios);
  return data;
}
