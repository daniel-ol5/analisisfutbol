/**
 * Layout principal: navegación lateral estructurada por categorías, cabecera y área de contenido.
 *
 * Envuelve a Inicio y a las seis secciones; /login y /registro quedan fuera.
 */
import type { ReactNode } from "react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { BotonCerrarSesion, useSesion } from "@/features/seguridad";
import { BotonTema } from "@/shared/theme/BotonTema";
import { Badge, Button } from "@/shared/ui";

import { puedeAcceder, type RutaProtegida } from "./permisos";

import "./layout.css";

interface SubEnlace {
  ruta: string;
  permiso: RutaProtegida;
  nombre: string;
}

interface ItemNav {
  ruta: string;
  permiso: RutaProtegida;
  nombre: string;
  icono: ReactNode;
  hijos?: SubEnlace[];
}

interface GrupoNav {
  categoria: string;
  items: ItemNav[];
}

const GRUPOS_NAV: GrupoNav[] = [
  {
    categoria: "Principal",
    items: [
      {
        ruta: "/",
        permiso: "/",
        nombre: "Panel de Inicio",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <rect x="2.5" y="2.5" width="6.2" height="6.2" rx="1.4" />
            <rect x="11.3" y="2.5" width="6.2" height="6.2" rx="1.4" />
            <rect x="2.5" y="11.3" width="6.2" height="6.2" rx="1.4" />
            <rect x="11.3" y="11.3" width="6.2" height="6.2" rx="1.4" />
          </svg>
        ),
      },
    ],
  },
  {
    categoria: "Competición y Visión",
    items: [
      {
        ruta: "/deportivo",
        permiso: "/deportivo",
        nombre: "Gestión Deportiva",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <path d="M10 2.2 3.5 5v4.6c0 4.2 2.8 7.5 6.5 8.6 3.7-1.1 6.5-4.4 6.5-8.6V5L10 2.2Z" />
            <path d="M7.5 10.2 9.2 12l3.5-3.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
      {
        ruta: "/vision",
        permiso: "/vision",
        nombre: "Visión por Computadora",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <path d="M2.2 10s2.9-5.2 7.8-5.2S17.8 10 17.8 10s-2.9 5.2-7.8 5.2S2.2 10 2.2 10Z" />
            <circle cx="10" cy="10" r="2.4" />
          </svg>
        ),
        hijos: [
          { ruta: "/vision/guia-montaje", permiso: "/vision", nombre: "Guía de montaje" },
          { ruta: "/vision/calibracion", permiso: "/vision", nombre: "Calibrar cámara" },
        ],
      },
      {
        ruta: "/partido",
        permiso: "/partido",
        nombre: "Operación del Partido",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <rect x="2" y="4" width="16" height="12" rx="1.8" />
            <line x1="10" y1="4" x2="10" y2="16" />
            <circle cx="10" cy="10" r="2.3" />
          </svg>
        ),
      },
    ],
  },
  {
    categoria: "Análisis y Reportes",
    items: [
      {
        ruta: "/analisis",
        permiso: "/analisis",
        nombre: "Análisis Táctico",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <path d="M3 15.5h14" strokeLinecap="round" />
            <path d="M5.5 12.5V9M10 12.5V5.5M14.5 12.5V7.5" strokeLinecap="round" />
          </svg>
        ),
      },
      {
        ruta: "/asistencia",
        permiso: "/asistencia",
        nombre: "Asistencia y Reportes",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <path d="M5.5 2.8h6.6l3.4 3.4v10a1.3 1.3 0 0 1-1.3 1.3H5.5a1.3 1.3 0 0 1-1.3-1.3V4.1a1.3 1.3 0 0 1 1.3-1.3Z" />
            <path d="M7.2 9.5h5.6M7.2 12.8h3.8" strokeLinecap="round" />
          </svg>
        ),
      },
    ],
  },
  {
    categoria: "Administración",
    items: [
      {
        ruta: "/seguridad",
        permiso: "/seguridad",
        nombre: "Seguridad y Cuenta",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <circle cx="10" cy="6.8" r="3" />
            <path d="M4.2 16.5c.8-2.8 3-4.3 5.8-4.3s5 1.5 5.8 4.3" strokeLinecap="round" />
          </svg>
        ),
        hijos: [
          { ruta: "/seguridad/perfil", permiso: "/seguridad/perfil", nombre: "Mi perfil" },
          { ruta: "/seguridad/usuarios", permiso: "/seguridad/usuarios", nombre: "Usuarios" },
        ],
      },
    ],
  },
];

