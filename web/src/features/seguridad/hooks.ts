/** Hooks de TanStack Query de Seguridad y Administración. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  actualizarUsuario,
  cambiarPassword,
  crearUsuario,
  editarPerfil,
  listarUsuarios,
  obtenerPerfil,
} from "./api";
import { actualizarUsuario as guardarUsuarioEnSesion } from "./session";
import type { ActualizarUsuario } from "./types";

const CLAVE_USUARIOS = ["seguridad", "usuarios"] as const;
const CLAVE_PERFIL = ["seguridad", "yo"] as const;

export function useUsuarios() {
  return useQuery({ queryKey: CLAVE_USUARIOS, queryFn: listarUsuarios });
}

export function useCrearUsuario() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: crearUsuario,
    onSuccess: () => cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  });
}

export function useActualizarUsuario() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, cambios }: { id: number; cambios: ActualizarUsuario }) =>
      actualizarUsuario(id, cambios),
    onSuccess: () => cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  });
}

export function usePerfil() {
  return useQuery({ queryKey: CLAVE_PERFIL, queryFn: obtenerPerfil });
}

/** Al guardar, actualiza la caché y la sesión (la cabecera muestra el nombre nuevo). */
export function useEditarPerfil() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: editarPerfil,
    onSuccess: (usuario) => {
      cliente.setQueryData(CLAVE_PERFIL, usuario);
      guardarUsuarioEnSesion(usuario);
      return cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS });
    },
  });
}

export function useCambiarPassword() {
  return useMutation({ mutationFn: cambiarPassword });
}
