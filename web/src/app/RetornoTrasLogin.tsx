import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { borrarRutaPendiente, leerRutaPendiente } from "./rutaPendiente";

/**
 * Envuelve a Inicio: si el usuario llegó aquí tras iniciar sesión desde una
 * ruta protegida, lo devuelve a esa ruta en vez de dejarlo en Inicio.
 */
export function RetornoTrasLogin({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [destino] = useState(leerRutaPendiente);

  useEffect(() => {
    if (destino === null) return;
    borrarRutaPendiente();
    navigate(destino, { replace: true });
  }, [destino, navigate]);

  return destino === null ? children : null;
}
