import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listarEquipos, listarPartidos } from "@/features/deportivo/api";

export function usePartidoUrl() {
  const [parametros, cambiarParametros] = useSearchParams();
  const id = Number(parametros.get("partidoId"));
  const elegir = (partidoId: number) => {
    cambiarParametros((actuales) => {
      const siguientes = new URLSearchParams(actuales);
      siguientes.set("partidoId", String(partidoId));
      return siguientes;
    });
  };
  return { partidoId: Number.isSafeInteger(id) && id > 0 ? id : null, elegir };
}

/** Lista de partidos del club; el primero queda elegido si no hay selección (como el panel en vivo). */
export function usePartidosAnalisis(seleccionado: number | null) {
  const equipos = useQuery({ queryKey: ["equipos"], queryFn: () => listarEquipos() });
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const id = seleccionado ?? partidos.data?.[0]?.id ?? null;
  const partido = partidos.data?.find((p) => p.id === id);
  const equipo = equipos.data?.find((e) => e.id === partido?.equipo_id);
  return {
    id,
    partido,
    equipos,
    partidos,
    nombreLocal: partido?.es_local ? (equipo?.nombre ?? "Local") : (partido?.rival ?? "Local"),
    nombreVisitante: partido?.es_local ? partido.rival : (equipo?.nombre ?? "Visitante"),
  };
}
