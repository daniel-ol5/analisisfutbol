/**
 * CU-34, CU-35 · Panel de asignación de jugadores a identificadores (tracks)
 * con lista del plantel al lado (T-072, Fase 2A).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import { asignarTrackPartido, listarJugadoresPlantelPartido, listarTracksPartido } from "../api";
import {
  INTERVALO_REFRESCO_TRACKS_MS,
  describirEquipoDetectado,
  es404TrackNoEncontrado,
  esTrackRivalOArbitro,
  unirTracksParaVista,
} from "../lib/tracks";
import type {
  EquipoDetectado,
  JugadorPlantelPartido,
  ResumenPartidoControl,
  TrackEnVivoLigero,
  TrackUnificadoVista,
} from "../types";

export interface PanelAsignacionTracksProps {
  partidoId: number;
  partido: ResumenPartidoControl | undefined;
  puedeOperar: boolean;
  /** En Fase 2A se recibe vacío; en Fase 2B se conectará con los `tid` vistos en vivo. */
  tracksEnVivo?: readonly TrackEnVivoLigero[];
}

interface ConfirmacionPendiente {
  trackId: number;
  jugadorId: number | null;
  motivos: string[];
}

interface ErrorAsignacion {
  mensaje: string;
  status: number | null;
}

const VACIO_VIVO: readonly TrackEnVivoLigero[] = [];

function claseInsigniaEquipo(equipo: EquipoDetectado, esLocal: boolean): string {
  if (equipo === "ARBITRO") return "par-badge-equipo par-badge-equipo--arbitro";
  if (equipo === "DESCONOCIDO") return "par-badge-equipo par-badge-equipo--desconocido";
  const esPropio = (esLocal && equipo === "LOCAL") || (!esLocal && equipo === "VISITANTE");
  return esPropio
    ? "par-badge-equipo par-badge-equipo--propio"
    : "par-badge-equipo par-badge-equipo--rival";
}

function formatearJugadorCorto(j: JugadorPlantelPartido): string {
  return `#${j.dorsal} ${j.apellido}, ${j.nombre} (${j.posicion})`;
}

