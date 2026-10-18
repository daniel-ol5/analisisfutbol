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

/** Cuerpo de POST /seguridad/registro (CU-01). */
export interface RegistroClub {
  nombre_club: string;
  ciudad?: string;
  email: string;
  password: string;
  nombre?: string;
  apellido?: string;
}
