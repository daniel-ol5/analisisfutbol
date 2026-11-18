import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { mensajeDeError } from "@/shared/lib/errors";
import { guardarCalibracion, listarPartidos, listarVideos, obtenerCuadroCalibracion } from "../api";
import { construirCuerpoCalibracion, construirPlantillaCancha, obtenerRolSesionActual,
  rolPuedeGuardarCalibracion, validarEstadoCalibracion } from "../calibracion";
import { VisorCuadro } from "../components/VisorCuadro";
import { PlanoCancha } from "../components/PlanoCancha";
import { useValidacionCalibracion } from "../useValidacionCalibracion";
import type { CalibracionGuardar, ParCalibracion, Punto, ReferenciaCalibracion } from "../types";
import "../calibracion.css";

export function CalibracionDinamicaPage() {
  const [params] = useSearchParams();
  const [partidoId, setPartidoId] = useState(Number(params.get("partidoId")) || 0);
  const [modo, setModo] = useState<"AUTOMATICA" | "MANUAL">("AUTOMATICA");
  const [tipo, setTipo] = useState<"VIDEO" | "DIRECTO">("VIDEO");
  const [fuenteId, setFuenteId] = useState("camara-principal");
  const [videoId, setVideoId] = useState(0);
  const [tiempo, setTiempo] = useState(0);
  const [largo, setLargo] = useState(105);
  const [ancho, setAncho] = useState(68);
  const [imagen, setImagen] = useState<string | null>(null);
  const [referencia, setReferencia] = useState<ReferenciaCalibracion | null>(null);
  const [pares, setPares] = useState<ParCalibracion[]>([]);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [hitoId, setHitoId] = useState<string | null>(null);
  const [libre, setLibre] = useState(false);
  const [pendiente, setPendiente] = useState<Punto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const solicitud = useRef(0);
  const partidos = useQuery({ queryKey: ["vision", "partidos"], queryFn: listarPartidos });
  const videos = useQuery({ queryKey: ["vision", "videos", partidoId], queryFn: () => listarVideos(partidoId), enabled: partidoId > 0 });
  useEffect(() => { if (!partidoId && partidos.data?.[0]) setPartidoId(partidos.data[0].id); }, [partidos.data, partidoId]);
  const plantilla = useMemo(() => construirPlantillaCancha(largo, ancho), [largo, ancho]);
  const usados = new Set(pares.map(p => p.hitoId));
  const hito = plantilla.find(h => h.id === hitoId && !usados.has(h.id)) ?? plantilla.find(h => !usados.has(h.id)) ?? null;
  const validacion = validarEstadoCalibracion(String(partidoId), largo, ancho, pares);
  const cuerpo: CalibracionGuardar | null = useMemo(() => {
    if (validacion.erroresMedidas.length) return null;
    const ref: ReferenciaCalibracion | null = tipo === "DIRECTO"
      ? (fuenteId.trim() ? { tipo, fuente_id: fuenteId.trim(), tiempo_s: 0 } : null)
      : modo === "AUTOMATICA" && videoId > 0 ? { tipo, video_id: videoId, tiempo_s: 0 } : referencia;
    if (!ref) return null;
    if (modo === "AUTOMATICA") return { modo, referencia: ref, largo_m: largo, ancho_m: ancho, puntos_imagen: [], puntos_cancha: [] };
    if (tipo !== "VIDEO" || !validacion.valido) return null;
    return { ...construirCuerpoCalibracion(pares, largo, ancho), modo, referencia: ref };
  }, [modo, tipo, videoId, fuenteId, referencia, pares, largo, ancho, validacion.valido, validacion.erroresMedidas.length]);
  const comprobar = useValidacionCalibracion(partidoId || null, modo === "MANUAL" ? cuerpo : null);
  const guardar = useMutation({ mutationFn: () => guardarCalibracion(partidoId, cuerpo!), onError: e => setError(mensajeDeError(e)) });

  function limpiar() {
    solicitud.current += 1;
    setCargando(false); setImagen(null); setReferencia(null); setPares([]); setSeleccion(null);
    setError(null); guardar.reset();
  }

  async function cargarCuadro() {
    const idSolicitud = ++solicitud.current;
    setCargando(true); setError(null); guardar.reset();
    try {
      const cuadro = await obtenerCuadroCalibracion(videoId, tiempo);
      if (idSolicitud !== solicitud.current) return;
      setImagen(`data:image/png;base64,${cuadro.imagen_base64}`);
      setReferencia({ tipo: "VIDEO", video_id: videoId, tiempo_s: cuadro.tiempo_s,
        cuadro_indice: cuadro.cuadro_indice, ancho_px: cuadro.ancho_px, alto_px: cuadro.alto_px });
      setPares([]); setSeleccion(null);
    } catch (e) { if (idSolicitud === solicitud.current) setError(mensajeDeError(e)); }
    finally { if (idSolicitud === solicitud.current) setCargando(false); }
  }

  function marcar(px: Punto) {
    if (modo !== "MANUAL" || !referencia) return;
    const destino = libre ? pendiente : hito;
    if (!destino) return;
    guardar.reset();
    const id = crypto.randomUUID();
    setPares(prev => [...prev, { id, hitoId: libre ? null : hito!.id,
      etiqueta: libre ? "Referencia libre" : hito!.nombre, imagen: px, cancha: { x: destino.x, y: destino.y } }]);
    setSeleccion(id); setPendiente(null);
  }

  const dimensiones = referencia?.ancho_px && referencia.alto_px ? { ancho: referencia.ancho_px, alto: referencia.alto_px } : null;
  return <main className="cal-pagina">
    <Link to="/vision" className="volver">← Visión por computadora</Link>
    <h1>Calibración y seguimiento de cancha</h1>
    <p className="cal-intro">Configura la fuente y las medidas del campo. El worker sigue los paneos y vuelve a buscar referencias cuando la cámara cambia.</p>
    <section className="cal-barra-config" aria-label="Fuente y medidas">
      <label className="cal-campo">Partido<select aria-label="Partido" className="cal-input" value={partidoId} onChange={e => { limpiar(); setPartidoId(Number(e.target.value)); setVideoId(0); }}>
        <option value={0}>Seleccionar partido</option>{partidos.data?.map(p => <option key={p.id} value={p.id}>#{p.id} · {p.rival}</option>)}
      </select></label>
      <label className="cal-campo">Fuente<select aria-label="Fuente" className="cal-input" value={tipo} onChange={e => { limpiar(); setTipo(e.target.value as typeof tipo); setModo("AUTOMATICA"); }}>
        <option value="VIDEO">Grabación subida</option><option value="DIRECTO">Cámara en directo</option>
      </select></label>
      <label className="cal-campo">Largo (m)<input className="cal-input" type="number" min={41} max={129} value={largo} onChange={e => { setLargo(Number(e.target.value)); setPares([]); guardar.reset(); }} /></label>
      <label className="cal-campo">Ancho (m)<input className="cal-input" type="number" min={26} max={89} value={ancho} onChange={e => { setAncho(Number(e.target.value)); setPares([]); guardar.reset(); }} /></label>
    </section>
    {tipo === "VIDEO" ? <section className="cal-barra-config">
      <label className="cal-campo">Video<select aria-label="Video" className="cal-input" value={videoId} onChange={e => { limpiar(); setVideoId(Number(e.target.value)); }}>
        <option value={0}>Seleccionar video</option>{videos.data?.filter(v => v.duracion_s !== null).map(v => <option key={v.id} value={v.id}>{v.nombre}</option>)}
      </select></label>
      <Link to={`/vision/videos?partidoId=${partidoId}`}>Subir un video</Link>
      <label className="cal-campo">Segundo de referencia<input className="cal-input" type="number" min={0} step={.1} value={tiempo} onChange={e => setTiempo(Number(e.target.value))} /></label>
      <button className="cal-btn" disabled={!videoId || cargando || !Number.isFinite(tiempo) || tiempo < 0} onClick={() => void cargarCuadro()}>{cargando ? "Extrayendo…" : "Ver cuadro del video"}</button>
    </section> : <section className="cal-panel">
      <label>Nombre de fuente<input className="cal-input" value={fuenteId} maxLength={120} onChange={e => { setFuenteId(e.target.value); guardar.reset(); }} /></label>
      <p>Usa el mismo nombre en el worker con <code>--fuente-id</code>. La referencia se reconoce desde la imagen que recibe el worker.</p>
    </section>}
    <section className="cal-barra-acciones" aria-label="Método de calibración">
      <button className={`cal-btn ${modo === "AUTOMATICA" ? "es-activo" : ""}`} onClick={() => { setModo("AUTOMATICA"); guardar.reset(); }}>Reconocimiento automático</button>
      {tipo === "VIDEO" && <button className={`cal-btn ${modo === "MANUAL" ? "es-activo" : ""}`} onClick={() => { setModo("MANUAL"); guardar.reset(); }}>Referencia manual de respaldo</button>}
    </section>
    {modo === "AUTOMATICA" && <section className="cal-panel">
      <h2>Cancha que sigue a la cámara</h2>
      <p>El modelo reconoce marcas del terreno y el seguimiento actualiza el plano entre cuadros. Cuando pierde la referencia, suspende las posiciones en metros y busca recuperarla.</p>
      <p>Guardar prepara la configuración. La calidad real se verifica al procesar: el panel mostrará si la cancha está verificada, en seguimiento o sin referencia.</p>
      <p>El worker necesita el modelo de cancha instalado. Las zonas fuera de cámara se consideran no observadas.</p>
    </section>}
    {referencia && <p>Cuadro #{referencia.cuadro_indice} · {referencia.tiempo_s.toFixed(3)} s · {referencia.ancho_px} × {referencia.alto_px} px</p>}
    {modo === "MANUAL" && <>
      <p>Marca ocho referencias reales repartidas en el suelo. Puedes seleccionar cruces del círculo central y del área chica; omite los puntos que no se vean.</p>
      <section className="cal-barra-acciones">
        <strong>{pares.length} / 8 referencias</strong>
        <button className="cal-btn" onClick={() => setLibre(!libre)}>{libre ? "Volver a plantilla" : "Punto libre"}</button>
        <button className="cal-btn" onClick={() => { setPares(prev => prev.slice(0, -1)); guardar.reset(); }}>Deshacer último punto</button>
        <button className="cal-btn" onClick={() => { setPares([]); guardar.reset(); }}>Borrar puntos</button>
      </section>
    </>}
    {imagen && <section className="cal-grilla-paneles">
      <VisorCuadro imagenUrl={imagen} nombreArchivo="Referencia del video" dimensiones={dimensiones} pares={pares} parSeleccionadoId={seleccion}
        etiquetaDestinoActual={modo === "AUTOMATICA" ? "Vista del encuadre seleccionado" : libre ? "Elige primero el punto del plano" : hito?.nombre ?? "Referencias completas"}
        onCargarDimensiones={() => {}} onClicNuevoPunto={marcar} onSeleccionarPar={setSeleccion} onInicioArrastreMarcador={() => guardar.reset()}
        onMoverMarcador={(id, punto) => { setPares(prev => prev.map(p => p.id === id ? { ...p, imagen: punto } : p)); guardar.reset(); }} />
      {modo === "MANUAL" && <PlanoCancha largoM={largo} anchoM={ancho} plantilla={plantilla} hitoActivoId={hito?.id ?? null}
        modoLibre={libre} puntoLibrePendiente={pendiente} pares={pares} parSeleccionadoId={seleccion}
        onSeleccionarHito={id => { setHitoId(id); setLibre(false); }} onSeleccionarPar={setSeleccion} onElegirPuntoLibre={setPendiente} />}
    </section>}
    {modo === "MANUAL" && <section className="cal-panel" aria-label="Validación de referencia manual">
      <h2>Comprobar referencia</h2>
      <p>{comprobar.resultado?.mensaje ?? (validacion.erroresPuntos.join(" · ") || "Marca las referencias del cuadro seleccionado.")}</p>
      {comprobar.resultado && <p>Error medio: {comprobar.resultado.error_medio_m.toFixed(2)} m · Máximo: {comprobar.resultado.error_max_m.toFixed(2)} m</p>}
      {Boolean(comprobar.error) && <p role="alert">{mensajeDeError(comprobar.error)}</p>}
      <button className="cal-btn" disabled={!cuerpo} onClick={() => comprobar.validarAhora()}>Validar ahora</button>
      <p className="cal-texto-suave">Este error mide el ajuste sobre tus marcas. Comprueba también otras líneas y los movimientos de cámara durante el análisis.</p>
    </section>}
    {error && <p className="cal-alerta cal-alerta-error" role="alert">{error}</p>}
    {validacion.erroresMedidas.map(e => <p key={e} role="alert">{e}</p>)}
    <button className="cal-btn-primario" disabled={!cuerpo || guardar.isPending || !rolPuedeGuardarCalibracion(obtenerRolSesionActual())}
      onClick={() => { setError(null); guardar.mutate(); }}>{guardar.isPending ? "Guardando…" : "Guardar configuración"}</button>
    {guardar.data && <div className="cal-alerta cal-alerta-exito" role="status">
      <p>{guardar.data.modo === "AUTOMATICA" ? "Configuración automática guardada. El worker verificará la cancha durante el análisis." : guardar.data.valida ? "Referencia manual guardada y válida." : "Referencia guardada con errores: corrige los puntos antes de procesar."}</p>
      <Link to={`/vision/videos?partidoId=${partidoId}`}>Continuar con el video</Link>{" · "}<Link to={`/analisis?partidoId=${partidoId}`}>Abrir análisis</Link>
      <p><a download={`calibracion-partido-${partidoId}.json`} href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(guardar.data, null, 2))}`}>Descargar configuración para Colab</a></p>
    </div>}
    {(partidos.isError || videos.isError) && <p role="alert">No se pudieron cargar los datos del club. Comprueba la conexión con la API.</p>}
  </main>;
}
