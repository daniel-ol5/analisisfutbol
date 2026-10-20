/**
 * Permisos de acceso a secciones: ruta → roles permitidos.
 *
 * ÚNICO lugar donde se decide quién entra a qué sección. Lo usan las guardas
 * (RequiereRol), la navegación lateral y las tarjetas de Inicio.
 *
 * Esto controla solo el ACCESO A SECCIONES. Los permisos por acción (por
 * ejemplo, que ASISTENTE no pueda modificar el plantel) irán en cada pantalla
 * y se añadirán aquí, en una tabla aparte (PERMISOS_ACCION), sin tocar esta.
 *
 * Lo no listado se deniega por defecto. El servidor es quien hace cumplir los
 * permisos de verdad; esto solo evita mostrar pantallas que el rol no puede usar.
 */
import type { Rol } from "@/features/seguridad";

/** "autenticados": cualquier usuario con sesión, sea cual sea su rol. */
type Permiso = "autenticados" | readonly Rol[];

export const PERMISOS_RUTA = {
  "/": "autenticados",
  "/seguridad": "autenticados",
  "/seguridad/perfil": "autenticados", // perfil propio
  "/seguridad/usuarios": ["ADMIN"],
  "/deportivo": ["ADMIN", "DT", "ANALISTA", "ASISTENTE"],
  "/vision": ["ADMIN", "ANALISTA"],
  "/partido": ["ADMIN", "DT", "ANALISTA", "ASISTENTE"],
  "/analisis": ["ADMIN", "DT", "ANALISTA", "ASISTENTE"],
  "/asistencia": ["ADMIN", "DT", "ANALISTA"],
  "/componentes": "autenticados", // solo existe en desarrollo
} as const satisfies Record<string, Permiso>;

export type RutaProtegida = keyof typeof PERMISOS_RUTA;

/** ¿Puede este rol entrar a esta sección? Una ruta sin entrada se deniega. */
export function puedeAcceder(rol: Rol | undefined, ruta: RutaProtegida): boolean {
  if (!rol) return false;
  const permiso: Permiso = PERMISOS_RUTA[ruta];
  return permiso === "autenticados" || permiso.includes(rol);
}
