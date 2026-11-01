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
  Perfil,
  RegistroClub,
  RestablecerPassword,
  Sesion,
  SolicitudRecuperacion,
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

/**
 * CU-06 · Pedir el enlace de recuperación. El servidor responde lo mismo exista
 * o no la cuenta, así que la UI tampoco distingue.
 */
export async function pedirRecuperacion(datos: SolicitudRecuperacion): Promise<void> {
  await api.post("/seguridad/password/olvido", datos);
}

/** CU-06 · Restablecer con el token del enlace. 400 si es inválido, usado o vencido. */
export async function restablecerPassword(datos: RestablecerPassword): Promise<Sesion> {
  const { data } = await api.post<Sesion>("/seguridad/password/restablecer", datos);
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

/** CU-05 · Datos del usuario autenticado, con el nombre de su club. */
export async function obtenerPerfil(): Promise<Perfil> {
  const { data } = await api.get<Perfil>("/seguridad/yo");
  return data;
}

/** CU-05 · Editar nombre y apellido propios. */
export async function editarPerfil(cambios: ActualizarPerfil): Promise<Perfil> {
  const { data } = await api.patch<Perfil>("/seguridad/yo", cambios);
  return data;
}

/**
 * CU-05 · Cambiar la contraseña propia. 403 si la actual no coincide.
 *
 * El servidor cierra TODAS las sesiones, también esta, y devuelve una nueva
 * que hay que guardar para seguir conectado (ver useCambiarPassword).
 */
export async function cambiarPassword(datos: CambioPassword): Promise<Sesion> {
  const { data } = await api.post<Sesion>("/seguridad/yo/password", datos);
  return data;
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
