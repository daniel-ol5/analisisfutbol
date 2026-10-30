/** Tipos del dominio de Seguridad y Administración  —  P1 · CU-01 … CU-08. */

export type Rol = "ADMIN" | "DT" | "ANALISTA" | "ASISTENTE";

export interface Usuario {
  id: number;
  club_id: number;
  email: string;
  nombre: string;
  apellido: string;
  rol: Rol;
  activo: boolean;
}

/** Respuesta de POST /seguridad/registro y POST /seguridad/login. */
export interface Sesion {
  access_token: string;
  /** Se emite, pero ninguna ruta lo consume todavía: no existe /refresh. */
  refresh_token: string;
  token_type: string;
  usuario: Usuario;
}

/** Lo único que la web conserva de la sesión. */
export interface SesionGuardada {
  access_token: string;
  usuario: Usuario;
}

/** Cuerpo de POST /seguridad/login. */
export interface Credenciales {
  email: string;
  password: string;
}

/** Roles asignables, en el orden en que se ofrecen en los formularios. */
export const ROLES: readonly Rol[] = ["ADMIN", "DT", "ANALISTA", "ASISTENTE"];

/** Cuerpo de POST /seguridad/usuarios (CU-04). */
export interface NuevoUsuario {
  email: string;
  password: string;
  rol: Rol;
  nombre?: string;
  apellido?: string;
}

/**
 * Cuerpo de PATCH /seguridad/usuarios/{id} (CU-04). Al menos un campo.
 * PROPUESTO, NO ESTÁ EN EL CONTRATO.
 */
export interface ActualizarUsuario {
  activo?: boolean;
  rol?: Rol;
}

/**
 * Cuerpo de PATCH /seguridad/yo (CU-05). Al menos un campo; no acepta email,
 * rol ni estado. PROPUESTO, NO ESTÁ EN EL CONTRATO.
 */
export interface ActualizarPerfil {
  nombre?: string;
  apellido?: string;
}

/** Cuerpo de POST /seguridad/yo/password (CU-05). PROPUESTO, NO ESTÁ EN EL CONTRATO. */
export interface CambioPassword {
  password_actual: string;
  password_nueva: string;
}

/** Cuerpo de POST /seguridad/registro (CU-01). */
export interface RegistroClub {
  nombre_club: string;
  ciudad?: string;
  email: string;
  password: string;
  nombre?: string;
  apellido?: string;
}
