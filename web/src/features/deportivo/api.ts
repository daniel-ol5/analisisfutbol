/**
 * Llamadas al backend de Gestión Deportiva  —  P2 (CU-09 y CU-10).
 *
 * Endpoints bajo /api/deportivo.
 */
import { api } from "@/shared/api/client";
import type { AvisoColores, Equipo, EquipoCrear, EquipoEditar } from "./types";

export async function ping() {
  const { data } = await api.get("/deportivo/ping");
  return data as { paquete: string; casos_de_uso: string; estado: string };
}

/** CU-09: Listar equipos del club autenticado */
export async function listarEquipos(activos = true): Promise<Equipo[]> {
  const { data } = await api.get<Equipo[]>("/deportivo/equipos", {
    params: { activos },
  });
  return data;
}

/** CU-09: Ver detalle de un equipo */
export async function verEquipo(id: number): Promise<Equipo> {
  const { data } = await api.get<Equipo>(`/deportivo/equipos/${id}`);
  return data;
}

/** CU-09: Crear un nuevo equipo */
export async function crearEquipo(datos: EquipoCrear): Promise<Equipo> {
  const { data } = await api.post<Equipo>("/deportivo/equipos", datos);
  return data;
}

/** CU-09: Editar datos o indumentaria de un equipo */
export async function editarEquipo(
  id: number,
  datos: EquipoEditar
): Promise<Equipo> {
  const { data } = await api.patch<Equipo>(`/deportivo/equipos/${id}`, datos);
  return data;
}

/** CU-09: Desactivar equipo (baja lógica, preservando histórico) */
export async function desactivarEquipo(id: number): Promise<void> {
  await api.delete(`/deportivo/equipos/${id}`);
}

/** CU-10: Verificar contraste de colores contra un rival en espacio HSV */
export async function verificarColoresEquipo(
  equipoId: number,
  colorRival: string
): Promise<AvisoColores> {
  const { data } = await api.get<AvisoColores>(
    `/deportivo/equipos/${equipoId}/colores/verificar`,
    {
      params: { color_rival: colorRival },
    }
  );
  return data;
}
