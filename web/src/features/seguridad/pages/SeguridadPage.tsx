import { Outlet } from "react-router-dom";

import { Pestanas } from "@/shared/ui/Pestanas";

import { useSesion } from "../session";

export function SeguridadPage() {
  const administrador = useSesion()?.usuario.rol === "ADMIN";
  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Administración</h1>
      </header>
      <Pestanas
        titulo="Administración"
        enlaces={[
          { ruta: "/seguridad/perfil", titulo: "Mi perfil" },
          ...(administrador ? [{ ruta: "/seguridad/usuarios", titulo: "Usuarios del club" }] : []),
        ]}
      />
      <div className="area-contenido administracion-contenido">
        <Outlet />
      </div>
    </main>
  );
}
