/**
 * Hook de suscripción en tiempo real al canal del partido en vivo  —  CU-40 · T-077.
 *
 * Se conecta a `ws://<host>/api/partido/{partidoId}/vivo`.
 * Realiza el handshake de autenticación enviando el token en el primer mensaje.
 * Implementa latido con `ping`/`pong` cada 20 segundos y reconexión automática
 * con retroceso exponencial ante desconexiones de red.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { obtenerSesion } from "@/features/seguridad/session";
import { env } from "@/shared/config/env";

import type {
  EstadoConexion,
  MensajeWebSocketVivo,
  MensajeWorker,
  PuntoTrayectoria,
} from "../types";

const NO_REINTENTAR = new Set([1000, 4400, 4401, 4404]);
const MAX_ESTELA_BALON = 25;
const VENTANA_POSESION_FRAMES = 300; // ~60 segundos a 5 Hz

interface OpcionesUsoPartidoEnVivo {
  partidoId: number | null;
  activo?: boolean;
}

interface ResultadoPartidoEnVivo {
  estadoConexion: EstadoConexion;
  datos: MensajeWorker | null;
  posesionLocalPct: number;
  posesionVisitantePct: number;
  estelaBalon: PuntoTrayectoria[];
  error: string | null;
  reconectar: () => void;
  desconectar: () => void;
}

export function usePartidoEnVivo({
  partidoId,
  activo = true,
}: OpcionesUsoPartidoEnVivo): ResultadoPartidoEnVivo {
  const [estadoConexion, setEstadoConexion] = useState<EstadoConexion>("desconectado");
  const [datos, setDatos] = useState<MensajeWorker | null>(null);
  const [posesionLocalPct, setPosesionLocalPct] = useState<number>(50);
  const [posesionVisitantePct, setPosesionVisitantePct] = useState<number>(50);
  const [estelaBalon, setEstelaBalon] = useState<PuntoTrayectoria[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const cerradoManualRef = useRef<boolean>(false);
  const reintentoRef = useRef<number>(0);
  const timerReintentoRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerLatidoRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ejecutarConexionRef = useRef<() => void>(() => {});

  // Buffer circular para cálculo de posesión en tiempo real
  const bufferPosesionRef = useRef<Array<"LOCAL" | "VISITANTE">>([]);

  const limpiarTemporizadores = useCallback(() => {
    if (timerReintentoRef.current) {
      clearTimeout(timerReintentoRef.current);
      timerReintentoRef.current = null;
    }
    if (timerLatidoRef.current) {
      clearInterval(timerLatidoRef.current);
      timerLatidoRef.current = null;
    }
  }, []);

  const desconectar = useCallback(() => {
    cerradoManualRef.current = true;
    limpiarTemporizadores();
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, "Cierre solicitado");
      } catch {
        // Ignorar si ya está cerrado
      }
      wsRef.current = null;
    }
    setEstadoConexion("desconectado");
  }, [limpiarTemporizadores]);

  const conectar = useCallback(() => {
    if (!partidoId || !activo) {
      desconectar();
      return;
    }

    // Reiniciar estado previo al cambiar de partido o reconectar
    setDatos(null);
    setEstelaBalon([]);
    bufferPosesionRef.current = [];
    setPosesionLocalPct(50);
    setPosesionVisitantePct(50);

    limpiarTemporizadores();
    cerradoManualRef.current = false;
    setError(null);
    setEstadoConexion((prev) => (prev === "desconectado" ? "conectando" : "reconectando"));

    const sesion = obtenerSesion();
    const token = sesion?.access_token;
    if (!token) {
      setError("No hay sesión activa para autenticar la transmisión.");
      setEstadoConexion("error");
      return;
    }

    const baseWs = env.apiUrl.replace(/^http/, "ws");
    const wsUrl = `${baseWs}/partido/${partidoId}/vivo`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Primer mensaje del contrato WebSocket: autenticación con Bearer token
        ws.send(JSON.stringify({ tipo: "auth", token }));
      };

      ws.onmessage = (evento: MessageEvent<string>) => {
        try {
          const mensaje = JSON.parse(evento.data) as MensajeWebSocketVivo;

          if (mensaje.tipo === "listo") {
            setEstadoConexion("conectado");
            setError(null);
            reintentoRef.current = 0;

            // Iniciar latido cada 20 segundos para mantener vivo el canal
            if (timerLatidoRef.current) clearInterval(timerLatidoRef.current);
            timerLatidoRef.current = setInterval(() => {
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ tipo: "ping" }));
              }
            }, 20_000);
            return;
          }

          if (mensaje.tipo === "pong") {
            return;
          }

          if (mensaje.tipo === "posiciones") {
            const workerData = mensaje.datos;
            setDatos(workerData);

            // Actualizar trayectoria reciente del balón si está visible
            if (workerData.balon) {
              const nuevoPunto: PuntoTrayectoria = {
                x: workerData.balon.x,
                y: workerData.balon.y,
                t: workerData.t,
              };
              setEstelaBalon((prev) => {
                const siguiente = [...prev, nuevoPunto];
                return siguiente.length > MAX_ESTELA_BALON
                  ? siguiente.slice(siguiente.length - MAX_ESTELA_BALON)
                  : siguiente;
              });

              // Estimar posesión según cercanía al balón (< 3 metros)
              let equipoCercano: "LOCAL" | "VISITANTE" | null = null;
              let distMinima = 3.0; // radio de control en metros

              for (const j of workerData.jugadores) {
                if (j.equipo !== "LOCAL" && j.equipo !== "VISITANTE") continue;
                const dx = j.x - workerData.balon.x;
                const dy = j.y - workerData.balon.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < distMinima) {
                  distMinima = dist;
                  equipoCercano = j.equipo;
                }
              }

              if (equipoCercano) {
                const buf = bufferPosesionRef.current;
                buf.push(equipoCercano);
                if (buf.length > VENTANA_POSESION_FRAMES) {
                  buf.shift();
                }

                const localTicks = buf.filter((eq) => eq === "LOCAL").length;
                const totalTicks = buf.length;
                if (totalTicks > 0) {
                  const pctLocal = Math.round((localTicks / totalTicks) * 100);
                  setPosesionLocalPct(pctLocal);
                  setPosesionVisitantePct(100 - pctLocal);
                }
              }
            }
          }

          if (mensaje.tipo === "error") {
            setError("Error reportado por el servidor en la transmisión.");
          }
        } catch {
          // Ignorar frames no serializables en JSON
        }
      };

      ws.onclose = (evento: CloseEvent) => {
        limpiarTemporizadores();

        if (cerradoManualRef.current || NO_REINTENTAR.has(evento.code)) {
          if (evento.code === 4401) {
            setError("Token inválido o expirado. Vuelve a iniciar sesión.");
            setEstadoConexion("error");
          } else if (evento.code === 4404) {
            setError("Partido no encontrado o no pertenece a tu club.");
            setEstadoConexion("error");
          } else if (evento.code === 4400) {
            setError("Error en el formato de mensajes del cliente.");
            setEstadoConexion("error");
          } else {
            setEstadoConexion("desconectado");
          }
          return;
        }

        // Desconexión inesperada de red o código 1006 / 4408: reconexión automática
        setEstadoConexion("reconectando");
        const espera = Math.min(30_000, 1_000 * 2 ** reintentoRef.current);
        reintentoRef.current += 1;

        timerReintentoRef.current = setTimeout(() => {
          ejecutarConexionRef.current();
        }, espera);
      };

      ws.onerror = () => {
        // El evento de cierre manejará la reconexión
      };
    } catch {
      setError("No se pudo establecer la conexión WebSocket.");
      setEstadoConexion("error");
    }
  }, [partidoId, activo, desconectar, limpiarTemporizadores]);

  // Mantener referencia actualizada para reintentos sin dependencias circulares
  useEffect(() => {
    ejecutarConexionRef.current = conectar;
  }, [conectar]);

  useEffect(() => {
    const timer = setTimeout(() => {
      conectar();
    }, 0);
    return () => {
      clearTimeout(timer);
      desconectar();
    };
  }, [conectar, desconectar]);

  const reconectar = useCallback(() => {
    reintentoRef.current = 0;
    conectar();
  }, [conectar]);

  return {
    estadoConexion,
    datos,
    posesionLocalPct,
    posesionVisitantePct,
    estelaBalon,
    error,
    reconectar,
    desconectar,
  };
}
