/** Hooks de TanStack Query de Seguridad y Administración. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  actualizarUsuario,
  cambiarPassword,
  crearUsuario,
  editarPerfil,
  eliminarUsuario,
  listarUsuarios,
  obtenerPerfil,
  obtenerUsuario,
} from "./api";
import {
  actualizarUsuario as guardarUsuarioEnSesion,
  iniciarSesion,
  obtenerSesion,
  useSesion,
} from "./session";
import type { ActualizarUsuario } from "./types";

const CLAVE_USUARIOS = ["seguridad", "usuarios"] as const;
const CLAVE_PERFIL = ["seguridad", "yo"] as const;

export function useUsuarios() {
  return useQuery({ queryKey: CLAVE_USUARIOS, queryFn: listarUsuarios });
}

export function useUsuario(id: number | null) {
  return useQuery({
    queryKey: [...CLAVE_USUARIOS, id],
    queryFn: () => obtenerUsuario(id!),
    enabled: id !== null,
  });
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
    onSuccess: (usuarioActualizado) => {
      const sesionActual = obtenerSesion();
      if (sesionActual && sesionActual.usuario.id === usuarioActualizado.id) {
        guardarUsuarioEnSesion(usuarioActualizado);
        cliente.invalidateQueries({ queryKey: CLAVE_PERFIL });
      }
      return cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS });
    },
  });
}

export function useEliminarUsuario() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => eliminarUsuario(id),
    onSuccess: () => cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  });
}

export function usePerfil() {
  const sesion = useSesion();
  return useQuery({
    queryKey: [...CLAVE_PERFIL, sesion?.usuario.id ?? null],
    queryFn: obtenerPerfil,
  });
}

/** Al guardar, actualiza la caché y la sesión (la cabecera muestra el nombre nuevo). */
export function useEditarPerfil() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: editarPerfil,
    onSuccess: (usuario) => {
      cliente.setQueryData([...CLAVE_PERFIL, usuario.id], usuario);
      guardarUsuarioEnSesion(usuario);
      return cliente.invalidateQueries({ queryKey: CLAVE_USUARIOS });
    },
  });
}

/** El token anterior ya no sirve: se guarda la sesión nueva para no caer al login. */
export function useCambiarPassword() {
  return useMutation({ mutationFn: cambiarPassword, onSuccess: iniciarSesion });
}
