/**
 * Interruptores de funciones que dependen de endpoints que TODAVÍA NO ESTÁN
 * en docs/api/openapi.json. El código ya está hecho; cada constante se pone
 * en true cuando su endpoint exista en el contrato.
 */

/** Desactivar, reactivar o cambiar rol de usuarios: PATCH /seguridad/usuarios/{id}. */
export const HABILITAR_EDICION_USUARIOS = false;

/** Editar nombre y apellido propios: PATCH /seguridad/yo. */
export const HABILITAR_EDICION_PERFIL = false;

/** Cambiar la contraseña propia: POST /seguridad/yo/password. */
export const HABILITAR_CAMBIO_PASSWORD = false;
