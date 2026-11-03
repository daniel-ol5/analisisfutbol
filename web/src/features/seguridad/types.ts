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

/** Etiquetas descriptivas de cada rol del club. */
export const ETIQUETA_ROL: Record<Rol, string> = {
  ADMIN: "Administrador",
  DT: "Director Técnico",
  ANALISTA: "Analista Táctico",
  ASISTENTE: "Asistente de Campo",
};

/** Descripción de permisos asociados a cada rol. */
export const DESCRIPCION_ROL: Record<Rol, string> = {
  ADMIN: "Acceso total al sistema, gestión de usuarios, roles, planteles, visión y reportes.",
  DT: "Gestión deportiva, alineaciones tácticas, operación de partido, análisis y reportes.",
  ANALISTA: "Calibración de cámaras, visión computacional, operación de partido, análisis y reportes.",
  ASISTENTE: "Consulta de planteles, operación de partido en campo y visualización de análisis.",
};

/** Cuerpo de POST /seguridad/usuarios (CU-04). */
export interface NuevoUsuario {
  email: string;
  password: string;
  rol: Rol;
  nombre?: string;
  apellido?: string;
}

/**
 * Cuerpo de PATCH /seguridad/usuarios/{id} (CU-04).
 * Coincide con UsuarioEditar en backend/app/seguridad/schemas.py.
 */
export interface ActualizarUsuario {
  nombre?: string;
  apellido?: string;
  rol?: Rol;
  activo?: boolean;
  password?: string;
}

/** Respuesta de GET y PATCH /seguridad/yo (CU-05): el usuario y el nombre de su club. */
export interface Perfil extends Usuario {
  club_nombre: string;
}

/**
 * Cuerpo de PATCH /seguridad/yo (CU-05). Al menos un campo; no acepta email,
 * rol ni estado (el servidor responde 422).
 */
export interface ActualizarPerfil {
  nombre?: string;
  apellido?: string;
}

/**
 * Cuerpo de POST /seguridad/yo/password (CU-05). Responde una Sesion nueva: las
 * anteriores, incluida la de esta pestaña, quedan invalidadas.
 */
export interface CambioPassword {
  password_actual: string;
  password_nueva: string;
}

/** Cuerpo de POST /seguridad/password/olvido (CU-06). */
export interface SolicitudRecuperacion {
  email: string;
}

/** Cuerpo de POST /seguridad/password/restablecer (CU-06). Responde una Sesion. */
export interface RestablecerPassword {
  token: string;
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
