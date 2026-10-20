import type { ReactNode } from "react";

import { useSesion } from "@/features/seguridad";

import { Prohibido } from "./Prohibido";
import { puedeAcceder, type RutaProtegida } from "./permisos";

/** Guarda de rol: si el rol no está permitido para `ruta` (ver permisos.ts), muestra el 403. */
export function RequiereRol({ ruta, children }: { ruta: RutaProtegida; children: ReactNode }) {
  const sesion = useSesion();
  if (!puedeAcceder(sesion?.usuario.rol, ruta)) return <Prohibido />;
  return children;
}
