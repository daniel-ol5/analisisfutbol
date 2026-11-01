/**
 * Pantalla de inicio: los seis paquetes y el estado de la conexión con la API.
 *
 * La comprobación de salud es el «walking skeleton» del Sprint 1: si esto
 * responde, la web y el backend están hablándose de verdad.
 */
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSesion } from "@/features/seguridad";
import { api } from "@/shared/api/client";

import { puedeAcceder, type RutaProtegida } from "./permisos";

interface PaqueteInfo {
  id: string;
  ruta: string;
  nombre: string;
  descripcion: string;
  cus: string;
  icono: ReactNode;
}

const PAQUETES: PaqueteInfo[] = [
  {
    id: "P1",
    ruta: "seguridad",
    nombre: "Seguridad y Administración",
    descripcion: "Control de acceso basado en roles, gestión de usuarios del club y perfil personal.",
    cus: "CU-01 … CU-08",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <circle cx="10" cy="6.8" r="3" />
        <path d="M4.2 16.5c.8-2.8 3-4.3 5.8-4.3s5 1.5 5.8 4.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "P2",
    ruta: "deportivo",
    nombre: "Gestión Deportiva",
    descripcion: "Equipos, validación óptica de indumentaria, planteles de jugadores y calendario.",
    cus: "CU-09 … CU-17",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M10 2.2 3.5 5v4.6c0 4.2 2.8 7.5 6.5 8.6 3.7-1.1 6.5-4.4 6.5-8.6V5L10 2.2Z" />
        <path d="M7.5 10.2 9.2 12l3.5-3.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "P3",
    ruta: "vision",
    nombre: "Visión por Computadora",
    descripcion: "Guía de montaje de cámara, calibración homográfica de cancha y procesamiento óptico.",
    cus: "CU-18 … CU-29",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M2.2 10s2.9-5.2 7.8-5.2S17.8 10 17.8 10s-2.9 5.2-7.8 5.2S2.2 10 2.2 10Z" />
        <circle cx="10" cy="10" r="2.4" />
      </svg>
    ),
  },
  {
    id: "P4",
    ruta: "partido",
    nombre: "Operación del Partido",
    descripcion: "Monitoreo en tiempo real, eventos del encuentro y seguimiento posicional en cancha.",
    cus: "CU-30 … CU-39",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <rect x="2" y="4" width="16" height="12" rx="1.8" />
        <line x1="10" y1="4" x2="10" y2="16" />
        <circle cx="10" cy="10" r="2.3" />
      </svg>
    ),
  },
  {
    id: "P5",
    ruta: "analisis",
    nombre: "Análisis Táctico",
    descripcion: "Mapas de calor, distancias recorridas, velocidades y líneas de presión colectiva.",
    cus: "CU-40 … CU-48",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M3 15.5h14" strokeLinecap="round" />
        <path d="M5.5 12.5V9M10 12.5V5.5M14.5 12.5V7.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "P6",
    ruta: "asistencia",
    nombre: "Asistencia y Reportes",
    descripcion: "Informes post-partido, comparativas de rendimiento y exportación ejecutiva.",
    cus: "CU-49 … CU-58",
    icono: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M5.5 2.8h6.6l3.4 3.4v10a1.3 1.3 0 0 1-1.3 1.3H5.5a1.3 1.3 0 0 1-1.3-1.3V4.1a1.3 1.3 0 0 1 1.3-1.3Z" />
        <path d="M7.2 9.5h5.6M7.2 12.8h3.8" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function Inicio() {
  const rol = useSesion()?.usuario.rol;
  const paquetes = PAQUETES.filter((p) => puedeAcceder(rol, `/${p.ruta}` as RutaProtegida));
  const salud = useQuery({
    queryKey: ["salud"],
    queryFn: async () => {
      const { data } = await api.get("/salud");
      return data as { estado: string; proyecto: string; version: string };
    },
  });

  return (
    <main className="inicio">
      <header className="inicio-hero">
        <div className="inicio-hero-texto">
          <p className="kicker">Ingeniería de Software · Scrum</p>
          <h1>
            Área <em>Técnica</em>
          </h1>
          <p className="dek">
            Plataforma de análisis táctico y telemetría de fútbol mediante visión por computadora.
          </p>
        </div>

        <div className={`estado ${salud.isSuccess ? "ok" : salud.isError ? "mal" : ""}`}>
          <span className="estado-punto" aria-hidden="true" />
          <span>
            {salud.isPending && "Conectando con la API…"}
            {salud.isSuccess && `API conectada · v${salud.data.version}`}
            {salud.isError && "Sin conexión — ¿está corriendo el backend en el puerto 8000?"}
          </span>
        </div>
      </header>

      <div className="inicio-seccion-cabecera">
        <h2 className="inicio-seccion-titulo">Módulos del Sistema</h2>
        <p className="inicio-seccion-sub">{paquetes.length} paquetes habilitados para tu rol</p>
      </div>

      <section className="paquetes">
        {paquetes.map((p) => (
          <Link key={p.id} to={`/${p.ruta}`} className="paquete">
            <div>
              <div className="paquete-top">
                <span className="paquete-icono">{p.icono}</span>
                <span className="id">{p.id}</span>
              </div>
              <h2>{p.nombre}</h2>
              <p className="paquete-desc">{p.descripcion}</p>
            </div>
            <div className="paquete-pie">
              <span className="cus">{p.cus}</span>
              <span className="paquete-flecha">Abrir módulo →</span>
            </div>
          </Link>
        ))}
      </section>
    </main>
  );
}
