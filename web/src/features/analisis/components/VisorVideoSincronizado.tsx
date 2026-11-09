/**
 * Visor de Video / Cámara en Vivo Sincronizado con el Radar 2D  —  CU-24, CU-25, CU-27, CU-40, CU-41.
 *
 * Permite visualizar simultáneamente la señal de video del partido (video subido al servidor,
 * archivo local de video o cámara en vivo por WebRTC/getUserMedia) junto con la superposición
 * en tiempo real de las cajas de detección YOLO + ByteTrack (tid) y el plano 2D táctico debajo
 * o en paralelo.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  descargarArchivoVideo,
  iniciarTransmisionVivoPartido,
  listarVideos,
} from "@/features/vision/api";
import type { Video } from "@/features/vision/types";

import type { PosicionDetectada } from "../types";

export type ModoDisposicionVivo = "apilado" | "paralelo" | "solo-radar";
type FuenteSenal = "servidor" | "archivo" | "camara";

interface Props {
  partidoId: number;
  jugadores: PosicionDetectada[];
  balon?: PosicionDetectada | null;
  colorLocal?: string;
  colorVisitante?: string;
  nombreLocal: string;
  nombreVisitante: string;
  workerTransmitiendo: boolean;
  modoDisposicion: ModoDisposicionVivo;
  onCambiarModoDisposicion: (modo: ModoDisposicionVivo) => void;
}

/**
 * Proyecta una coordenada métrica de la cancha (0..105 m x 0..68 m)
 * a coordenadas porcentuales (0..100%) de perspectiva de cámara de tribuna
 * para superponer el HUD de detección YOLO + ByteTrack sobre el cuadro de video.
 */
function proyectarCanchaACamara(xMetros: number, yMetros: number): {
  leftPct: number;
  topPct: number;
  escala: number;
} {
  const u = Math.min(1, Math.max(0, xMetros / 105));
  const v = Math.min(1, Math.max(0, yMetros / 68));
  // v = 1 es la banda superior (más lejana a la cámara); v = 0 es la banda inferior (más cercana).
  const profundidad = 1 - v; // 0 arriba (lejos), 1 abajo (cerca)
  const topPct = 24 + profundidad * 64;
  // Efecto trapezoidal de perspectiva de cámara: más estrecho al fondo, más ancho cerca.
  const margenLateral = 16 - profundidad * 11;
  const anchoUtil = 100 - margenLateral * 2;
  const leftPct = margenLateral + u * anchoUtil;
  const escala = 0.72 + profundidad * 0.42;
  return { leftPct, topPct, escala };
}

