/**
 * Variables de entorno de la aplicación.
 *
 * Este es el ÚNICO archivo que puede leer import.meta.env.
 * Todos los demás módulos importan desde aquí para que el tipado
 * sea central y los errores de configuración aparezcan al arrancar,
 * no en tiempo de ejecución en producción.
 *
 * Cómo añadir una variable nueva:
 *   1. Declararla en .env.example con un valor por defecto comentado.
 *   2. Añadirla al objeto env abajo, con su aserción de tipo.
 *   3. El error de arranque muestra exactamente qué falta.
 */

function requireEnv(name: string, fallback?: string): string {
  const value = (import.meta.env[name] as string | undefined) ?? fallback;
  if (!value) {
    throw new Error(
      `[env] Variable de entorno requerida no definida: ${name}\n` +
        `Copia .env.example a .env.local y rellena el valor.`,
    );
  }
  return value;
}

export const env = {
  /** URL base de la API. Ej: http://127.0.0.1:8000/api */
  apiUrl: requireEnv("VITE_API_URL", "http://127.0.0.1:8000/api"),

  /**
   * Cuando es "true", el cliente HTTP apunta al mock de Prism en vez de
   * al backend real. Útil mientras el caso de uso devuelve 501.
   * Cambiar en .env.local sin tocar el código.
   */
  useMocks: import.meta.env["VITE_USE_MOCKS"] === "true",
} as const;
