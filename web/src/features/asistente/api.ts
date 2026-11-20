/**
 * Llamadas al asistente de uso. La web habla SOLO con nuestro backend: la
 * clave de OpenAI nunca llega al navegador.
 */
import { api } from "@/shared/api/client";

import type { Pregunta, Progreso, Respuesta } from "./types";

export const LARGO_MAX_PREGUNTA = 500;
export const MAX_HISTORIAL = 6;

export async function obtenerProgreso(): Promise<Progreso> {
  const { data } = await api.get<Progreso>("/asistente/progreso", {
    params: { plataforma: "web" },
  });
  return data;
}

export async function preguntar(datos: Pregunta): Promise<Respuesta> {
  const { data } = await api.post<Respuesta>("/asistente/preguntar", datos);
  return data;
}