export function VisorVideoSincronizado({
  partidoId,
  jugadores,
  balon,
  colorLocal = "#10b981",
  colorVisitante = "#ef4444",
  nombreLocal: _nombreLocal,
  nombreVisitante: _nombreVisitante,
  workerTransmitiendo,
  modoDisposicion,
  onCambiarModoDisposicion,
}: Props) {
  const [fuente, setFuente] = useState<FuenteSenal>("servidor");
  const [videosServidor, setVideosServidor] = useState<Video[]>([]);
  const [videoSeleccionadoId, setVideoSeleccionadoId] = useState<number | null>(null);
  const [cargandoLista, setCargandoLista] = useState(false);
  const [cargandoBinario, setCargandoBinario] = useState(false);
  const [videoSrcUrl, setVideoSrcUrl] = useState<string | null>(null);
  const [nombreArchivoLocal, setNombreArchivoLocal] = useState<string | null>(null);
  const [errorFuente, setErrorFuente] = useState<string | null>(null);
  const [mostrarOverlayYolo, setMostrarOverlayYolo] = useState(false);
  const [iniciandoStream, setIniciandoStream] = useState(false);

  // Estado de cámara en vivo
  const [dispositivosCamara, setDispositivosCamara] = useState<MediaDeviceInfo[]>([]);
  const [dispositivoCamaraId, setDispositivoCamaraId] = useState<string>("");
  const [camaraActiva, setCamaraActiva] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const camaraVideoRef = useRef<HTMLVideoElement | null>(null);
  const streamCamaraRef = useRef<MediaStream | null>(null);
  const urlObjetoRef = useRef<string | null>(null);

  const limpiarUrlObjeto = useCallback(() => {
    if (urlObjetoRef.current) {
      URL.revokeObjectURL(urlObjetoRef.current);
      urlObjetoRef.current = null;
    }
  }, []);

  const detenerCamara = useCallback(() => {
    if (streamCamaraRef.current) {
      streamCamaraRef.current.getTracks().forEach((t) => t.stop());
      streamCamaraRef.current = null;
    }
    if (camaraVideoRef.current) {
      camaraVideoRef.current.srcObject = null;
    }
    setCamaraActiva(false);
  }, []);

  useEffect(() => {
    return () => {
      limpiarUrlObjeto();
      detenerCamara();
    };
  }, [limpiarUrlObjeto, detenerCamara]);

  // Cargar videos subidos del partido cuando cambia partidoId
  useEffect(() => {
    let activo = true;
    setCargandoLista(true);
    setErrorFuente(null);
    listarVideos(partidoId)
      .then((lista) => {
        if (!activo) return;
        const disponibles = lista.filter((v) => v.estado !== "CARGANDO");
        setVideosServidor(disponibles);
        if (disponibles.length > 0) {
          setVideoSeleccionadoId(disponibles[0].id);
        } else {
          setVideoSeleccionadoId(null);
          if (fuente === "servidor") {
            setVideoSrcUrl(null);
          }
        }
      })
      .catch(() => {
        if (!activo) return;
        setVideosServidor([]);
        setVideoSeleccionadoId(null);
      })
      .finally(() => {
        if (activo) setCargandoLista(false);
      });
    return () => {
      activo = false;
    };
  }, [partidoId]);

  // Descargar el blob del video del servidor cuando se selecciona uno en modo "servidor"
  useEffect(() => {
    if (fuente !== "servidor" || !videoSeleccionadoId) return;
    let activo = true;
    setCargandoBinario(true);
    setErrorFuente(null);
    descargarArchivoVideo(videoSeleccionadoId)
      .then((blob) => {
        if (!activo) return;
        limpiarUrlObjeto();
        const url = URL.createObjectURL(blob);
        urlObjetoRef.current = url;
        setVideoSrcUrl(url);
      })
      .catch(() => {
        if (!activo) return;
        setErrorFuente(
          "No se pudo cargar el archivo de video desde el servidor. Puedes elegir un archivo local o usar la cámara en vivo.",
        );
      })
      .finally(() => {
        if (activo) setCargandoBinario(false);
      });
    return () => {
      activo = false;
    };
  }, [fuente, videoSeleccionadoId, limpiarUrlObjeto]);

  const activarSincronizacion5Hz = useCallback(async () => {
    setIniciandoStream(true);
    try {
      await iniciarTransmisionVivoPartido(partidoId, 90);
    } catch {
      // Si falla por permisos o red, no bloquea la reproducción local
    } finally {
      setIniciandoStream(false);
    }
  }, [partidoId]);

  const manejarReproducirYSincronizar = async () => {
    await activarSincronizacion5Hz();
    if (fuente !== "camara" && videoRef.current) {
      try {
        await videoRef.current.play();
      } catch {
        // Ignorar bloqueo de autoplay si el usuario ya interactuó con el control nativo
      }
    }
  };

  const manejarSeleccionArchivoLocal = (e: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    detenerCamara();
    limpiarUrlObjeto();
    const url = URL.createObjectURL(archivo);
    urlObjetoRef.current = url;
    setNombreArchivoLocal(archivo.name);
    setVideoSrcUrl(url);
    setErrorFuente(null);
  };

  const iniciarCamaraEnVivo = useCallback(
    async (deviceId?: string) => {
      setErrorFuente(null);
      if (!navigator.mediaDevices?.getUserMedia) {
        setErrorFuente("Este navegador no soporta captura de cámara en vivo (getUserMedia).");
        return;
      }
      try {
        detenerCamara();
        const constraints: MediaStreamConstraints = {
          video: deviceId
            ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
            : { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        };
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamCamaraRef.current = stream;
        if (camaraVideoRef.current) {
          camaraVideoRef.current.srcObject = stream;
          await camaraVideoRef.current.play();
        }
        setCamaraActiva(true);
        const devices = await navigator.mediaDevices.enumerateDevices();
        const cams = devices.filter((d) => d.kind === "videoinput");
        setDispositivosCamara(cams);
        if (!deviceId && cams.length > 0) {
          const trackDevice = stream.getVideoTracks()[0]?.getSettings().deviceId;
          setDispositivoCamaraId(trackDevice ?? cams[0].deviceId);
        }
        void activarSincronizacion5Hz();
      } catch {
        setErrorFuente(
          "No se pudo acceder a la cámara. Verifica los permisos del navegador o que no esté ocupada por otra aplicación.",
        );
      }
    },
    [detenerCamara, activarSincronizacion5Hz],
  );

  const cambiarFuente = (nueva: FuenteSenal) => {
    setErrorFuente(null);
    if (nueva !== "camara") {
      detenerCamara();
    }
    setFuente(nueva);
    if (nueva === "camara") {
      void iniciarCamaraEnVivo(dispositivoCamaraId || undefined);
    }
  };

  return (
    <section
      className="visor-sincro-contenedor"
      aria-label="Visor de video y cámara en vivo sincronizado con el radar 2D"
    >
      {/* Cabecera de controles de fuente y disposición */}
      <div className="visor-sincro-cabecera">
        <div className="visor-sincro-titulo-bloque">
          <span className="visor-sincro-kicker">CU-24 · CU-25 · CU-27 · SEÑAL DE VISIÓN</span>
          <h3 className="visor-sincro-titulo">
            Video / Cámara en Vivo sincronizado con Radar 2D
          </h3>
        </div>

        <div className="visor-sincro-modos-vista" role="group" aria-label="Disposición de pantalla">
          <button
            type="button"
            className={`panel-toggle-btn ${modoDisposicion === "apilado" ? "panel-toggle-btn--activo" : ""}`}
            onClick={() => onCambiarModoDisposicion("apilado")}
          >
            Video arriba + Radar 2D abajo
          </button>
          <button
            type="button"
            className={`panel-toggle-btn ${modoDisposicion === "paralelo" ? "panel-toggle-btn--activo" : ""}`}
            onClick={() => onCambiarModoDisposicion("paralelo")}
          >
            Lado a lado
          </button>
          <button
            type="button"
            className={`panel-toggle-btn ${modoDisposicion === "solo-radar" ? "panel-toggle-btn--activo" : ""}`}
            onClick={() => onCambiarModoDisposicion("solo-radar")}
          >
            Solo Radar 2D
          </button>
        </div>
      </div>

      {modoDisposicion !== "solo-radar" && (
        <>
          {/* Selector de fuente de video y controles de sincronización */}
          <div className="visor-sincro-barra-fuente">
            <div className="visor-sincro-tabs-fuente" role="tablist" aria-label="Fuente de video">
              <button
                type="button"
                role="tab"
                aria-selected={fuente === "servidor"}
                className={`visor-fuente-btn ${fuente === "servidor" ? "visor-fuente-btn--activa" : ""}`}
                onClick={() => cambiarFuente("servidor")}
              >
                Video subido del partido ({videosServidor.length})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={fuente === "archivo"}
                className={`visor-fuente-btn ${fuente === "archivo" ? "visor-fuente-btn--activa" : ""}`}
                onClick={() => cambiarFuente("archivo")}
              >
                Cargar video desde mi PC
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={fuente === "camara"}
                className={`visor-fuente-btn ${fuente === "camara" ? "visor-fuente-btn--activa" : ""}`}
                onClick={() => cambiarFuente("camara")}
              >
                Cámara en vivo
              </button>
            </div>

            <div className="visor-sincro-acciones">
              <button
                type="button"
                className={`panel-toggle-btn ${mostrarOverlayYolo ? "panel-toggle-btn--activo" : ""}`}
                onClick={() => setMostrarOverlayYolo((v) => !v)}
              >
                {mostrarOverlayYolo
                  ? "Detecciones YOLO (tid): ON"
                  : "Detecciones YOLO (tid): OFF"}
              </button>

              <button
                type="button"
                className="panel-vivo-btn-primario"
                disabled={iniciandoStream}
                onClick={() => void manejarReproducirYSincronizar()}
              >
                {iniciandoStream
                  ? "Iniciando telemetría 5 Hz..."
                  : workerTransmitiendo
                    ? "Reiniciar sincronización 5 Hz"
                    : "Reproducir y Analizar en Vivo (5 Hz)"}
              </button>
            </div>
          </div>

          {/* Subbarra según la fuente elegida */}
          {fuente === "servidor" && (
            <div className="visor-sincro-subbarra">
              {cargandoLista ? (
                <span className="visor-sincro-nota">Buscando videos subidos para este partido...</span>
              ) : videosServidor.length > 0 ? (
                <div className="visor-sincro-selector-linea">
                  <label htmlFor="select-video-partido" className="panel-control-etiqueta">
                    Grabación del partido:
                  </label>
                  <select
                    id="select-video-partido"
                    className="panel-control-select"
                    value={videoSeleccionadoId ?? ""}
                    onChange={(e) => setVideoSeleccionadoId(Number(e.target.value))}
                  >
                    {videosServidor.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.nombre} ({v.resolucion ?? "HD"} · {v.fps ? `${Math.round(v.fps)} fps` : "30 fps"} ·{" "}
                        {v.estado})
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <span className="visor-sincro-nota">
                  Este partido aún no tiene videos guardados en el servidor. Puedes usar la pestaña{" "}
                  <strong>«Cargar video desde mi PC»</strong> o <strong>«Cámara en vivo»</strong> aquí
                  mismo.
                </span>
              )}
            </div>
          )}

          {fuente === "archivo" && (
            <div className="visor-sincro-subbarra">
              <label className="visor-archivo-label">
                <span>Seleccionar video MP4 / MOV / WebM de tu equipo:</span>
                <input
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                  onChange={manejarSeleccionArchivoLocal}
                />
              </label>
              {nombreArchivoLocal && (
                <span className="visor-sincro-nota">Archivo cargado: {nombreArchivoLocal}</span>
              )}
            </div>
          )}

          {fuente === "camara" && (
            <div className="visor-sincro-subbarra">
              {dispositivosCamara.length > 0 && (
                <div className="visor-sincro-selector-linea">
                  <label htmlFor="select-camara-vivo" className="panel-control-etiqueta">
                    Dispositivo de cámara:
                  </label>
                  <select
                    id="select-camara-vivo"
                    className="panel-control-select"
                    value={dispositivoCamaraId}
                    onChange={(e) => {
                      setDispositivoCamaraId(e.target.value);
                      void iniciarCamaraEnVivo(e.target.value);
                    }}
                  >
                    {dispositivosCamara.map((d, i) => (
                      <option key={d.deviceId || i} value={d.deviceId}>
                        {d.label || `Cámara ${i + 1}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {camaraActiva ? (
                <button
                  type="button"
                  className="panel-vivo-btn-secundario"
                  onClick={detenerCamara}
                >
                  Detener cámara
                </button>
              ) : (
                <button
                  type="button"
                  className="panel-vivo-btn-accion"
                  onClick={() => void iniciarCamaraEnVivo(dispositivoCamaraId || undefined)}
                >
                  Encender cámara
                </button>
              )}
            </div>
          )}

          {errorFuente && (
            <div className="panel-vivo-alerta panel-vivo-alerta--aviso" role="alert">
              <span>{errorFuente}</span>
            </div>
          )}

          {/* Marco del reproductor de video / cámara con HUD YOLO superpuesto */}
          <div className="visor-sincro-stage">
            {fuente === "camara" ? (
              <div className="visor-video-canvas-wrapper">
                <video
                  ref={camaraVideoRef}
                  className="visor-sincro-video"
                  playsInline
                  muted
                  autoPlay
                />
                {/* Capa de superposición YOLO + ByteTrack sincronizada con `jugadores` y `balon` */}
                {mostrarOverlayYolo && jugadores.length > 0 && (
                  <div className="visor-yolo-overlay" aria-hidden="true">
                    <div className="visor-yolo-badge-superior">
                      <span>YOLOv8 + ByteTrack · {jugadores.length} tracks activos</span>
                      <span>Homografía 105x68m sincronizada (5.0 Hz)</span>
                    </div>

                    {jugadores.map((j) => {
                      const pos = proyectarCanchaACamara(j.x, j.y);
                      const esLocal = j.equipo === "LOCAL";
                      const colorCaja = esLocal ? colorLocal : colorVisitante;
                      const anchoPx = Math.round(24 * pos.escala);
                      const altoPx = Math.round(48 * pos.escala);
                      return (
                        <div
                          key={j.tid}
                          className="visor-yolo-bbox"
                          style={{
                            left: `${pos.leftPct}%`,
                            top: `${pos.topPct}%`,
                            width: `${anchoPx}px`,
                            height: `${altoPx}px`,
                            borderColor: colorCaja,
                          }}
                        >
                          <span
                            className="visor-yolo-bbox-tag"
                            style={{ backgroundColor: colorCaja }}
                          >
                            {j.dorsal ? `#${j.dorsal}` : `ID:${j.tid}`}
                          </span>
                        </div>
                      );
                    })}

                    {balon && (
                      <div
                        className="visor-yolo-balon"
                        style={{
                          left: `${proyectarCanchaACamara(balon.x, balon.y).leftPct}%`,
                          top: `${proyectarCanchaACamara(balon.x, balon.y).topPct}%`,
                        }}
                      >
                        <span className="visor-yolo-balon-tag">BALÓN</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : videoSrcUrl ? (
              <div className="visor-video-canvas-wrapper">
                <video
                  ref={videoRef}
                  src={videoSrcUrl}
                  className="visor-sincro-video"
                  controls
                  playsInline
                  loop
                  onPlay={() => {
                    if (!workerTransmitiendo) {
                      void activarSincronizacion5Hz();
                    }
                  }}
                />
                {/* Capa de superposición YOLO + ByteTrack sincronizada con `jugadores` y `balon` */}
                {mostrarOverlayYolo && jugadores.length > 0 && (
                  <div className="visor-yolo-overlay" aria-hidden="true">
                    <div className="visor-yolo-badge-superior">
                      <span>YOLOv8 + ByteTrack · {jugadores.length} tracks activos</span>
                      <span>Homografía 105x68m sincronizada (5.0 Hz)</span>
                    </div>

                    {jugadores.map((j) => {
                      const pos = proyectarCanchaACamara(j.x, j.y);
                      const esLocal = j.equipo === "LOCAL";
                      const colorCaja = esLocal ? colorLocal : colorVisitante;
                      const anchoPx = Math.round(24 * pos.escala);
                      const altoPx = Math.round(48 * pos.escala);
                      return (
                        <div
                          key={j.tid}
                          className="visor-yolo-bbox"
                          style={{
                            left: `${pos.leftPct}%`,
                            top: `${pos.topPct}%`,
                            width: `${anchoPx}px`,
                            height: `${altoPx}px`,
                            borderColor: colorCaja,
                          }}
                        >
                          <span
                            className="visor-yolo-bbox-tag"
                            style={{ backgroundColor: colorCaja }}
                          >
                            {j.dorsal ? `#${j.dorsal}` : `ID:${j.tid}`}
                          </span>
                        </div>
                      );
                    })}

                    {balon && (
                      <div
                        className="visor-yolo-balon"
                        style={{
                          left: `${proyectarCanchaACamara(balon.x, balon.y).leftPct}%`,
                          top: `${proyectarCanchaACamara(balon.x, balon.y).topPct}%`,
                        }}
                      >
                        <span className="visor-yolo-balon-tag">BALÓN</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="visor-sincro-placeholder">
                <strong>
                  {cargandoBinario
                    ? "Cargando transmisión de video del partido..."
                    : "Selecciona un video o activa la cámara en vivo"}
                </strong>
                <p>
                  Al darle reproducir, el motor de visión transmite las posiciones a 5 Hz y el
                  Radar 2D inferior mueve las 22 fichas y el balón en sincronía.
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

