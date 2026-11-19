/**
 * Recomendaciones activas de un partido, en vivo  —  T-090 (CU-50).
 *
 * - Carga inicial por REST (`GET .../recomendaciones`, como máximo 3).
 * - Se actualiza con el mensaje `recomendacion` del canal /vivo
 *   (docs/api/websockets.md), sin esperar al siguiente sondeo.
 * - Sin canal, recarga por REST cada INTERVALO_RESPALDO_MS como respaldo.
 *
 * Abre su propia conexión a /vivo (no toca `useCanalVivo` de T-068) y reutiliza
 * la URL y la espera de reconexión de `partido/lib/reloj.ts`.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import {
  INTERVALO_PING_WS_MS,
  WS_CLOSE_MENSAJE_INVALIDO,
  WS_CLOSE_NORMAL,
  WS_CLOSE_NO_AUTENTICADO,
  WS_CLOSE_NO_ENCONTRADO,
  calcularEsperaReconexionWsMs,
  construirUrlWsVivo,
} from "@/features/partido/lib/reloj";
import { obtenerTokenAcceso } from "@/shared/api/client";
import { env } from "@/shared/config/env";

import { listarRecomendaciones } from "../api";
import { esRecomendacion, incorporar, ordenarActivas } from "../recomendaciones";
import type { Recomendacion } from "../types";

/** Sin WebSocket, cada cuánto se vuelve a pedir la lista. */
export const INTERVALO_RESPALDO_MS = 3_000;

/** Cierres tras los que no tiene sentido reintentar (contrato de /vivo). */
const CIERRES_DEFINITIVOS = new Set([
  WS_CLOSE_NORMAL,
  WS_CLOSE_MENSAJE_INVALIDO,
  WS_CLOSE_NO_AUTENTICADO,
  WS_CLOSE_NO_ENCONTRADO,
]);

export type CrearSocket = (url: string) => WebSocket;

const socketDelNavegador: CrearSocket = (url) => new WebSocket(url);

export const claveRecomendaciones = (partidoId: number) => ["recomendaciones", partidoId] as const;

export interface EstadoRecomendaciones {
  recomendaciones: Recomendacion[];
  cargando: boolean;
  error: unknown;
  /** El canal /vivo está autenticado y recibiendo. */
  enVivo: boolean;
  /** Reemplaza una recomendación (por ejemplo, con la respuesta de valorar). */
  actualizar: (r: Recomendacion) => void;
}

export function useRecomendaciones(
  partidoId: number | null,
  crearSocket: CrearSocket = socketDelNavegador,
): EstadoRecomendaciones {
  const queryClient = useQueryClient();
  const [enVivo, setEnVivo] = useState(false);

  const consulta = useQuery({
    queryKey: claveRecomendaciones(partidoId ?? -1),
    enabled: partidoId !== null,
    queryFn: async () => ordenarActivas(await listarRecomendaciones(partidoId as number)),
    refetchInterval: enVivo ? false : INTERVALO_RESPALDO_MS,
    retry: false,
  });

  const actualizar = useCallback(
    (r: Recomendacion) => {
      if (partidoId === null) return;
      queryClient.setQueryData<Recomendacion[]>(claveRecomendaciones(partidoId), (previas) =>
        incorporar(previas ?? [], r),
      );
    },
    [partidoId, queryClient],
  );

  useEffect(() => {
    if (partidoId === null) return;
    let cancelado = false;
    let intentos = 0;
    let socket: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | null = null;
    let reintento: ReturnType<typeof setTimeout> | null = null;

    const conectar = () => {
      if (cancelado) return;
      const url = construirUrlWsVivo(env.apiUrl, partidoId, window.location.origin);
      const ws = crearSocket(url);
      socket = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ tipo: "auth", token: obtenerTokenAcceso() ?? "" }));
      };
      ws.onmessage = (evento: MessageEvent) => {
        let mensaje: unknown;
        try {
          mensaje = JSON.parse(String(evento.data));
        } catch {
          return;
        }
        if (typeof mensaje !== "object" || mensaje === null) return;
        const { tipo, datos } = mensaje as { tipo?: unknown; datos?: unknown };
        if (tipo === "listo") {
          intentos = 0;
          setEnVivo(true);
          // Lo que pasó mientras no había canal llega por REST una vez.
          void queryClient.invalidateQueries({ queryKey: claveRecomendaciones(partidoId) });
          ping = setInterval(() => ws.send(JSON.stringify({ tipo: "ping" })), INTERVALO_PING_WS_MS);
        } else if (tipo === "recomendacion" && esRecomendacion(datos) && datos.partido_id === partidoId) {
          queryClient.setQueryData<Recomendacion[]>(claveRecomendaciones(partidoId), (previas) =>
            incorporar(previas ?? [], datos),
          );
        }
      };
      ws.onclose = (evento: CloseEvent) => {
        if (ping !== null) clearInterval(ping);
        ping = null;
        socket = null;
        if (cancelado) return;
        setEnVivo(false);
        if (CIERRES_DEFINITIVOS.has(evento.code)) return; // queda el respaldo por REST
        intentos += 1;
        reintento = setTimeout(conectar, calcularEsperaReconexionWsMs(intentos));
      };
    };

    conectar();
    return () => {
      cancelado = true;
      if (ping !== null) clearInterval(ping);
      if (reintento !== null) clearTimeout(reintento);
      socket?.close(WS_CLOSE_NORMAL);
      setEnVivo(false);
    };
  }, [partidoId, crearSocket, queryClient]);

  return {
    recomendaciones: consulta.data ?? [],
    cargando: consulta.isLoading,
    error: consulta.error,
    enVivo,
    actualizar,
  };
}
