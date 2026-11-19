/** Asistencia y Reportes  —  P6 · CU-49 … CU-58.
 *
 * Pestañas del rediseño (Daniel):
 * - Recomendaciones: T-090 y T-091 (Alejandra), recomendaciones en vivo del
 *   partido elegido, con su valoración.
 * - Reglas tácticas: CU-54 / T-092 (Araceli), catálogo con activación por club,
 *   edición y prueba contra un partido.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { listarPartidos } from "@/features/deportivo/api";
import type { Partido } from "@/features/deportivo/types";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Select } from "@/shared/ui";
import { Pestanas } from "@/shared/ui/Pestanas";

import { RecomendacionesEnVivo } from "../components/RecomendacionesEnVivo";
import "../components/recomendaciones.css";
import { ReglasPage } from "./ReglasPage";

/** Primero el partido en juego; después, los más recientes. */
function ordenar(partidos: readonly Partido[]): Partido[] {
  return [...partidos].sort(
    (a, b) =>
      Number(b.estado === "EN_CURSO") - Number(a.estado === "EN_CURSO") ||
      b.fecha_hora.localeCompare(a.fecha_hora),
  );
}

function Recomendaciones() {
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const [elegido, setElegido] = useState<number | null>(null);
  const lista = ordenar(partidos.data ?? []);
  const partidoId = elegido ?? lista[0]?.id ?? null;

  return (
    <section className="rec-pagina" aria-label="Recomendaciones del partido">
      {partidos.isError && <Alert tono="error">{mensajeDeError(partidos.error)}</Alert>}
      {lista.length > 0 && (
        <Select
          etiqueta="Partido"
          value={partidoId ?? ""}
          onChange={(e) => setElegido(Number(e.target.value))}
          data-testid="asistencia-partido"
        >
          {lista.map((p) => (
            <option key={p.id} value={p.id}>
              {p.rival} · {new Date(p.fecha_hora).toLocaleDateString("es")}
              {p.estado === "EN_CURSO" ? " · en curso" : ""}
            </option>
          ))}
        </Select>
      )}
      {!partidos.isLoading && lista.length === 0 && !partidos.isError && (
        <p>No hay partidos registrados.</p>
      )}
      {partidoId !== null && <RecomendacionesEnVivo key={partidoId} partidoId={partidoId} />}
    </section>
  );
}

export function AsistenciaPage() {
  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Asistencia y reportes</h1>
      </header>
      <Pestanas
        titulo="Asistencia y reportes"
        enlaces={[
          { ruta: "/asistencia", titulo: "Recomendaciones", exacta: true },
          { ruta: "/asistencia/reglas", titulo: "Reglas tácticas" },
        ]}
      />
      <Routes>
        <Route index element={<Recomendaciones />} />
        <Route path="reglas" element={<ReglasPage />} />
        <Route path="*" element={<Navigate to="/asistencia" replace />} />
      </Routes>
    </main>
  );
}
