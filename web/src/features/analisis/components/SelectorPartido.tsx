import { usePartidosAnalisis } from "../hooks/usePartidosAnalisis";

interface Props {
  valor: number | null;
  onCambiar: (id: number) => void;
}

export function SelectorPartido({ valor, onCambiar }: Props) {
  const { partidos, equipos, id } = usePartidosAnalisis(valor);
  return (
    <>
      <label>
        Partido{" "}
        <select
          aria-label="Seleccionar partido"
          value={id ?? ""}
          onChange={(e) => onCambiar(Number(e.target.value))}
        >
          {!partidos.data?.length && (
            <option value="">{partidos.isPending ? "Cargando…" : "Sin partidos"}</option>
          )}
          {partidos.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {equipos.data?.find((e) => e.id === p.equipo_id)?.nombre ?? "Equipo"} · {p.rival}
            </option>
          ))}
        </select>
      </label>
      {(partidos.isError || equipos.isError) && (
        <p role="alert">No se pudieron cargar los partidos. Revisa la conexión con la API.</p>
      )}
    </>
  );
}
