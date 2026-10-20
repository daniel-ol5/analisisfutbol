/**
 * Pantalla de inicio: los seis paquetes y el estado de la conexión con la API.
 *
 * La comprobación de salud es el «walking skeleton» del Sprint 1: si esto
 * responde, la web y el backend están hablándose de verdad.
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useSesion } from "@/features/seguridad";
import { api } from "@/shared/api/client";

import { puedeAcceder, type RutaProtegida } from "./permisos";

const PAQUETES = [
  { id: "P1", ruta: "seguridad", nombre: "Seguridad y Administración", cus: "CU-01 … CU-08" },
  { id: "P2", ruta: "deportivo", nombre: "Gestión Deportiva", cus: "CU-09 … CU-17" },
  { id: "P3", ruta: "vision", nombre: "Visión por Computadora", cus: "CU-18 … CU-29" },
  { id: "P4", ruta: "partido", nombre: "Operación del Partido", cus: "CU-30 … CU-39" },
  { id: "P5", ruta: "analisis", nombre: "Análisis Táctico", cus: "CU-40 … CU-48" },
  { id: "P6", ruta: "asistencia", nombre: "Asistencia y Reportes", cus: "CU-49 … CU-58" },
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
      <header>
        <p className="kicker">Ingeniería de Software · Scrum</p>
        <h1>
          Área <em>Técnica</em>
        </h1>
        <p className="dek">
          Análisis táctico de fútbol por visión computacional.
        </p>

        <div className={`estado ${salud.isSuccess ? "ok" : salud.isError ? "mal" : ""}`}>
          {salud.isPending && "Conectando con la API…"}
          {salud.isSuccess && `API conectada · v${salud.data.version}`}
          {salud.isError && "Sin conexión — ¿está corriendo el backend en el puerto 8000?"}
        </div>
      </header>

      <section className="paquetes">
        {paquetes.map((p) => (
          <Link key={p.id} to={`/${p.ruta}`} className="paquete">
            <span className="id">{p.id}</span>
            <h2>{p.nombre}</h2>
            <span className="cus">{p.cus}</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
