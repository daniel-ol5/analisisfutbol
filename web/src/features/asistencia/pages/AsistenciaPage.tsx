/** Asistencia y Reportes  —  P6 · CU-49 … CU-58.
 *
 * T-090 y T-091: recomendaciones tácticas del partido elegido, en vivo, con su
 * valoración. El resto de los casos del paquete (alertas, push, catálogo,
 * informes) se suman aquí cuando estén.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listarPartidos } from "@/features/deportivo/api";
import type { Partido } from "@/features/deportivo/types";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Select } from "@/shared/ui";

import { RecomendacionesEnVivo } from "../components/RecomendacionesEnVivo";
import "../components/recomendaciones.css";

/** Primero el partido en juego; después, los más recientes. */
function ordenar(partidos: readonly Partido[]): Partido[] {
  return [...partidos].sort(
    (a, b) =>
      Number(b.estado === "EN_CURSO") - Number(a.estado === "EN_CURSO") ||
      b.fecha_hora.localeCompare(a.fecha_hora),
  );
}

export function AsistenciaPage() {
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const [elegido, setElegido] = useState<number | null>(null);
  const lista = ordenar(partidos.data ?? []);
  const partidoId = elegido ?? lista[0]?.id ?? null;

  return (
    <div className="rec-pagina">
      <h1>Asistencia táctica</h1>
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
    </div>
  );
}
