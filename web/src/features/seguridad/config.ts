/**
 * Interruptores de funciones del paquete de Seguridad y Administración (P1).
 */

/** Editar, dar de baja, reactivar o cambiar rol de usuarios: PATCH/DELETE /seguridad/usuarios/{id}. */
export const HABILITAR_EDICION_USUARIOS = true;

/** Editar nombre y apellido propios: PATCH /seguridad/yo. */
export const HABILITAR_EDICION_PERFIL = true;

/** Cambiar la contraseña propia: POST /seguridad/yo/password. */
export const HABILITAR_CAMBIO_PASSWORD = true;
