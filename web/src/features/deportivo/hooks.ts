import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listarCompeticiones, listarEquipos, programarPartido } from "./api";

export const CLAVE_EQUIPOS = ["deportivo", "equipos"] as const;
export const CLAVE_COMPETICIONES = ["deportivo", "competiciones"] as const;
export const CLAVE_PARTIDOS = ["deportivo", "partidos"] as const;

export function useEquiposParaPartido(habilitado = true) {
  return useQuery({
    queryKey: [...CLAVE_EQUIPOS, "activos"],
    queryFn: () => listarEquipos(true),
    enabled: habilitado,
  });
}

export function useCompeticiones(habilitado = true) {
  return useQuery({
    queryKey: CLAVE_COMPETICIONES,
    queryFn: listarCompeticiones,
    enabled: habilitado,
  });
}

export function useProgramarPartido() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: programarPartido,
    onSuccess: () => cliente.invalidateQueries({ queryKey: CLAVE_PARTIDOS }),
  });
}
