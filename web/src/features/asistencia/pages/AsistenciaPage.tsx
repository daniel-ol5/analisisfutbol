import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";

import { listarPartidos } from "@/features/deportivo/api";
import { Alert, Badge, Select } from "@/shared/ui";
import { Pestanas } from "@/shared/ui/Pestanas";

import { listarRecomendaciones, listarReglas } from "../api";
import type { Prioridad } from "../types";
import "../asistencia.css";

const PRIORIDAD: Record<Prioridad, string> = {
  CRITICA: "Crítica",
  ALTA: "Alta",
  MEDIA: "Media",
  BAJA: "Baja",
};

function Recomendaciones() {
  const [parametros, cambiarParametros] = useSearchParams();
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const partidoId = Number(parametros.get("partidoId"));
  const partido = partidos.data?.find(({ id }) => id === partidoId) ?? partidos.data?.[0];
  const recomendaciones = useQuery({
    queryKey: ["recomendaciones", partido?.id],
    queryFn: () => listarRecomendaciones(partido!.id),
    enabled: Boolean(partido),
    refetchInterval: partido?.estado === "EN_CURSO" ? 10_000 : false,
  });
  return (
    <section className="asistencia-panel" aria-label="Recomendaciones del partido">
      <Select
        etiqueta="Partido"
        value={partido?.id ?? ""}
        onChange={(evento) => cambiarParametros({ partidoId: evento.currentTarget.value })}
      >
        {!partido && (
          <option value="">{partidos.isPending ? "Cargando partidos…" : "Sin partidos"}</option>
        )}
        {partidos.data?.map(({ id, rival, fecha_hora }) => (
          <option key={id} value={id}>
            vs. {rival} · {new Date(fecha_hora).toLocaleDateString("es-BO")}
          </option>
        ))}
      </Select>
      {partidos.isError && <Alert tono="error">No se pudieron cargar los partidos.</Alert>}
      {recomendaciones.isError && (
        <Alert tono="error">No se pudieron cargar las recomendaciones.</Alert>
      )}
      {partido && recomendaciones.isPending && <p role="status">Cargando recomendaciones…</p>}
      {recomendaciones.data?.length === 0 && (
        <p>Este partido aún no tiene recomendaciones activas.</p>
      )}
      {!!recomendaciones.data?.length && (
        <ul className="asistencia-lista">
          {recomendaciones.data.map((recomendacion) => (
            <li key={recomendacion.id}>
              <div className="asistencia-fila">
                <h2>{recomendacion.mensaje}</h2>
                <Badge tono={recomendacion.prioridad === "CRITICA" ? "error" : "info"}>
                  {PRIORIDAD[recomendacion.prioridad]}
                </Badge>
              </div>
              <p>{recomendacion.justificacion}</p>
              <small>Minuto {recomendacion.minuto}</small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Reglas() {
  const reglas = useQuery({ queryKey: ["reglas-tacticas"], queryFn: listarReglas });
  return (
    <section className="asistencia-panel" aria-label="Reglas tácticas">
      {reglas.isPending && <p role="status">Cargando reglas…</p>}
      {reglas.isError && <Alert tono="error">No se pudieron cargar las reglas.</Alert>}
      {reglas.data?.length === 0 && <p>El club aún no tiene reglas disponibles.</p>}
      {!!reglas.data?.length && (
        <ul className="asistencia-lista">
          {reglas.data.map((regla) => (
            <li key={regla.id} className="asistencia-fila">
              <div>
                <h2>{regla.nombre}</h2>
                <small>Prioridad {PRIORIDAD[regla.prioridad].toLowerCase()}</small>
              </div>
              <Badge tono={regla.activa ? "ok" : "neutro"}>
                {regla.activa ? "Activa" : "Inactiva"}
              </Badge>
            </li>
          ))}
        </ul>
      )}
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
        <Route path="reglas" element={<Reglas />} />
        <Route path="*" element={<Navigate to="/asistencia" replace />} />
      </Routes>
    </main>
  );
}
