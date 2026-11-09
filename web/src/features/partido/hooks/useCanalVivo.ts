/**
 * Hook del canal WebSocket `/api/partido/{id}/vivo` (CU-30, CU-32, T-068 Fase 2B).
 *
 * - Autentica en el primer mensaje `onopen` con `{"tipo":"auth","token":"..."}`
 *   leyendo un token fresco en cada intento mediante `obtenerTokenAcceso()`.
 * - Envía `{"tipo":"ping"}` cada 20 s tras recibir `{"tipo":"listo"}`.
 * - Actualiza la caché de TanStack Query al recibir `{"tipo":"estado"}`.
 * - Actualiza únicamente `calidad` al recibir `{"tipo":"posiciones"}`, acotado
 *   a como máximo una vez por segundo (sin guardar posiciones ni renderizar a 5 Hz).
 * - Reconecta con espera creciente (1, 2, 4, 8, 16 y tope 30 s) en 1006 y 4408;
 *   no reintenta en 1000, 4400, 4401 ni 4404.
 */
import type { QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { obtenerTokenAcceso } from "@/shared/api/client";
import { env } from "@/shared/config/env";

import {
  INTERVALO_MIN_CALIDAD_POSICIONES_MS,
  INTERVALO_PING_WS_MS,
  WS_CLOSE_ANORMAL,
  WS_CLOSE_MENSAJE_INVALIDO,
  WS_CLOSE_NORMAL,
  WS_CLOSE_NO_AUTENTICADO,
  WS_CLOSE_NO_ENCONTRADO,
  WS_CLOSE_TIEMPO_AGOTADO,
  calcularEsperaReconexionWsMs,
  construirUrlWsVivo,
} from "../lib/reloj";
import { calcularLatenciaWsMs, contarTracksActivos } from "../lib/calidad";
import type { EstadoCanalVivo, EstadoEnVivo, IndicadorCalidad } from "../types";

export interface EstadoHookCanalVivo {
  estado: EstadoCanalVivo;
  etiqueta: string;
  aviso: string | null;
  calidad: IndicadorCalidad | null;
  tracksActivos: number | null;
  latenciaMs: number | null;
  ultimaTelemetriaEnMs: number | null;
}

interface instantaneaCanal {
  partidoId: number;
  estado: EstadoCanalVivo;
  aviso: string | null;
  calidad: IndicadorCalidad | null;
  tracksActivos: number | null;
  latenciaMs: number | null;
  ultimaTelemetriaEnMs: number | null;
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null;
}

function esIndicadorCalidad(valor: unknown): valor is IndicadorCalidad {
  if (!esObjeto(valor)) return false;
  return (
    typeof valor["worker_conectado"] === "boolean" &&
    typeof valor["fps"] === "number" &&
    typeof valor["jugadores_detectados"] === "number" &&
    typeof valor["balon_visible"] === "boolean" &&
    typeof valor["retraso_s"] === "number" &&
    typeof valor["degradado"] === "boolean" &&
    (typeof valor["motivo"] === "string" || valor["motivo"] === null)
  );
}

function esEstadoEnVivo(valor: unknown): valor is EstadoEnVivo {
  if (!esObjeto(valor)) return false;
  return (
    typeof valor["partido_id"] === "number" &&
    typeof valor["parte"] === "number" &&
    typeof valor["minuto"] === "number" &&
    typeof valor["segundo"] === "number" &&
    typeof valor["en_curso"] === "boolean" &&
    typeof valor["goles_favor"] === "number" &&
    typeof valor["goles_contra"] === "number" &&
    (typeof valor["posesion_local_pct"] === "number" || valor["posesion_local_pct"] === null) &&
    esIndicadorCalidad(valor["calidad"])
  );
}

export function etiquetaEstadoCanalVivo(estado: EstadoCanalVivo): string {
  switch (estado) {
    case "CONECTADO":
      return "En vivo";
    case "RECONECTANDO":
      return "Reconectando…";
    case "SIN_CONEXION":
      return "Sin conexión, respaldo HTTP activo";
    case "SESION_VENCIDA":
      return "Sesión vencida";
  }
}

export function useCanalVivo(
  partidoId: number | null,
  queryClient: QueryClient,
): EstadoHookCanalVivo {
  const socketActualRef = useRef<WebSocket | null>(null);
  const [instantanea, setInstantanea] = useState<instantaneaCanal | null>(null);

  useEffect(() => {
    if (partidoId === null) {
      socketActualRef.current = null;
      return;
    }

    let cancelado = false;
    let intentos = 0;
    let ultimaActualizacionCalidadMs = 0;
    let pingEnviadoEnMs: number | null = null;
    let inicioTimeoutId: number | null = null;
    let pingIntervalId: number | null = null;
    let reintentoTimeoutId: number | null = null;

    const limpiarPing = () => {
      if (pingIntervalId !== null) {
        window.clearInterval(pingIntervalId);
        pingIntervalId = null;
      }
    };

    const limpiarReintento = () => {
      if (reintentoTimeoutId !== null) {
        window.clearTimeout(reintentoTimeoutId);
        reintentoTimeoutId = null;
      }
    };

    const actualizarEstadoCanal = (nuevoEstado: EstadoCanalVivo, aviso: string | null = null) => {
      actualizarInstantanea({
        estado: nuevoEstado,
        aviso,
      });
    };

    const actualizarInstantanea = (cambios: Partial<instantaneaCanal>) => {
      if (cancelado) return;
      setInstantanea((actual) => {
        const base: instantaneaCanal =
          actual?.partidoId === partidoId
            ? actual
            : {
                partidoId,
                estado: "SIN_CONEXION",
                aviso: null,
                calidad: null,
                tracksActivos: null,
                latenciaMs: null,
                ultimaTelemetriaEnMs: null,
              };
        return { ...base, ...cambios, partidoId };
      });
    };


    const conectar = () => {
      if (cancelado) return;
      limpiarPing();
      limpiarReintento();

      // Requisito 2: lee el access_token de nuevo en CADA intento de conexión
      const token = obtenerTokenAcceso();
      if (!token) {
        socketActualRef.current = null;
        actualizarEstadoCanal("SESION_VENCIDA", "Sesión vencida, vuelve a iniciar sesión");
        return;
      }

      const url = construirUrlWsVivo(env.apiUrl, partidoId);
      const socket = new WebSocket(url);
      socketActualRef.current = socket;

      socket.onopen = () => {
        if (cancelado || socket !== socketActualRef.current) return;
        socket.send(JSON.stringify({ tipo: "auth", token }));
      };

      socket.onmessage = (evento: MessageEvent<unknown>) => {
        if (cancelado || socket !== socketActualRef.current) return;
        if (typeof evento.data !== "string") return;

        let msg: unknown;
        try {
          msg = JSON.parse(evento.data);
        } catch {
          return;
        }
        if (!esObjeto(msg) || typeof msg["tipo"] !== "string") return;

        const tipo = msg["tipo"];

        if (tipo === "listo") {
          intentos = 0;
          actualizarEstadoCanal("CONECTADO", null);
          limpiarPing();
          const enviarPing = () => {
            if (
              !cancelado &&
              socket === socketActualRef.current &&
              socket.readyState === WebSocket.OPEN
            ) {
              pingEnviadoEnMs = performance.now();
              socket.send(JSON.stringify({ tipo: "ping" }));
            }
          };
          enviarPing();
          pingIntervalId = window.setInterval(enviarPing, INTERVALO_PING_WS_MS);
          return;
        }

        if (tipo === "pong") {
          if (pingEnviadoEnMs !== null) {
            const latenciaMs = calcularLatenciaWsMs(pingEnviadoEnMs, performance.now());
            pingEnviadoEnMs = null;
            actualizarInstantanea({ latenciaMs });
          }
          return;
        }

        if (tipo === "estado") {
          const datos = msg["datos"];
          if (!esEstadoEnVivo(datos)) return;
          const previo = queryClient.getQueryData<EstadoEnVivo>([
            "partido",
            "estado-vivo",
            partidoId,
          ]);
          queryClient.setQueryData(["partido", "estado-vivo", partidoId], datos);
          if (!previo || previo.parte !== datos.parte || previo.en_curso !== datos.en_curso) {
            void queryClient.invalidateQueries({
              queryKey: ["partido", "detalle-control", partidoId],
            });
            void queryClient.invalidateQueries({
              queryKey: ["partido", "agenda-control"],
            });
          }
          return;
        }

        if (tipo === "posiciones") {
          const datos = msg["datos"];
          if (!esObjeto(datos) || !esIndicadorCalidad(datos["calidad"])) return;
          const ahora = performance.now();
          if (ahora - ultimaActualizacionCalidadMs < INTERVALO_MIN_CALIDAD_POSICIONES_MS) {
            return;
          }
          ultimaActualizacionCalidadMs = ahora;
          const nuevaCalidad = datos["calidad"];
          actualizarInstantanea({
            calidad: nuevaCalidad,
            tracksActivos: contarTracksActivos(datos),
            ultimaTelemetriaEnMs: Date.now(),
          });
          queryClient.setQueryData<EstadoEnVivo>(["partido", "estado-vivo", partidoId], (actual) =>
            actual ? { ...actual, calidad: nuevaCalidad } : actual,
          );
        }
      };

      socket.onclose = (evento: CloseEvent) => {
        if (cancelado || socket !== socketActualRef.current) return;
        limpiarPing();
        socketActualRef.current = null;

        const codigo = evento.code;

        // 4401: sesión vencida, no reintenta
        if (codigo === WS_CLOSE_NO_AUTENTICADO) {
          actualizarEstadoCanal("SESION_VENCIDA", "Sesión vencida, vuelve a iniciar sesión");
          return;
        }

        // 4404: partido no encontrado, no reintenta y avisa
        if (codigo === WS_CLOSE_NO_ENCONTRADO) {
          actualizarEstadoCanal(
            "SIN_CONEXION",
            "Partido no encontrado en el canal en vivo (4404).",
          );
          return;
        }

        // 1000 y 4400: cierre normal o mensaje inválido, no reintenta
        if (codigo === WS_CLOSE_NORMAL || codigo === WS_CLOSE_MENSAJE_INVALIDO) {
          const aviso =
            codigo === WS_CLOSE_MENSAJE_INVALIDO
              ? "El canal en vivo se cerró por un mensaje inválido (4400)."
              : null;
          actualizarEstadoCanal("SIN_CONEXION", aviso);
          return;
        }

        // 1006, 4408 u otro corte de red: reintenta con espera creciente (1, 2, 4, 8, 16, tope 30 s)
        if (
          codigo === WS_CLOSE_ANORMAL ||
          codigo === WS_CLOSE_TIEMPO_AGOTADO ||
          codigo !== WS_CLOSE_NORMAL
        ) {
          intentos += 1;
          const esperaMs = calcularEsperaReconexionWsMs(intentos);
          actualizarEstadoCanal("RECONECTANDO", null);
          reintentoTimeoutId = window.setTimeout(conectar, esperaMs);
        }
      };

      socket.onerror = () => {
        // El navegador dispara onclose inmediatamente después de onerror; la gestión
        // de reconexión se realiza en onclose para centralizar los códigos de cierre.
      };
    };

    // Inicia asíncronamente en el próximo turno para resistir el doble montaje de
    // React.StrictMode sin abrir dos conexiones ni llamar a setState síncrono en el efecto.
    inicioTimeoutId = window.setTimeout(conectar, 0);

    return () => {
      cancelado = true;
      if (inicioTimeoutId !== null) {
        window.clearTimeout(inicioTimeoutId);
      }
      limpiarPing();
      limpiarReintento();
      const ws = socketActualRef.current;
      socketActualRef.current = null;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close(WS_CLOSE_NORMAL, "Desmontaje o cambio de partido");
      }
    };
  }, [partidoId, queryClient]);

  const estadoVigente: EstadoCanalVivo =
    partidoId !== null && instantanea !== null && instantanea.partidoId === partidoId
      ? instantanea.estado
      : "SIN_CONEXION";

  const avisoVigente: string | null =
    partidoId !== null && instantanea !== null && instantanea.partidoId === partidoId
      ? instantanea.aviso
      : null;

  return {
    estado: estadoVigente,
    etiqueta: etiquetaEstadoCanalVivo(estadoVigente),
    aviso: avisoVigente,
    calidad:
      partidoId !== null && instantanea?.partidoId === partidoId ? instantanea.calidad : null,
    tracksActivos:
      partidoId !== null && instantanea?.partidoId === partidoId ? instantanea.tracksActivos : null,
    latenciaMs:
      partidoId !== null && instantanea?.partidoId === partidoId ? instantanea.latenciaMs : null,
    ultimaTelemetriaEnMs:
      partidoId !== null && instantanea?.partidoId === partidoId
        ? instantanea.ultimaTelemetriaEnMs
        : null,
  };
}
