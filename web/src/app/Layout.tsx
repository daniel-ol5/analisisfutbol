/**
 * Layout principal: navegación lateral, cabecera y área de contenido.
 *
 * Envuelve a Inicio y a las seis secciones; /login y /registro quedan fuera.
 */
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { BotonCerrarSesion, useSesion } from "@/features/seguridad";
import { BotonTema } from "@/shared/theme/BotonTema";
import { Badge, Button } from "@/shared/ui";

import { puedeAcceder, type RutaProtegida } from "./permisos";

import "./layout.css";

interface Seccion {
  ruta: RutaProtegida;
  nombre: string;
  /** Subenlaces, siempre visibles debajo de la sección; cada uno se filtra por permisos. */
  hijos?: { ruta: RutaProtegida; nombre: string }[];
}

const SECCIONES: Seccion[] = [
  { ruta: "/", nombre: "Inicio" },
  {
    ruta: "/seguridad",
    nombre: "Seguridad y Administración",
    hijos: [
      { ruta: "/seguridad/perfil", nombre: "Mi perfil" },
      { ruta: "/seguridad/usuarios", nombre: "Usuarios" },
    ],
  },
  { ruta: "/deportivo", nombre: "Gestión Deportiva" },
  { ruta: "/vision", nombre: "Visión por Computadora" },
  { ruta: "/partido", nombre: "Operación del Partido" },
  { ruta: "/analisis", nombre: "Análisis Táctico" },
  { ruta: "/asistencia", nombre: "Asistencia y Reportes" },
];

export function Layout() {
  const sesion = useSesion();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const usuario = sesion?.usuario;
  const { pathname } = useLocation();
  const visibles = SECCIONES.filter((s) => puedeAcceder(usuario?.rol, s.ruta));
  const cerrarMenu = () => setMenuAbierto(false);

  return (
    <div className="layout">
      <aside className={`layout-lateral${menuAbierto ? " abierto" : ""}`}>
        <Link to="/" className="layout-marca" onClick={() => setMenuAbierto(false)}>
          Área <em>Técnica</em>
        </Link>
        <nav aria-label="Secciones">
          <p className="kicker layout-nav-titulo">Secciones</p>
          <ul>
            {visibles.map((s) => {
              const hijos = (s.hijos ?? []).filter((h) => puedeAcceder(usuario?.rol, h.ruta));
              // En un subenlace, la sección padre se resalta de forma sutil.
              const enHijo = hijos.some((h) => pathname === h.ruta || pathname.startsWith(`${h.ruta}/`));
              return (
                <li key={s.ruta}>
                  <NavLink
                    to={s.ruta}
                    end={s.ruta === "/" || s.hijos !== undefined}
                    className={enHijo ? "padre-activo" : undefined}
                    onClick={cerrarMenu}
                  >
                    {s.nombre}
                  </NavLink>
                  {hijos.length > 0 && (
                    <ul className="layout-sub">
                      {hijos.map((h) => (
                        <li key={h.ruta}>
                          <NavLink to={h.ruta} onClick={cerrarMenu}>
                            {h.nombre}
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {menuAbierto && (
        <div className="layout-velo" aria-hidden="true" onClick={() => setMenuAbierto(false)} />
      )}

      <div className="layout-principal">
        <header className="layout-cabecera">
          <Button
            variante="secundario"
            className="layout-menu"
            aria-expanded={menuAbierto}
            aria-label="Abrir menú de secciones"
            onClick={() => setMenuAbierto((abierto) => !abierto)}
          >
            Menú
          </Button>
          <div className="layout-acciones">
            {usuario ? (
              <span className="layout-usuario">
                <span>
                  {usuario.nombre} {usuario.apellido}
                </span>
                <Badge tono="ok">{usuario.rol}</Badge>
              </span>
            ) : (
              <Link to="/login" className="layout-enlace">
                Iniciar sesión
              </Link>
            )}
            <BotonTema />
            {usuario && <BotonCerrarSesion className="ui-btn ui-btn--secundario" />}
          </div>
        </header>
        <div className="layout-contenido">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
