import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { NotificacionesWeb } from "@/features/asistencia";
import { BotonCerrarSesion, useSesion } from "@/features/seguridad";
import type { SesionGuardada } from "@/features/seguridad/types";
import { ETIQUETA_ROL } from "@/features/seguridad/types";
import { BotonTema } from "@/shared/theme/BotonTema";

import { Icono } from "@/shared/ui/Icono";

import { MODULOS } from "./navegacion";
import { puedeAcceder } from "./permisos";
import "./layout.css";

const CLAVE_MENU = "areatecnica.menu-oculto";
const PANTALLA_ESTRECHA = "(max-width: 860px)";

function observarPantalla(avisar: () => void) {
  const media = window.matchMedia(PANTALLA_ESTRECHA);
  media.addEventListener("change", avisar);
  return () => media.removeEventListener("change", avisar);
}

function pantallaEstrecha() {
  return window.matchMedia(PANTALLA_ESTRECHA).matches;
}

function leerMenuCompacto() {
  try {
    return localStorage.getItem(CLAVE_MENU) === "true";
  } catch {
    return false;
  }
}

function MenuLateral({
  usuario,
  cerrar,
  compacto = false,
}: {
  usuario: SesionGuardada["usuario"] | undefined;
  cerrar?: () => void;
  compacto?: boolean;
}) {
  const nombre = [usuario?.nombre, usuario?.apellido].filter(Boolean).join(" ") || usuario?.email;
  const iniciales = [usuario?.nombre, usuario?.apellido]
    .map((parte) => parte?.[0])
    .join("")
    .toUpperCase();
  return (
    <>
      <div className="layout-lateral-top">
        <Link
          className="layout-marca"
          to="/"
          onClick={cerrar}
          aria-label="Área Técnica"
          title={compacto ? "Área Técnica" : undefined}
        >
          <span className="layout-marca-icono">
            <Icono nombre="partido" />
          </span>
          <span className="layout-nav-etiqueta">Área Técnica</span>
        </Link>
        {cerrar && (
          <button
            type="button"
            className="layout-menu-cerrar"
            onClick={cerrar}
            aria-label="Cerrar menú"
          >
            <Icono nombre="cerrar" />
          </button>
        )}
      </div>
      <nav className="layout-nav" aria-label="Navegación principal">
        <NavLink
          to="/"
          end
          className="layout-nav-link"
          onClick={cerrar}
          aria-label="Inicio"
          title={compacto ? "Inicio" : undefined}
        >
          <Icono nombre="inicio" />
          <span className="layout-nav-etiqueta">Inicio</span>
        </NavLink>
        <ul>
          {MODULOS.filter((modulo) => puedeAcceder(usuario?.rol, modulo.ruta)).map((modulo) => (
            <li key={modulo.ruta}>
              <NavLink
                to={modulo.ruta}
                className="layout-nav-link"
                onClick={cerrar}
                aria-label={modulo.nombre}
                title={compacto ? modulo.nombre : undefined}
              >
                <Icono nombre={modulo.icono} />
                <span className="layout-nav-etiqueta">{modulo.nombre}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {usuario && (
        <div className="layout-lateral-pie">
          <Link
            to="/seguridad/perfil"
            className="layout-perfil"
            onClick={cerrar}
            aria-label="Mi perfil"
            title={compacto ? "Mi perfil" : undefined}
          >
            <span className="layout-avatar" aria-hidden="true">
              {compacto ? <Icono nombre="perfil" /> : iniciales || "AT"}
            </span>
            <span className="layout-perfil-info">
              <strong>{nombre}</strong>
              <span>{ETIQUETA_ROL[usuario.rol]}</span>
            </span>
            <Icono nombre="chevron" />
          </Link>
        </div>
      )}
    </>
  );
}

export function Layout() {
  const usuario = useSesion()?.usuario;
  const { pathname } = useLocation();
  const estrecha = useSyncExternalStore(observarPantalla, pantallaEstrecha);
  const [compacto, setCompacto] = useState(leerMenuCompacto);
  const [movilAbierto, setMovilAbierto] = useState(false);
  const dialogo = useRef<HTMLDialogElement>(null);
  const modulo = MODULOS.find(({ ruta }) => pathname === ruta || pathname.startsWith(`${ruta}/`));
  const menuExpandido = estrecha ? movilAbierto : !compacto;
  const etiquetaMenu = estrecha ? "Abrir menú" : compacto ? "Expandir menú" : "Contraer menú";

  useEffect(() => {
    dialogo.current?.close();
  }, [estrecha, pathname]);

  function alternarMenu() {
    if (estrecha) {
      dialogo.current?.showModal();
      setMovilAbierto(true);
      return;
    }
    const siguiente = !compacto;
    setCompacto(siguiente);
    try {
      localStorage.setItem(CLAVE_MENU, String(siguiente));
    } catch {
      // El menú sigue siendo operable en la sesión actual.
    }
  }

  return (
    <div className="layout">
      <aside
        id="navegacion-escritorio"
        className={`layout-lateral${compacto ? " layout-lateral--compacta" : ""}`}
      >
        <MenuLateral usuario={usuario} compacto={compacto} />
      </aside>
      <dialog
        id="navegacion-movil"
        ref={dialogo}
        className="layout-dialogo"
        aria-label="Menú de navegación"
        onClose={() => setMovilAbierto(false)}
        onClick={(evento) => {
          if (evento.target === evento.currentTarget) evento.currentTarget.close();
        }}
      >
        <div className="layout-lateral">
          <MenuLateral usuario={usuario} cerrar={() => dialogo.current?.close()} />
        </div>
      </dialog>

      <div className="layout-principal">
        <header className="layout-cabecera">
          <div className="layout-contexto">
            <button
              type="button"
              className="layout-menu"
              aria-controls={estrecha ? "navegacion-movil" : "navegacion-escritorio"}
              aria-expanded={menuExpandido}
              aria-label={etiquetaMenu}
              title={etiquetaMenu}
              onClick={alternarMenu}
            >
              <Icono nombre="menu" />
            </button>
            <span>{modulo?.nombre ?? "Inicio"}</span>
          </div>
          <div className="layout-acciones">
            <NotificacionesWeb usuarioId={usuario?.id} />
            <BotonTema />
            <BotonCerrarSesion className="ui-btn ui-btn--secundario" />
          </div>
        </header>
        <div className="layout-contenido" key={usuario?.id ?? "anon"}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