export function PanelAsignacionTracks({
  partidoId,
  partido,
  puedeOperar,
  tracksEnVivo = VACIO_VIVO,
}: PanelAsignacionTracksProps) {
  const esLocal = partido?.es_local ?? true;
  const equipoId = partido?.equipo_id ?? null;

  // Sondeo de tracks vigentes cada 5 s
  const tracksQuery = useQuery({
    queryKey: ["partido", "tracks-activos", partidoId],
    queryFn: () => listarTracksPartido(partidoId, true),
    refetchInterval: INTERVALO_REFRESCO_TRACKS_MS,
  });

  // Plantel activo del equipo del partido
  const plantelQuery = useQuery({
    queryKey: ["partido", "plantel-equipo", equipoId],
    queryFn: () => listarJugadoresPlantelPartido(equipoId as number),
    enabled: equipoId !== null,
  });

  // Refetch al volver a la pestaña (visibilitychange)
  useEffect(() => {
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") {
        void tracksQuery.refetch();
        if (equipoId !== null) {
          void plantelQuery.refetch();
        }
      }
    };
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    return () => {
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, [equipoId, tracksQuery, plantelQuery]);

  // Unión de los tramos vigentes (GET solo_activos=true) y los tid vistos en vivo (2B)
  const tracksVista = useMemo(
    () => unirTracksParaVista(tracksQuery.data ?? [], tracksEnVivo),
    [tracksQuery.data, tracksEnVivo],
  );

  const plantel = useMemo(() => plantelQuery.data ?? [], [plantelQuery.data]);

  const jugadorPorId = useMemo(() => {
    const mapa = new Map<number, JugadorPlantelPartido>();
    for (const j of plantel) {
      mapa.set(j.id, j);
    }
    return mapa;
  }, [plantel]);

  // Mapa jugador_id -> track_id vigente (un jugador solo puede estar en un track vigente)
  const trackPorJugadorId = useMemo(() => {
    const mapa = new Map<number, number>();
    for (const t of tracksVista) {
      if (t.jugador_id !== null) {
        mapa.set(t.jugador_id, t.track_id);
      }
    }
    return mapa;
  }, [tracksVista]);

  // Estado de interacción de la vista (asociado a partidoId para limpiarse al cambiar de partido)
  const [estadoInteraccion, setEstadoInteraccion] = useState<{
    partidoId: number;
    trackResaltadoId: number | null;
    borradorJugadorPorTrack: Record<number, string>;
    confirmacion: ConfirmacionPendiente | null;
    aviso404: string | null;
    error: ErrorAsignacion | null;
  }>({
    partidoId,
    trackResaltadoId: null,
    borradorJugadorPorTrack: {},
    confirmacion: null,
    aviso404: null,
    error: null,
  });

  const interaccionVigente =
    estadoInteraccion.partidoId === partidoId
      ? estadoInteraccion
      : {
          partidoId,
          trackResaltadoId: null,
          borradorJugadorPorTrack: {},
          confirmacion: null,
          aviso404: null,
          error: null,
        };

  function actualizarInteraccion(parcial: Partial<typeof interaccionVigente>) {
    setEstadoInteraccion((prev) => {
      const base =
        prev.partidoId === partidoId
          ? prev
          : {
              partidoId,
              trackResaltadoId: null,
              borradorJugadorPorTrack: {},
              confirmacion: null,
              aviso404: null,
              error: null,
            };
      return { ...base, ...parcial };
    });
  }

  const asignarMut = useMutation({
    mutationFn: (vars: { trackId: number; jugadorId: number | null }) =>
      asignarTrackPartido(partidoId, vars.trackId, { jugador_id: vars.jugadorId }),
    onSuccess: (_datos, vars) => {
      const copiaBorrador = { ...interaccionVigente.borradorJugadorPorTrack };
      delete copiaBorrador[vars.trackId];
      actualizarInteraccion({
        borradorJugadorPorTrack: copiaBorrador,
        confirmacion: null,
        aviso404: null,
        error: null,
      });
      void tracksQuery.refetch();
    },
    onError: (err: unknown) => {
      const status = estadoHttp(err) ?? null;
      const mensaje = mensajeDeError(err);
      // Requisito 7: tras cada PUT, error o 404, refresca los tracks
      void tracksQuery.refetch();

      // Requisito 4: 404 «Track no encontrado en este partido» es aviso suave
      if (es404TrackNoEncontrado(status, mensaje)) {
        actualizarInteraccion({
          confirmacion: null,
          error: null,
          aviso404: "El identificador aún se está registrando; inténtalo de nuevo en unos segundos",
        });
        return;
      }

      actualizarInteraccion({
        confirmacion: null,
        aviso404: null,
        error: { mensaje, status },
      });
    },
  });

  const putEnVuelo = asignarMut.isPending;
  const controlesDeshabilitados = !puedeOperar || putEnVuelo;

  function valorSelectTrack(track: TrackUnificadoVista): string {
    const enBorrador = interaccionVigente.borradorJugadorPorTrack[track.track_id];
    if (enBorrador !== undefined) return enBorrador;
    return track.jugador_id !== null ? String(track.jugador_id) : "";
  }

  function cambiarSelectTrack(trackId: number, valor: string) {
    actualizarInteraccion({
      trackResaltadoId: trackId,
      confirmacion:
        interaccionVigente.confirmacion?.trackId === trackId
          ? null
          : interaccionVigente.confirmacion,
      borradorJugadorPorTrack: {
        ...interaccionVigente.borradorJugadorPorTrack,
        [trackId]: valor,
      },
    });
  }

  function solicitarAsignacion(track: TrackUnificadoVista) {
    const valorRaw = valorSelectTrack(track);
    if (!valorRaw) return;
    const jugadorIdElegido = Number(valorRaw);
    if (!Number.isInteger(jugadorIdElegido) || jugadorIdElegido <= 0) return;

    // Si ya tiene asignado ese mismo jugador, no hace falta reenviar
    if (track.jugador_id === jugadorIdElegido) return;

    const motivos: string[] = [];

    if (esTrackRivalOArbitro(track.equipo_detectado, esLocal)) {
      motivos.push("Este identificador figura como rival/árbitro. ¿Asignarlo de todos modos?");
    }

    const trackPrevioDelJugador = trackPorJugadorId.get(jugadorIdElegido);
    if (trackPrevioDelJugador !== undefined && trackPrevioDelJugador !== track.track_id) {
      motivos.push(
        `El jugador elegido ya está activo en otro identificador: se cerrará su tramo en el Track #${trackPrevioDelJugador} y continuará aquí.`,
      );
    }

    if (track.jugador_id !== null && track.jugador_id !== jugadorIdElegido) {
      const jugadorAnterior = jugadorPorId.get(track.jugador_id);
      const etiquetaAnterior = jugadorAnterior
        ? formatearJugadorCorto(jugadorAnterior)
        : `Jugador #${track.jugador_id}`;
      motivos.push(
        `El Track #${track.track_id} dejará de estar asociado a ${etiquetaAnterior} a partir del instante actual.`,
      );
    }

    if (motivos.length > 0) {
      actualizarInteraccion({
        trackResaltadoId: track.track_id,
        confirmacion: {
          trackId: track.track_id,
          jugadorId: jugadorIdElegido,
          motivos,
        },
      });
      return;
    }

    asignarMut.mutate({ trackId: track.track_id, jugadorId: jugadorIdElegido });
  }

  function solicitarDesasignacion(track: TrackUnificadoVista) {
    if (track.jugador_id === null) return;
    actualizarInteraccion({
      trackResaltadoId: track.track_id,
      confirmacion: {
        trackId: track.track_id,
        jugadorId: null,
        motivos: [
          `¿Desasignar el Track #${track.track_id}? Se cerrará su tramo vigente en el instante actual.`,
        ],
      },
    });
  }

  function reintentarConsultas() {
    actualizarInteraccion({ error: null, aviso404: null });
    void tracksQuery.refetch();
    if (equipoId !== null) {
      void plantelQuery.refetch();
    }
  }

  const errorCarga =
    tracksQuery.isError || plantelQuery.isError
      ? {
          mensaje: mensajeDeError(tracksQuery.error ?? plantelQuery.error),
          status: estadoHttp(tracksQuery.error ?? plantelQuery.error) ?? null,
        }
      : null;

  return (
    <div>
      {/* Aviso permanente de máximo 2 líneas sobre métricas de equipo vs individuales */}
      <p className="par-aviso-metricas" role="note">
        Un identificador sin asignar aporta a las métricas de equipo, pero no genera métricas
        individuales. Reasignar tras una oclusión cierra el tramo anterior y continúa las métricas
        del jugador sin reiniciarlas.
      </p>

      {errorCarga && (
        <div className="par-alerta-error" role="alert">
          <p className="par-alerta-error-titulo">
            Error al cargar identificadores o plantel
            {errorCarga.status ? ` (HTTP ${errorCarga.status})` : ""}
          </p>
          <p className="par-alerta-error-mensaje">{errorCarga.mensaje}</p>
          <div className="par-alerta-acciones">
            <button type="button" className="par-btn" onClick={reintentarConsultas}>
              Reintentar
            </button>
          </div>
        </div>
      )}

      {interaccionVigente.aviso404 && (
        <div className="par-aviso-suave" role="status">
          <span>{interaccionVigente.aviso404}</span>
          <button
            type="button"
            className="par-btn"
            disabled={putEnVuelo}
            onClick={reintentarConsultas}
          >
            Reintentar
          </button>
        </div>
      )}

      {interaccionVigente.error && (
        <div className="par-alerta-error" role="alert">
          <p className="par-alerta-error-titulo">
            No se pudo guardar la asignación
            {interaccionVigente.error.status ? ` (HTTP ${interaccionVigente.error.status})` : ""}
          </p>
          <p className="par-alerta-error-mensaje">{interaccionVigente.error.mensaje}</p>
          <div className="par-alerta-acciones">
            <button
              type="button"
              className="par-btn"
              disabled={putEnVuelo}
              onClick={reintentarConsultas}
            >
              Reintentar
            </button>
          </div>
        </div>
      )}

      <div className="par-asignacion-layout">
        {/* Columna izquierda: Lista de tracks vigentes */}
        <section className="par-tarjeta" aria-label="Identificadores detectados">
          <div className="par-cronometro-cabecera">
            <h2 className="par-seccion-titulo">
              Identificadores detectados ({tracksVista.length})
            </h2>
            <button
              type="button"
              className="par-btn"
              disabled={putEnVuelo || tracksQuery.isFetching}
              onClick={() => void tracksQuery.refetch()}
            >
              Actualizar lista
            </button>
          </div>

          {tracksVista.length === 0 ? (
            <p className="par-subtitulo">
              Aún no hay identificadores vigentes para este partido. Aparecerán automáticamente
              cuando el worker publique detecciones en <code>/ingesta</code>.
            </p>
          ) : (
            <ul className="par-tracks-lista">
              {tracksVista.map((track) => {
                const jugadorActual =
                  track.jugador_id !== null ? jugadorPorId.get(track.jugador_id) : undefined;
                const valorSelect = valorSelectTrack(track);
                const jugadorElegidoNum = valorSelect ? Number(valorSelect) : null;
                const sinCambioSeleccion =
                  jugadorElegidoNum === null || jugadorElegidoNum === track.jugador_id;
                const esResaltado = interaccionVigente.trackResaltadoId === track.track_id;
                const confFila =
                  interaccionVigente.confirmacion?.trackId === track.track_id
                    ? interaccionVigente.confirmacion
                    : null;

                return (
                  <li
                    key={track.track_id}
                    className={`par-track-fila ${esResaltado ? "par-track-fila--resaltada" : ""}`}
                    onClick={() => actualizarInteraccion({ trackResaltadoId: track.track_id })}
                  >
                    <div className="par-track-principal">
                      <div className="par-track-identidad">
                        <span className="par-track-id">Track #{track.track_id}</span>
                        <span className={claseInsigniaEquipo(track.equipo_detectado, esLocal)}>
                          {describirEquipoDetectado(track.equipo_detectado, esLocal)}
                        </span>
                        <span className="par-meta-reloj">
                          Conf. {Math.round(track.confianza * 100)} %
                          {track.desde_t !== null ? ` · desde ${Math.floor(track.desde_t)} s` : ""}
                        </span>
                      </div>

                      <div className="par-track-estado-actual">
                        Asignación actual:{" "}
                        <strong>
                          {jugadorActual
                            ? formatearJugadorCorto(jugadorActual)
                            : track.jugador_id !== null
                              ? `Jugador #${track.jugador_id}`
                              : "Sin asignar"}
                        </strong>
                      </div>
                    </div>

                    <div className="par-track-controles" onClick={(e) => e.stopPropagation()}>
                      <select
                        aria-label={`Seleccionar jugador para Track #${track.track_id}`}
                        className="par-select par-track-select"
                        value={valorSelect}
                        disabled={controlesDeshabilitados}
                        onChange={(e) => cambiarSelectTrack(track.track_id, e.target.value)}
                      >
                        <option value="">— Seleccionar jugador del plantel —</option>
                        {plantel.map((j) => {
                          const trackDelJugador = trackPorJugadorId.get(j.id);
                          const sufijoTrack =
                            trackDelJugador !== undefined
                              ? trackDelJugador === track.track_id
                                ? " (asignado aquí)"
                                : ` (en Track #${trackDelJugador})`
                              : "";
                          return (
                            <option key={j.id} value={j.id}>
                              {formatearJugadorCorto(j)}
                              {sufijoTrack}
                            </option>
                          );
                        })}
                      </select>

                      <button
                        type="button"
                        className="par-btn par-btn--primario"
                        disabled={controlesDeshabilitados || sinCambioSeleccion}
                        onClick={() => solicitarAsignacion(track)}
                      >
                        {track.jugador_id === null ? "Asignar" : "Reasignar"}
                      </button>

                      {track.jugador_id !== null && (
                        <button
                          type="button"
                          className="par-btn"
                          disabled={controlesDeshabilitados}
                          onClick={() => solicitarDesasignacion(track)}
                        >
                          Desasignar
                        </button>
                      )}
                    </div>

                    {confFila && (
                      <div
                        className="par-track-confirmacion"
                        role="region"
                        aria-label={`Confirmación para Track #${track.track_id}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {confFila.motivos.map((motivo, idx) => (
                          <p key={idx} className="par-track-confirmacion-texto">
                            {motivo}
                          </p>
                        ))}
                        <div className="par-acciones-fila">
                          <button
                            type="button"
                            className="par-btn par-btn--primario"
                            disabled={controlesDeshabilitados}
                            onClick={() =>
                              asignarMut.mutate({
                                trackId: confFila.trackId,
                                jugadorId: confFila.jugadorId,
                              })
                            }
                          >
                            {putEnVuelo ? "Guardando…" : "Confirmar"}
                          </button>
                          <button
                            type="button"
                            className="par-btn"
                            disabled={putEnVuelo}
                            onClick={() => actualizarInteraccion({ confirmacion: null })}
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* Columna derecha: Lista del plantel */}
        <aside className="par-tarjeta" aria-label="Plantel del equipo">
          <h2 className="par-seccion-titulo">Plantel ({plantel.length})</h2>
          <p className="par-meta-reloj">
            Haz clic en un jugador con track activo para resaltarlo en la lista.
          </p>

          {plantel.length === 0 ? (
            <p className="par-subtitulo">No hay jugadores activos registrados en este equipo.</p>
          ) : (
            <ul className="par-plantel-lista">
              {plantel.map((j) => {
                const trackAsignado = trackPorJugadorId.get(j.id) ?? null;
                const estaResaltado =
                  trackAsignado !== null && interaccionVigente.trackResaltadoId === trackAsignado;

                return (
                  <li key={j.id}>
                    <button
                      type="button"
                      className={`par-plantel-item ${
                        estaResaltado ? "par-plantel-item--resaltado" : ""
                      }`}
                      onClick={() => {
                        if (trackAsignado !== null) {
                          actualizarInteraccion({ trackResaltadoId: trackAsignado });
                        }
                      }}
                    >
                      <span className="par-plantel-dorsal">#{j.dorsal}</span>
                      <span className="par-plantel-nombre">
                        {j.apellido}, {j.nombre}
                      </span>
                      <span className="par-plantel-pos">{j.posicion}</span>
                      <span
                        className={
                          trackAsignado !== null
                            ? "par-plantel-track par-plantel-track--activo"
                            : "par-plantel-track"
                        }
                      >
                        {trackAsignado !== null ? `Track #${trackAsignado}` : "Sin track activo"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
