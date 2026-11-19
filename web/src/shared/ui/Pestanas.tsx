import { NavLink } from "react-router-dom";

export interface EnlacePestana {
  ruta: string;
  titulo: string;
  exacta?: boolean;
}

export function Pestanas({
  titulo,
  enlaces,
}: {
  titulo: string;
  enlaces: readonly EnlacePestana[];
}) {
  return (
    <nav className="area-pestañas" aria-label={titulo}>
      {enlaces.map((enlace) => (
        <NavLink key={enlace.ruta} to={enlace.ruta} end={enlace.exacta}>
          {enlace.titulo}
        </NavLink>
      ))}
    </nav>
  );
}
