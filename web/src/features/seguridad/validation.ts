/** Validación de formularios en cliente. Funciones puras: devuelven el mensaje de error o null. */

const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const MIN_PASSWORD = 8;
const MAX_PASSWORD = 72;

/** El backend no normaliza el email: se recorta y pasa a minúsculas acá. */
export function normalizarEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Recibe el email ya normalizado. */
export function validarEmail(email: string): string | null {
  if (email === "") return "Ingresa tu correo electrónico.";
  if (!EMAIL_VALIDO.test(email)) {
    return "Ingresa un correo electrónico válido.";
  }
  return null;
}

/** Login: el backend no exige largo mínimo al iniciar sesión. */
export function validarPasswordLogin(password: string): string | null {
  return password === "" ? "Ingresa tu contraseña." : null;
}

/**
 * Registro: de 8 a 72 caracteres y, además, máximo 72 bytes en UTF-8, porque
 * bcrypt limita bytes y una contraseña con acentos puede pasar el límite de
 * caracteres y aun así fallar en el servidor.
 */
export function validarPasswordRegistro(password: string): string | null {
  const caracteres = [...password].length;
  if (caracteres < MIN_PASSWORD) {
    return `La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`;
  }
  if (caracteres > MAX_PASSWORD) {
    return `La contraseña no puede superar los ${MAX_PASSWORD} caracteres.`;
  }
  if (new TextEncoder().encode(password).length > MAX_PASSWORD) {
    return (
      `La contraseña es demasiado larga: ocupa más de ${MAX_PASSWORD} bytes ` +
      "(los acentos y símbolos ocupan más de un byte). Usa una más corta."
    );
  }
  return null;
}

/** Nombre del club: de 2 a 120 caracteres (sin contar espacios de los extremos). */
export function validarNombreClub(nombreClub: string): string | null {
  const largo = [...nombreClub.trim()].length;
  if (largo < 2) return "El nombre del club debe tener al menos 2 caracteres.";
  if (largo > 120) return "El nombre del club no puede superar los 120 caracteres.";
  return null;
}

/** Campos opcionales con máximo de caracteres (ciudad, nombre y apellido: 80). */
export function validarOpcional(valor: string, maximo: number, etiqueta: string): string | null {
  return [...valor.trim()].length > maximo
    ? `${etiqueta} no puede superar los ${maximo} caracteres.`
    : null;
}
