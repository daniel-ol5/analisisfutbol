/**
 * Layout principal: navegación lateral estructurada por categorías, cabecera contextual y área de contenido.
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
            <rect x="2.5" y="2.5" width="6.2" height="6.2" rx="1.5" />
            <rect x="11.3" y="2.5" width="6.2" height="6.2" rx="1.5" />
            <rect x="2.5" y="11.3" width="6.2" height="6.2" rx="1.5" />
            <rect x="11.3" y="11.3" width="6.2" height="6.2" rx="1.5" />
          </svg>
        ),
      },
    ],
  },
  {
    categoria: "Competición y Campo",
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
    ],
  },
  {
    categoria: "Inteligencia y Reportes",
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
        ruta: "/seguridad/perfil",
        permiso: "/seguridad/perfil",
        nombre: "Mi Perfil",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <circle cx="10" cy="6.8" r="3" />
            <path d="M4.2 16.5c.8-2.8 3-4.3 5.8-4.3s5 1.5 5.8 4.3" strokeLinecap="round" />
          </svg>
        ),
      },
      {
        ruta: "/seguridad/usuarios",
        permiso: "/seguridad/usuarios",
        nombre: "Usuarios del Club",
        icono: (
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <circle cx="7.5" cy="7" r="2.6" />
            <path d="M2.8 15.8c.6-2.3 2.3-3.6 4.7-3.6s4.1 1.3 4.7 3.6" strokeLinecap="round" />
            <circle cx="13.8" cy="7.6" r="2" />
            <path d="M13.5 12.4c1.8.1 3.2 1.1 3.7 3" strokeLinecap="round" />
          </svg>
        ),
      },
    ],
  },
];

const ROL_LEGIBLE: Record<string, string> = {
  ADMIN: "Administrador",
  DT: "Director Técnico",
  ANALISTA: "Analista Táctico",
  ASISTENTE: "Asistente de Campo",
};

function obtenerSeccionActual(pathname: string): string {
  if (pathname === "/") return "Panel de Inicio";
  if (pathname.startsWith("/deportivo")) return "Gestión Deportiva";
  if (pathname.startsWith("/partido")) return "Operación del Partido";
  if (pathname.startsWith("/vision/guia-montaje")) return "Visión · Guía de Montaje";
  if (pathname.startsWith("/vision/calibracion")) return "Visión · Calibración de Cámara";
  if (pathname.startsWith("/vision")) return "Visión por Computadora";
  if (pathname.startsWith("/analisis")) return "Análisis Táctico";
  if (pathname.startsWith("/asistencia")) return "Asistencia y Reportes";
  if (pathname.startsWith("/seguridad/usuarios")) return "Administración · Usuarios";
  if (pathname.startsWith("/seguridad")) return "Administración · Mi Perfil";
  return "Área Técnica";
}

export function Layout() {
  const sesion = useSesion();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const usuario = sesion?.usuario;
  const { pathname } = useLocation();
  const cerrarMenu = () => setMenuAbierto(false);

  const iniciales = usuario
    ? `${usuario.nombre.charAt(0)}${usuario.apellido.charAt(0)}`.toUpperCase() || "AT"
    : "AT";

  const rolTexto = usuario ? (ROL_LEGIBLE[usuario.rol] ?? usuario.rol) : "";
  const seccionActual = obtenerSeccionActual(pathname);

  return (
    <div className="layout">
      <aside className={`layout-lateral${menuAbierto ? " abierto" : ""}`}>
        {/* 1. Cabecera fija de marca */}
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

        {/* 2. Navegación desplazable por bloques categorizados */}
        <nav className="layout-nav" aria-label="Secciones">
          {GRUPOS_NAV.map((grupo) => {
            const itemsVisibles = grupo.items.filter((item) =>
              puedeAcceder(usuario?.rol, item.permiso)
            );
            if (itemsVisibles.length === 0) return null;

            return (
              <div key={grupo.categoria} className="layout-grupo">
                <p className="layout-nav-titulo">{grupo.categoria}</p>
                <ul className="layout-grupo-lista">
                  {itemsVisibles.map((item) => {
                    const hijos = (item.hijos ?? []).filter((h) =>
                      puedeAcceder(usuario?.rol, h.permiso)
                    );
                    const enHijo = hijos.some(
                      (h) => pathname === h.ruta || pathname.startsWith(`${h.ruta}/`)
                    );
                    const enSeccion =
                      pathname === item.ruta ||
                      pathname.startsWith(`${item.ruta}/`) ||
                      enHijo;

                    return (
                      <li key={item.ruta} className="layout-nav-item">
                        <NavLink
                          to={item.ruta}
                          end={item.ruta === "/" || hijos.length > 0}
                          className={({ isActive }) =>
                            `layout-nav-link${isActive ? " active" : ""}${enHijo ? " padre-activo" : ""}`
                          }
                          onClick={cerrarMenu}
                        >
                          <span className="layout-nav-icono">{item.icono}</span>
                          <span className="layout-nav-etiqueta">{item.nombre}</span>
                          {hijos.length > 0 && (
                            <span
                              className={`layout-nav-chevron${enSeccion ? " abierto" : ""}`}
                              aria-hidden="true"
                            >
                              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
                                <path d="m4.5 6 3.5 3.5L11.5 6" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            </span>
                          )}
                        </NavLink>
                        {hijos.length > 0 && (
                          <ul className={`layout-sub${enSeccion ? " expandido" : ""}`}>
                            {hijos.map((h) => (
                              <li key={h.ruta}>
                                <NavLink
                                  to={h.ruta}
                                  className={({ isActive }) =>
                                    `layout-sub-link${isActive ? " active" : ""}`
                                  }
                                  onClick={cerrarMenu}
                                >
                                  <span className="layout-sub-punto" aria-hidden="true" />
                                  <span>{h.nombre}</span>
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

        {/* 3. Pie fijo del Sidebar: Ficha de usuario y estado de sesión */}
        {usuario && (
          <div className="layout-lateral-pie">
            <Link
              to="/seguridad/perfil"
              className={`layout-perfil-card${pathname === "/seguridad/perfil" ? " activo" : ""}`}
              onClick={cerrarMenu}
              title="Ir a Mi Perfil"
            >
              <span className="layout-avatar" aria-hidden="true">
                {iniciales}
              </span>
              <span className="layout-perfil-info">
                <span className="layout-perfil-nombre">
                  {usuario.nombre} {usuario.apellido}
                </span>
                <span className="layout-perfil-rol">{rolTexto}</span>
              </span>
              <span className="layout-perfil-flecha" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75">
                  <path d="m6 4 4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
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
            <div className="layout-migas">
              <span className="layout-migas-raiz">Área Técnica</span>
              <span className="layout-migas-sep" aria-hidden="true">/</span>
              <span className="layout-contexto">{seccionActual}</span>
            </div>
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
