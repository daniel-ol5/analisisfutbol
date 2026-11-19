import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { descargarArchivoVideo, listarVideos, obtenerMuestrasVideo, verVideo } from "@/features/vision/api";
import type { Video } from "@/features/vision/types";
import type { MensajeWorker, PosicionDetectada } from "../types";
import { muestraInterpoladaEnTiempo } from "../reproduccion";

export type ModoDisposicionVivo = "apilado" | "paralelo" | "solo-radar";
interface Props {
  partidoId: number; jugadores: PosicionDetectada[]; balon?: PosicionDetectada | null;
  videoInicialId?: number | null;
  colorLocal?: string; colorVisitante?: string; workerTransmitiendo: boolean; modoDisposicion: ModoDisposicionVivo;
  onCambiarModoDisposicion: (modo: ModoDisposicionVivo) => void;
  onMuestraSincronizada: (m: MensajeWorker | null) => void;
  onCambiarFuente: (directo: boolean) => void;
  onElegirVideo?: (video: Video | null) => void;
  muestra?: MensajeWorker | null;
  /** CU-47: pide llevar el video (y con él el plano 2D) a un instante; `n` distingue pedidos repetidos. */
  saltarA?: { t: number; n: number } | null;
}

export function VisorVideoSincronizado({ partidoId, videoInicialId, jugadores, balon, colorLocal, colorVisitante,
  workerTransmitiendo, modoDisposicion, onCambiarModoDisposicion, onMuestraSincronizada, onCambiarFuente, onElegirVideo, muestra, saltarA }: Props) {
  const [fuente, setFuente] = useState("servidor");
  const [videos, setVideos] = useState<Video[]>([]);
  const [videoId, setVideoId] = useState<number | null>(null);
  const [muestras, setMuestras] = useState<MensajeWorker[]>([]);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [errorMuestras, setErrorMuestras] = useState(false);
  const [seguir, setSeguir] = useState(true);
  const [avance, setAvance] = useState<number | null>(null);
  const [reintento, setReintento] = useState(0);
  const [cajas, setCajas] = useState(Boolean(videoInicialId));
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
  const tamano = videoElegido?.tamano_bytes;
  const estadoInicial = useRef<Video | undefined>(undefined);
  estadoInicial.current = videoElegido;
  useEffect(() => {
    onElegirVideo?.(fuente === "servidor" ? videoElegido ?? null : null);
  }, [fuente, onElegirVideo, videoElegido]);
  useEffect(() => {
    limpiar(); setUrl(null); setError(null);
    setAvance(null); setErrorCarga(null);
    if (fuente !== "servidor" || videoId === null || tamano === undefined) return;

    const control = new AbortController();
    const { signal } = control;
    setAvance(0);
    void descargarArchivoVideo({ id: videoId, tamano_bytes: tamano }, signal, (pct) => {
      if (!signal.aborted) setAvance(pct);
    }).then(archivo => {
      if (signal.aborted) return;
      const objeto = URL.createObjectURL(archivo);
      urlRef.current = objeto;
      setUrl(objeto);
    }).catch(() => {
      if (!signal.aborted) setErrorCarga("No se pudo cargar la grabación.");
    }).finally(() => {
      if (!signal.aborted) setAvance(null);
    });
    return () => control.abort();
  }, [fuente, videoId, tamano, limpiar, reintento]);
  useEffect(() => {
    setMuestras([]); setErrorMuestras(false); setSeguir(true); onMuestraSincronizada(null);
    if (fuente !== "servidor" || videoId === null) return;

    const control = new AbortController();
    const { signal } = control;
    let estado = estadoInicial.current?.estado;
    let inicio = estadoInicial.current?.iniciado_en;
    let ultimoT: number | undefined;
    let timer: number | undefined;
    const consultar = async () => {
      try {
        if (estado === "PROCESANDO") {
          const actual = await verVideo(videoId, signal);
          if (signal.aborted) return;
          if (inicio !== actual.iniciado_en) {
            inicio = actual.iniciado_en;
            ultimoT = undefined;
            setMuestras([]);
            onMuestraSincronizada(null);
          }
          estado = actual.estado;
          setVideos(lista => lista.map(v => v.id === videoId ? actual : v));
        }
        const lote = await obtenerMuestrasVideo(videoId, signal, ultimoT);
        if (signal.aborted) return;
        const nuevas = lote.filter(m => ultimoT === undefined || m.t > ultimoT).sort((a, b) => a.t - b.t);
        if (nuevas.length) {
          ultimoT = nuevas[nuevas.length - 1].t;
          setMuestras(previas => [...previas, ...nuevas]);
        }
        setErrorMuestras(false);
      } catch {
        if (!signal.aborted) setErrorMuestras(true);
      } finally {
        if (!signal.aborted && estado === "PROCESANDO") timer = window.setTimeout(consultar, 1500);
      }
    };
    void consultar();
    return () => { control.abort(); window.clearTimeout(timer); };
  }, [fuente, videoId, onMuestraSincronizada, reintento]);
  const enCurso = videoElegido?.estado === "PROCESANDO";
  const siguiendo = fuente === "servidor" && enCurso && seguir;
  const ultimoTiempo = muestras.at(-1)?.t;
  const sincronizar = useCallback(() => {
    const el = video.current;
    if (fuente !== "servidor" || !el) return;
    if (siguiendo && ultimoTiempo === undefined) el.pause();
    if (siguiendo && ultimoTiempo !== undefined && el.currentTime > ultimoTiempo) {
      el.pause();
      el.currentTime = ultimoTiempo;
    }
    onMuestraSincronizada(muestraInterpoladaEnTiempo(muestras, el.currentTime));
  }, [fuente, muestras, onMuestraSincronizada, siguiendo, ultimoTiempo]);
  const reproducirAvance = useCallback(() => {
    const el = video.current;
    if (!siguiendo || !el || el.readyState < 2 || ultimoTiempo === undefined) return;
    sincronizar();
    if (el.paused && ultimoTiempo - el.currentTime > 0.25) void el.play().catch(() => {});
  }, [siguiendo, sincronizar, ultimoTiempo]);
  useEffect(() => { reproducirAvance(); }, [reproducirAvance]);
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
    setSeguir(false);
    el.currentTime = Math.min(Math.max(0, saltarA.t), Number.isFinite(el.duration) ? el.duration : saltarA.t);
    sincronizar();
  }, [saltarA, fuente, muestras, sincronizar]);
  useEffect(() => {
    if (!muestras.length || fuente !== "servidor") return;
    let rafId = 0;
    let activo = true;
    const paso = () => {
      if (!activo) return;
      if (!video.current?.paused) sincronizar();
      rafId = window.requestAnimationFrame(paso);
    };
    rafId = window.requestAnimationFrame(paso);
    return () => {
      activo = false;
      window.cancelAnimationFrame(rafId);
    };
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
  const sinReferencia = muestra?.calidad.calibracion_valida === false;
  const posiciones = new Map((sinReferencia ? [] : jugadores).map(p => [p.tid, p]));
  const personas = detecciones.filter(p => p.clase !== "BALON" && posiciones.has(p.tid));
  const posicionesSinCaja = [...posiciones.values()].filter(p => !personas.some(d => d.tid === p.tid));
  const puntosDibujados = balon && !sinReferencia ? [...posicionesSinCaja, balon] : posicionesSinCaja;
  const colorEquipo = (equipo?: PosicionDetectada["equipo"], clase?: string) => {
    if (clase === "ARBITRO" || equipo === "ARBITRO") return "#facc15";
    if (clase === "PORTERO") {
      if (equipo === "LOCAL") return "#06b6d4";
      if (equipo === "VISITANTE") return "#ec4899";
      return "#a855f7";
    }
    if (equipo === "LOCAL") return colorLocal || "#1d4ed8";
    if (equipo === "VISITANTE") return colorVisitante || "#dc2626";
    return "#94a3b8";
  };
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
    {fuente === "servidor" && enCurso && <div className="analisis-video-pie">
      <label><input type="checkbox" checked={seguir} onChange={e => {
        setSeguir(e.target.checked);
        if (!e.target.checked) video.current?.pause();
      }} /> Seguir procesamiento</label>
      <span role="status">{ultimoTiempo === undefined
        ? videoElegido?.iniciado_en ? "Esperando las primeras detecciones" : "Esperando al worker"
        : `Analizado hasta ${Math.floor(ultimoTiempo / 60)}:${String(Math.floor(ultimoTiempo % 60)).padStart(2, "0")} · ${videoElegido?.progreso_pct ?? 0} %`}</span>
    </div>}
    {fuente === "archivo" && <label className="analisis-video-selector">Archivo local <input type="file" accept="video/*" onChange={e => {
      const archivo = e.target.files?.[0]; if (!archivo) return;
      limpiar(); const objeto = URL.createObjectURL(archivo); urlRef.current = objeto; setUrl(objeto);
    }} /></label>}
    <div className="analisis-video-lienzo" style={{ aspectRatio: aspecto, display: modoDisposicion === "solo-radar" ? "none" : undefined }}>
      <video key={fuente} ref={video} src={url ?? undefined} controls={fuente !== "directo"} playsInline muted={fuente === "directo" || siguiendo}
        onLoadedMetadata={() => { const el = video.current; if (el?.videoHeight) setAspecto(el.videoWidth / el.videoHeight); }}
        onLoadedData={() => { sincronizar(); reproducirAvance(); }} onPlay={sincronizar} onTimeUpdate={sincronizar} onSeeked={sincronizar}
        onError={() => { if (url && fuente === "servidor") setErrorCarga("El navegador no pudo reproducir esta grabación."); }} />
      {!url && !errorCarga && fuente !== "directo" && <p className="analisis-video-vacio">
        {avance !== null ? `Cargando video… ${avance} %` : "Selecciona un video para comenzar"}
      </p>}
      {lineas && fuente === "servidor" && <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Líneas de cancha estimadas" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
        {muestra?.calidad.lineas_imagen?.map((p, i) => <polyline key={i} points={p.map(x => x.join(",")).join(" ")} fill="none" stroke="#5fffe1" strokeWidth={.25} />)}
      </svg>}
      {cajas && fuente === "servidor" && personas.map((p, i) => {
        const pos = posiciones.get(p.tid);
        const equipo = p.clase === "ARBITRO" ? "ARBITRO" : pos?.equipo;
        const esPortero = p.clase === "PORTERO";
        const esArbitro = equipo === "ARBITRO";
        const rol = esPortero ? "Arquero" : esArbitro ? "Árbitro" : (equipo === "LOCAL" || equipo === "VISITANTE" ? "Jugador" : "Persona");
        const color = colorEquipo(equipo, p.clase);
        const etiqueta = esArbitro ? `Árbitro ${p.tid}` : esPortero ? `Arquero ${p.tid}` : `${pos?.dorsal ?? p.tid}`;
        return <div key={`raw-${i}`} className={`analisis-caja${esPortero ? " analisis-caja--portero" : esArbitro ? " analisis-caja--arbitro" : ""}`} style={{
          borderStyle: esPortero ? "dashed" : "solid",
          left: `${p.bbox[0]}%`, top: `${p.bbox[1]}%`, width: `${p.bbox[2] - p.bbox[0]}%`, height: `${p.bbox[3] - p.bbox[1]}%`,
          borderColor: color,
        }} title={`${rol} ${p.tid}`}><span style={{ borderLeft: `3px solid ${color}` }}>{etiqueta}</span></div>;
      })}
      {cajas && fuente === "servidor" && puntosDibujados.map(p => p.bbox && <div key={p === balon ? "balon" : p.tid} className={`analisis-caja${p === balon ? " analisis-caja--balon" : ""}`} style={{
        left: `${p.bbox[0]}%`, top: `${p.bbox[1]}%`, width: `${p.bbox[2] - p.bbox[0]}%`, height: `${p.bbox[3] - p.bbox[1]}%`,
        borderColor: p === balon ? "#ff6b00" : colorEquipo(p.equipo),
      }}><span style={{ borderLeft: `3px solid ${p === balon ? "#ff6b00" : colorEquipo(p.equipo)}` }}>{p === balon ? "Balón" : p.dorsal ?? p.tid}</span></div>)}
    </div>
    {cajas && fuente === "servidor" && !sinReferencia && <div className="analisis-leyenda-cajas" aria-label="Leyenda de cajas">
      <span><i style={{ background: colorLocal || "#1d4ed8" }} />Local</span>
      <span><i style={{ background: colorVisitante || "#dc2626" }} />Visitante</span>
      <span><i className="punteado" style={{ borderColor: "#06b6d4" }} />Arquero</span>
      <span><i style={{ background: "#facc15" }} />Árbitro</span>
      <span><i style={{ background: "#ff6b00" }} />Pelota</span>
    </div>}
    <div className="analisis-video-pie">
      {fuente === "servidor" && <><label><input type="checkbox" checked={cajas} onChange={e => setCajas(e.target.checked)} /> Mostrar detecciones</label>
        <label><input type="checkbox" checked={lineas} onChange={e => setLineas(e.target.checked)} /> Verificar líneas de cancha</label>
        {sinReferencia && <span>Referencia de cancha perdida. Buscando marcas de referencia.</span>}
        {!enCurso && !sinReferencia && avance === null && !errorCarga && !errorMuestras && <span>{muestras.length ? "Resultados sincronizados con el video" : "Procesa el video para ver posiciones"}</span>}</>}
      {fuente === "archivo" && <p>Vista previa del archivo. Súbelo y procésalo para obtener posiciones y métricas.</p>}
      {fuente === "directo" && <><button onClick={() => void abrirCamara()}>Vista previa de cámara</button>
        <p>{workerTransmitiendo ? "Recibiendo posiciones del worker" : "Esperando al worker de visión"}. La vista previa local no envía video al servidor.</p></>}
    </div>
    {errorCarga && <div className="analisis-video-pie">
      <p role="alert">{errorCarga}</p>
      <button onClick={() => setReintento(n => n + 1)}>Reintentar carga</button>
    </div>}
    {errorMuestras && !errorCarga && <div className="analisis-video-pie">
      <p role="alert">No se pudieron actualizar las detecciones.</p>
      {!enCurso && <button onClick={() => setReintento(n => n + 1)}>Reintentar carga</button>}
    </div>}
    {fuente === "servidor" && videoElegido?.estado === "ERROR" && <div className="analisis-video-pie">
      <p role="alert">{muestras.length
        ? "Se interrumpió el procesamiento. El tramo analizado sigue disponible."
        : "El procesamiento del video se interrumpió."}</p>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
