import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listarCompeticiones, listarEquipos, listarPartidos, programarPartido } from "./api";
import type { FiltrosPartidos } from "./types";

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

export function useEquiposAgenda(habilitado = true) {
  return useQuery({
    queryKey: [...CLAVE_EQUIPOS, "todos"],
    queryFn: () => listarEquipos(false),
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

export function usePartidos(filtros: FiltrosPartidos, habilitado = true) {
  return useQuery({
    queryKey: [...CLAVE_PARTIDOS, filtros],
    queryFn: () => listarPartidos(filtros),
    enabled: habilitado,
  });
}
