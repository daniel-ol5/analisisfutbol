/**
 * Llamadas al backend de Gestión Deportiva  —  P2 (CU-09 y CU-10).
 *
 * Endpoints bajo /api/deportivo.
 */
import { api, guardarToken, leerToken } from "@/shared/api/client";
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

/**
 * Conexión rápida para desarrollo/demo: asegura una sesión activa en el club de pruebas.
 */
export async function conectarSesionDemo(): Promise<{ email: string; token: string }> {
  const creds = {
    email: "demo_admin@areatecnica.com",
    password: "Password123!",
  };

  try {
    const loginRes = await api.post("/seguridad/login", creds);
    const token = loginRes.data.access_token;
    guardarToken(token);
    return { email: creds.email, token };
  } catch (err: any) {
    if (err?.response?.status === 401 || err?.response?.status === 404) {
      // Si el usuario demo no existe aún, lo creamos
      const regRes = await api.post("/seguridad/registro", {
        nombre_club: "Club Bolívar Demo",
        ciudad: "La Paz",
        email: creds.email,
        password: creds.password,
        nombre: "Daniel",
        apellido: "DT",
      });
      const token = regRes.data.access_token;
      guardarToken(token);
      return { email: creds.email, token };
    }
    throw err;
  }
}

export function tieneSesion(): boolean {
  return Boolean(leerToken());
}
