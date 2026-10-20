import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { logout } from "../api";
import { cerrarSesion } from "../session";

/**
 * Cierra la sesión: avisa al servidor (CU-03) y limpia la sesión local
 * aunque esa llamada falle, para no dejar al usuario atrapado.
 */
export function BotonCerrarSesion({
  className,
  children = "Cerrar sesión",
}: {
  className?: string;
  children?: ReactNode;
}) {
  const navigate = useNavigate();
  const [cerrando, setCerrando] = useState(false);

  async function alPulsar() {
    setCerrando(true);
    try {
      await logout();
    } catch {
      // Se ignora a propósito: la sesión local se limpia igualmente.
    }
    cerrarSesion();
    navigate("/login", { replace: true });
  }

  return (
    <button type="button" className={className} onClick={alPulsar} disabled={cerrando}>
      {children}
    </button>
  );
}
