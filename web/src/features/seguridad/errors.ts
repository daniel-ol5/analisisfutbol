/**
 * Re-exporta el normalizador de errores compartido en `@/shared/lib/errors`
 * para mantener intactas las importaciones internas de la feature `seguridad`.
 */
export {
  MENSAJE_CREDENCIALES,
  MENSAJE_CUENTA_DESACTIVADA,
  MENSAJE_EMAIL_DUPLICADO,
  MENSAJE_GENERICO,
  MENSAJE_RED,
  MENSAJE_SERVIDOR,
  estadoHttp,
  mensajeDeError,
  mensajeDeLogin,
} from "@/shared/lib/errors";
