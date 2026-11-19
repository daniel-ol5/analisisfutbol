import type { ReactNode } from "react";

const trazos = {
  inicio: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  deportivo: (
    <>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 20v-2a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v2M16 4a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v2" />
    </>
  ),
  vision: (
    <>
      <rect x="3" y="5" width="13" height="14" rx="2" />
      <path d="m16 10 5-3v10l-5-3" />
    </>
  ),
  partido: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2" />
      <path d="M12 5v14M3 9h3v6H3m18-6h-3v6h3" />
      <circle cx="12" cy="12" r="2.7" />
    </>
  ),
  analisis: (
    <>
      <path d="M4 4v16h16M8 15v-4m5 4V7m5 8V9" />
    </>
  ),
  asistencia: (
    <>
      <path d="M5 21V3h10l4 4v14zM14 3v5h5M8 12h8m-8 4h6" />
    </>
  ),
  seguridad: (
    <>
      <path d="M12 3 4.5 6v5.5c0 4.5 3 7.8 7.5 9.5 4.5-1.7 7.5-5 7.5-9.5V6L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  perfil: (
    <>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5 21v-1.4a5.6 5.6 0 0 1 5.6-5.6h2.8a5.6 5.6 0 0 1 5.6 5.6V21" />
    </>
  ),
  menu: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </>
  ),
  cerrar: <path d="m6 6 12 12M18 6 6 18" />,
  flecha: <path d="M4 12h15m-6-6 6 6-6 6" />,
  chevron: <path d="m9 6 6 6-6 6" />,
} satisfies Record<string, ReactNode>;

export type NombreIcono = keyof typeof trazos;

export function Icono({ nombre }: { nombre: NombreIcono }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {trazos[nombre]}
    </svg>
  );
}
