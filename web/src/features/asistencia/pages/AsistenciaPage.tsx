import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";

import { listarPartidos } from "@/features/deportivo/api";
import type { Partido } from "@/features/deportivo/types";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Select } from "@/shared/ui";
import { Pestanas } from "@/shared/ui/Pestanas";

import { RecomendacionesEnVivo } from "../components/RecomendacionesEnVivo";
import { ReglasPage } from "./ReglasPage";
import "../asistencia.css";

function ordenar(partidos: readonly Partido[]): Partido[] {
  return [...partidos].sort(
    (a, b) =>
      Number(b.estado === "EN_CURSO") - Number(a.estado === "EN_CURSO") ||
      b.fecha_hora.localeCompare(a.fecha_hora),
  );
}

function Recomendaciones() {
  const [parametros, cambiarParametros] = useSearchParams();
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const lista = ordenar(partidos.data ?? []);
  const elegido = Number(parametros.get("partidoId"));
  const partidoId = (lista.find((partido) => partido.id === elegido) ?? lista[0])?.id;

  return (
    <section className="asistencia-panel" aria-label="Recomendaciones del partido">
      {partidos.isError && <Alert tono="error">{mensajeDeError(partidos.error)}</Alert>}
      {partidos.isPending && <p role="status">Cargando partidos…</p>}
      {partidos.isSuccess && lista.length === 0 && <p>No hay partidos registrados.</p>}
      {partidoId !== undefined && (
        <>
          <Select
            etiqueta="Partido"
            value={partidoId}
            onChange={(evento) => cambiarParametros({ partidoId: evento.currentTarget.value })}
            data-testid="asistencia-partido"
          >
            {lista.map((partido) => (
              <option key={partido.id} value={partido.id}>
                vs. {partido.rival} · {new Date(partido.fecha_hora).toLocaleDateString("es-BO")}
                {partido.estado === "EN_CURSO" ? " · en curso" : ""}
              </option>
            ))}
          </Select>
          <RecomendacionesEnVivo key={partidoId} partidoId={partidoId} />
        </>
      )}
    </section>
  );
}

export function AsistenciaPage() {
  const { search } = useLocation();
  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Asistencia y reportes</h1>
      </header>
      <Pestanas
        titulo="Asistencia y reportes"
        enlaces={[
          { ruta: `/asistencia${search}`, titulo: "Recomendaciones", exacta: true },
          { ruta: `/asistencia/reglas${search}`, titulo: "Reglas tácticas" },
        ]}
      />
      <div className="area-contenido">
        <Routes>
          <Route index element={<Recomendaciones />} />
          <Route path="reglas" element={<ReglasPage />} />
          <Route path="*" element={<Navigate to="/asistencia" replace />} />
        </Routes>
      </div>
    </main>
  );
}
