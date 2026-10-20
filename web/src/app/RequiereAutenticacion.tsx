import { useLocation, Navigate, Outlet } from "react-router-dom";

import { useSesion } from "@/features/seguridad";

import { guardarRutaPendiente } from "./rutaPendiente";

/** Guarda de autenticación: sin sesión, redirige a /login recordando la ruta pedida. */
export function RequiereAutenticacion() {
  const sesion = useSesion();
  const ubicacion = useLocation();

  if (!sesion) {
    guardarRutaPendiente(ubicacion.pathname + ubicacion.search + ubicacion.hash);
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