export function Layout() {
  const sesion = useSesion();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const usuario = sesion?.usuario;
  const { pathname } = useLocation();
  const cerrarMenu = () => setMenuAbierto(false);

  const iniciales = usuario
    ? `${usuario.nombre.charAt(0)}${usuario.apellido.charAt(0)}`.toUpperCase()
    : "AT";

  return (
    <div className="layout">
      <aside className={`layout-lateral${menuAbierto ? " abierto" : ""}`}>
        {/* Marca / Cabecera del Sidebar */}
        <div className="layout-lateral-top">
          <Link to="/" className="layout-marca" onClick={cerrarMenu}>
            <span className="layout-marca-icono" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
                <line x1="12" y1="4.5" x2="12" y2="19.5" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </span>
            <span className="layout-marca-texto">
              <span className="layout-marca-titulo">
                Área <em>Técnica</em>
              </span>
              <span className="layout-marca-sub">Telemetría y Visión</span>
            </span>
          </Link>
        </div>

        {/* Navegación estructurada por categorías */}
        <nav className="layout-nav" aria-label="Secciones">
          {GRUPOS_NAV.map((grupo) => {
            const itemsVisibles = grupo.items.filter((item) =>
              puedeAcceder(usuario?.rol, item.permiso)
            );
            if (itemsVisibles.length === 0) return null;

            return (
              <div key={grupo.categoria} className="layout-grupo">
                <p className="layout-nav-titulo">{grupo.categoria}</p>
                <ul>
                  {itemsVisibles.map((item) => {
                    const hijos = (item.hijos ?? []).filter((h) =>
                      puedeAcceder(usuario?.rol, h.permiso)
                    );
                    const enHijo = hijos.some(
                      (h) => pathname === h.ruta || pathname.startsWith(`${h.ruta}/`)
                    );
                    return (
                      <li key={item.ruta}>
                        <NavLink
                          to={item.ruta}
                          end={item.ruta === "/" || item.hijos !== undefined}
                          className={({ isActive }) =>
                            `layout-nav-link${isActive ? " active" : ""}${enHijo ? " padre-activo" : ""}`
                          }
                          onClick={cerrarMenu}
                        >
                          <span className="layout-nav-icono">{item.icono}</span>
                          <span className="layout-nav-etiqueta">{item.nombre}</span>
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
              </div>
            );
          })}
        </nav>

        {/* Tarjeta de usuario en el pie del Sidebar */}
        {usuario && (
          <div className="layout-lateral-pie">
            <Link to="/seguridad/perfil" className="layout-perfil-card" onClick={cerrarMenu}>
              <span className="layout-avatar" aria-hidden="true">
                {iniciales}
              </span>
              <span className="layout-perfil-info">
                <span className="layout-perfil-nombre">
                  {usuario.nombre} {usuario.apellido}
                </span>
                <span className="layout-perfil-rol">{usuario.rol}</span>
              </span>
            </Link>
          </div>
        )}
      </aside>

      {menuAbierto && (
        <div className="layout-velo" aria-hidden="true" onClick={() => setMenuAbierto(false)} />
      )}

      <div className="layout-principal">
        <header className="layout-cabecera">
          <div className="layout-cabecera-izq">
            <Button
              variante="secundario"
              className="layout-menu"
              aria-expanded={menuAbierto}
              aria-label="Abrir menú de secciones"
              onClick={() => setMenuAbierto((abierto) => !abierto)}
            >
              Menú
            </Button>
            <span className="layout-contexto">Plataforma de Análisis Deportivo</span>
          </div>

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
