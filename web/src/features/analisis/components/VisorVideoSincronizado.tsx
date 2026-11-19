import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { descargarArchivoVideo, listarVideos, obtenerMuestrasVideo } from "@/features/vision/api";
import type { Video } from "@/features/vision/types";
import type { MensajeWorker, PosicionDetectada } from "../types";
import { muestraEnTiempo } from "../reproduccion";

export type ModoDisposicionVivo = "apilado" | "paralelo" | "solo-radar";
interface Props {
  partidoId: number; jugadores: PosicionDetectada[]; balon?: PosicionDetectada | null;
  videoInicialId?: number | null;
  colorLocal?: string; colorVisitante?: string; workerTransmitiendo: boolean; modoDisposicion: ModoDisposicionVivo;
  onCambiarModoDisposicion: (modo: ModoDisposicionVivo) => void;
  onMuestraSincronizada: (m: MensajeWorker | null) => void;
  onCambiarFuente: (directo: boolean) => void;
  muestra?: MensajeWorker | null;
  /** CU-47: pide llevar el video (y con él el plano 2D) a un instante; `n` distingue pedidos repetidos. */
  saltarA?: { t: number; n: number } | null;
}

export function VisorVideoSincronizado({ partidoId, videoInicialId, jugadores, balon, colorLocal, colorVisitante,
  workerTransmitiendo, modoDisposicion, onCambiarModoDisposicion, onMuestraSincronizada, onCambiarFuente, muestra, saltarA }: Props) {
  const [fuente, setFuente] = useState("servidor");
  const [videos, setVideos] = useState<Video[]>([]);
  const [videoId, setVideoId] = useState<number | null>(null);
  const [muestras, setMuestras] = useState<MensajeWorker[]>([]);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [avance, setAvance] = useState<number | null>(null);
  const [reintento, setReintento] = useState(0);
  const [cajas, setCajas] = useState(false);
  const [lineas, setLineas] = useState(false);
  const [aspecto, setAspecto] = useState(16 / 9);
  const video = useRef<HTMLVideoElement>(null);
  const urlRef = useRef<string | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const limpiar = useCallback(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    stream.current?.getTracks().forEach(t => t.stop()); stream.current = null;
  }, []);
  useEffect(() => () => limpiar(), [limpiar]);
  useEffect(() => {
    let vigente = true;
    listarVideos(partidoId).then(lista => {
      if (!vigente) return;
      const disponibles = lista.filter(v => v.estado !== "CARGANDO" && v.duracion_s !== null);
      const inicial = disponibles.find(v => v.id === videoInicialId) ?? disponibles[0];
      setVideos(disponibles); setVideoId(inicial?.id ?? null);
    }).catch(() => { if (vigente) setError("No se pudo consultar la lista de videos."); });
    return () => { vigente = false; };
  }, [partidoId, videoInicialId]);
  const videoElegido = videos.find(v => v.id === videoId);
  useEffect(() => {
    limpiar(); setUrl(null); setMuestras([]); onMuestraSincronizada(null); setError(null);
    setAvance(null); setErrorCarga(null);
    if (fuente !== "servidor" || !videoElegido) return;

    const control = new AbortController();
    const { signal } = control;
    setAvance(0);
    void Promise.allSettled([
      descargarArchivoVideo(videoElegido, signal, (pct) => {
        if (!signal.aborted) setAvance(pct);
      }),
      obtenerMuestrasVideo(videoElegido.id, signal),
    ]).then(([archivo, resultados]) => {
      if (signal.aborted) return;
      setAvance(null);
      if (archivo.status === "fulfilled") {
        const objeto = URL.createObjectURL(archivo.value);
        urlRef.current = objeto;
        setUrl(objeto);
      } else {
        setErrorCarga("No se pudo cargar la grabación.");
      }
      if (resultados.status === "fulfilled") {
        setMuestras([...resultados.value].sort((a, b) => a.t - b.t));
      } else if (archivo.status === "fulfilled") {
        setErrorCarga("La grabación está disponible. No se pudieron cargar las detecciones.");
      }
    });
    return () => control.abort();
  }, [fuente, videoElegido, limpiar, onMuestraSincronizada, reintento]);
  const sincronizar = useCallback(() => {
    if (fuente === "servidor") onMuestraSincronizada(muestraEnTiempo(muestras, video.current?.currentTime ?? 0));
  }, [fuente, muestras, onMuestraSincronizada]);
  const ultimoSalto = useRef(0);
  useEffect(() => {
    if (!saltarA || saltarA.n === ultimoSalto.current) return;
    const el = video.current;
    if (fuente !== "servidor" || !el || !muestras.length) {
      ultimoSalto.current = saltarA.n;
      setError("Elige «Grabación» y un video procesado para saltar a ese instante.");
      return;
    }
    ultimoSalto.current = saltarA.n;
    setError(null);
    el.currentTime = Math.min(Math.max(0, saltarA.t), Number.isFinite(el.duration) ? el.duration : saltarA.t);
    sincronizar();
  }, [saltarA, fuente, muestras, sincronizar]);
  useEffect(() => {
    if (!muestras.length || fuente !== "servidor") return;
    const timer = window.setInterval(() => { if (!video.current?.paused) sincronizar(); }, 100);
    return () => window.clearInterval(timer);
  }, [muestras, fuente, sincronizar]);
  const seleccionarFuente = (nueva: string) => {
    if (nueva === fuente) return;
    limpiar(); setUrl(null); setMuestras([]); setError(null); setAvance(null); setErrorCarga(null);
    onMuestraSincronizada(null); onCambiarFuente(nueva === "directo"); setFuente(nueva);
  };
  const abrirCamara = async () => {
    try {
      limpiar();
      const media = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      stream.current = media;
      if (video.current) { video.current.srcObject = media; await video.current.play(); }
    } catch { setError("No se pudo abrir la vista previa de la cámara."); }
  };
  const detecciones = muestra?.detecciones ?? [];
  const jugadoresProyectados = detecciones.length ? [] : jugadores;
  const balonDeSeguimiento = balon && !detecciones.some(p => p.clase === "BALON") ? [balon] : [];
  return <section className="analisis-video" aria-label="Video del partido">
    <div className="analisis-video-barra">
      <div role="group" aria-label="Fuente">
        {[["servidor", "Grabación"], ["directo", "Directo"], ["archivo", "Vista previa"]].map(([valor, nombre]) =>
          <button key={valor} className={fuente === valor ? "activo" : ""} onClick={() => seleccionarFuente(valor)}>{nombre}</button>)}
      </div>
      <select aria-label="Distribución" value={modoDisposicion} onChange={e => onCambiarModoDisposicion(e.target.value as ModoDisposicionVivo)}>
        <option value="paralelo">Lado a lado</option><option value="apilado">Apilado</option><option value="solo-radar">Solo plano</option>
      </select>
    </div>
    {fuente === "servidor" && <div className="analisis-video-selector">
      <select aria-label="Seleccionar video" value={videoId ?? ""} onChange={e => setVideoId(Number(e.target.value))}>
        {!videos.length && <option value="">Sin videos subidos</option>}
        {videos.map(v => <option key={v.id} value={v.id}>{v.nombre} · {v.estado}</option>)}
      </select><Link to="/vision/videos">Subir o procesar</Link>
    </div>}
    {fuente === "archivo" && <label className="analisis-video-selector">Archivo local <input type="file" accept="video/*" onChange={e => {
      const archivo = e.target.files?.[0]; if (!archivo) return;
      limpiar(); const objeto = URL.createObjectURL(archivo); urlRef.current = objeto; setUrl(objeto);
    }} /></label>}
    <div className="analisis-video-lienzo" style={{ aspectRatio: aspecto, display: modoDisposicion === "solo-radar" ? "none" : undefined }}>
      <video key={fuente} ref={video} src={url ?? undefined} controls={fuente !== "directo"} playsInline muted={fuente === "directo"}
        onLoadedMetadata={() => { const el = video.current; if (el?.videoHeight) setAspecto(el.videoWidth / el.videoHeight); }}
        onLoadedData={sincronizar} onTimeUpdate={sincronizar} onSeeked={sincronizar}
        onError={() => { if (url && fuente === "servidor") setErrorCarga("El navegador no pudo reproducir esta grabación."); }} />
      {!url && !errorCarga && fuente !== "directo" && <p className="analisis-video-vacio">
        {avance !== null ? `Cargando video… ${avance} %` : "Selecciona un video para comenzar"}
      </p>}
      {lineas && fuente === "servidor" && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Líneas de cancha estimadas" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
        {muestra?.calidad.lineas_imagen?.map((p, i) => <polyline key={i} points={p.map(x => x.join(",")).join(" ")} fill="none" stroke="#5fffe1" strokeWidth={.25} />)}
      </svg>}
      {cajas && fuente === "servidor" && detecciones.map((p, i) => <div key={`raw-${i}`} className="analisis-caja" style={{
        left: `${p.bbox[0]}%`, top: `${p.bbox[1]}%`, width: `${p.bbox[2] - p.bbox[0]}%`, height: `${p.bbox[3] - p.bbox[1]}%`, borderColor: p.clase === "BALON" ? "white" : "#f9d65c",
      }}><span>{p.clase === "BALON" ? "Balón" : `${p.clase} ${p.tid}`}</span></div>)}
      {cajas && fuente === "servidor" && [...jugadoresProyectados, ...balonDeSeguimiento].map(p => p.bbox && <div key={p.tid} className="analisis-caja" style={{
        left: `${p.bbox[0]}%`, top: `${p.bbox[1]}%`, width: `${p.bbox[2] - p.bbox[0]}%`, height: `${p.bbox[3] - p.bbox[1]}%`,
        borderColor: p === balon ? "white" : p.equipo === "LOCAL" ? colorLocal : colorVisitante,
      }}><span>{p === balon ? "Balón (seguimiento)" : p.dorsal ?? p.tid}</span></div>)}
    </div>
    <div className="analisis-video-pie">
      {fuente === "servidor" && <><label><input type="checkbox" checked={cajas} onChange={e => setCajas(e.target.checked)} /> Mostrar detecciones</label>
        <label><input type="checkbox" checked={lineas} onChange={e => setLineas(e.target.checked)} /> Verificar líneas de cancha</label>
        {avance === null && !errorCarga && <span>{muestras.length ? "Resultados sincronizados con el video" : "Procesa el video para ver posiciones"}</span>}</>}
      {fuente === "archivo" && <p>Vista previa del archivo. Súbelo y procésalo para obtener posiciones y métricas.</p>}
      {fuente === "directo" && <><button onClick={() => void abrirCamara()}>Vista previa de cámara</button>
        <p>{workerTransmitiendo ? "Recibiendo posiciones del worker" : "Esperando al worker de visión"}. La vista previa local no envía video al servidor.</p></>}
    </div>
    {errorCarga && <div className="analisis-video-pie">
      <p role="alert">{errorCarga}</p>
      <button onClick={() => setReintento(n => n + 1)}>Reintentar carga</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
