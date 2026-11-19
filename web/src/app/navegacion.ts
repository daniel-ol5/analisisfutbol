import type { NombreIcono } from "@/shared/ui/Icono";

import type { RutaProtegida } from "./permisos";

interface Modulo {
  ruta: RutaProtegida;
  nombre: string;
  descripcion: string;
  icono: NombreIcono;
}

export const MODULOS: readonly Modulo[] = [
  {
    ruta: "/deportivo",
    nombre: "Gestión deportiva",
    descripcion: "Equipos, plantel y calendario",
    icono: "deportivo",
  },
  {
    ruta: "/vision",
    nombre: "Visión y video",
    descripcion: "Grabaciones y calibración de cámara",
    icono: "vision",
  },
  {
    ruta: "/partido",
    nombre: "Control de partido",
    descripcion: "Cronómetro, eventos y seguimiento en vivo",
    icono: "partido",
  },
  {
    ruta: "/analisis",
    nombre: "Análisis táctico",
    descripcion: "Plano 2D, métricas y red de pases",
    icono: "analisis",
  },
  {
    ruta: "/asistencia",
    nombre: "Asistencia y reportes",
    descripcion: "Recomendaciones y reglas tácticas",
    icono: "asistencia",
  },
  {
    ruta: "/seguridad",
    nombre: "Administración",
    descripcion: "Perfil y acceso al club",
    icono: "seguridad",
  },
];
