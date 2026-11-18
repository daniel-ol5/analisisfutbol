import { useQuery } from "@tanstack/react-query";
import { listarEquipos, listarPartidos } from "@/features/deportivo/api";

interface Props { valor: number | null; onCambiar: (id: number) => void }

/** Lista de partidos del club; el primero queda elegido si no hay selección (como el panel en vivo). */
export function usePartidosAnalisis(seleccionado: number | null) {
  const equipos = useQuery({ queryKey: ["equipos"], queryFn: () => listarEquipos() });
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const id = seleccionado ?? partidos.data?.[0]?.id ?? null;
  const partido = partidos.data?.find(p => p.id === id);
  const equipo = equipos.data?.find(e => e.id === partido?.equipo_id);
  return {
    id, partido, equipos, partidos,
    nombreLocal: partido?.es_local ? equipo?.nombre ?? "Local" : partido?.rival ?? "Local",
    nombreVisitante: partido?.es_local ? partido.rival : equipo?.nombre ?? "Visitante",
  };
}

export function SelectorPartido({ valor, onCambiar }: Props) {
  const { partidos, equipos, id } = usePartidosAnalisis(valor);
  return <>
    <label>Partido <select aria-label="Seleccionar partido" value={id ?? ""} onChange={e => onCambiar(Number(e.target.value))}>
      {!partidos.data?.length && <option value="">{partidos.isPending ? "Cargando…" : "Sin partidos"}</option>}
      {partidos.data?.map(p => <option key={p.id} value={p.id}>{equipos.data?.find(e => e.id === p.equipo_id)?.nombre ?? "Equipo"} · {p.rival}</option>)}
    </select></label>
    {(partidos.isError || equipos.isError) && <p role="alert">No se pudieron cargar los partidos. Revisa la conexión con la API.</p>}
  </>;
}
