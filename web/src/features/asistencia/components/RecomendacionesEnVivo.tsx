/**
 * Recomendaciones activas de un partido, en vivo  —  T-090 (CU-50).
 *
 * Como máximo 3, priorizadas. Se usa en la página de Asistencia y en el panel
 * del partido en vivo (PanelPartidoVivo, T-077).
 */
import { obtenerRolActual } from "@/shared/api/client";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge } from "@/shared/ui";

import { type CrearSocket, useRecomendaciones } from "../hooks/useRecomendaciones";
import { TarjetaRecomendacion } from "./TarjetaRecomendacion";
import "./recomendaciones.css";

export function RecomendacionesEnVivo({
  partidoId,
  crearSocket,
}: {
  partidoId: number;
  /** Solo para pruebas: reemplaza el WebSocket del navegador. */
  crearSocket?: CrearSocket;
}) {
  const { recomendaciones, cargando, error, enVivo, actualizar } = useRecomendaciones(
    partidoId,
    crearSocket,
  );
  // Mismos roles que el backend para valorar y marcar vista (T-090, T-091).
  const soloLectura = !["ADMIN", "DT", "ANALISTA"].includes(obtenerRolActual() ?? "");

  return (
    <section className="rec-lista" aria-label="Recomendaciones tácticas" data-testid="recomendaciones">
      <header className="rec-lista-cabecera">
        <h2>Recomendaciones</h2>
        <Badge tono={enVivo ? "ok" : "aviso"}>{enVivo ? "En vivo" : "Sin conexión en vivo"}</Badge>
      </header>
      {error !== null && <Alert tono="error">{mensajeDeError(error)}</Alert>}
      {cargando && <p className="rec-vacio">Cargando…</p>}
      {!cargando && error === null && recomendaciones.length === 0 && (
        <p className="rec-vacio">Sin recomendaciones activas por ahora.</p>
      )}
      {recomendaciones.map((r) => (
        <TarjetaRecomendacion
          key={r.id}
          recomendacion={r}
          alValorar={actualizar}
          soloLectura={soloLectura}
        />
      ))}
    </section>
  );
}
