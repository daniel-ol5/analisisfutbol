/**
 * Llamadas al backend de Gestión Deportiva  —  P2 (CU-09 y CU-10).
 *
 * Endpoints bajo /api/deportivo.
 */
import { api } from "@/shared/api/client";
import type {
  AvisoColores,
  Equipo,
  EquipoCrear,
  EquipoEditar,
  Jugador,
  JugadorCrear,
  JugadorEditar,
  OrdenJugadores,
  ResultadoImportacion,
} from "./types";

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
export async function editarEquipo(id: number, datos: EquipoEditar): Promise<Equipo> {
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
  colorRival: string,
): Promise<AvisoColores> {
  const { data } = await api.get<AvisoColores>(`/deportivo/equipos/${equipoId}/colores/verificar`, {
    params: { color_rival: colorRival },
  });
  return data;
}

/** CU-11: Listar el plantel de un equipo */
export async function listarJugadores(
  equipoId: number,
  activos = true,
  orden: OrdenJugadores = "dorsal",
): Promise<Jugador[]> {
  const { data } = await api.get<Jugador[]>(`/deportivo/equipos/${equipoId}/jugadores`, {
    params: { activos, orden },
  });
  return data;
}

/** CU-11: Crear jugador */
export async function crearJugador(datos: JugadorCrear): Promise<Jugador> {
  const { data } = await api.post<Jugador>("/deportivo/jugadores", datos);
  return data;
}

/** CU-11: Ver ficha de jugador */
export async function verJugador(id: number): Promise<Jugador> {
  const { data } = await api.get<Jugador>(`/deportivo/jugadores/${id}`);
  return data;
}

/** CU-11: Editar jugador */
export async function editarJugador(id: number, datos: JugadorEditar): Promise<Jugador> {
  const { data } = await api.patch<Jugador>(`/deportivo/jugadores/${id}`, datos);
  return data;
}

/** CU-11: Dar de baja un jugador (conserva su historial) */
export async function bajaJugador(id: number): Promise<void> {
  await api.delete(`/deportivo/jugadores/${id}`);
}

/**
 * CU-12: Importar plantel desde CSV.
 *
 * Con `confirmar=false` devuelve la vista previa sin guardar nada; con
 * `confirmar=true` persiste las filas válidas. El archivo se reenvía en
 * ambas llamadas porque el backend no conserva el upload entre peticiones.
 */
export async function importarPlantel(
  equipoId: number,
  archivo: File,
  confirmar = false,
): Promise<ResultadoImportacion> {
  const formData = new FormData();
  formData.append("archivo", archivo);
  const { data } = await api.post<ResultadoImportacion>(
    `/deportivo/equipos/${equipoId}/jugadores/importar`,
    formData,
    { params: { confirmar }, headers: { "Content-Type": undefined } },
  );
  return data;
}
