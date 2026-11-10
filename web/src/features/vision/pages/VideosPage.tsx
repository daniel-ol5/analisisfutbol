/**
 * Video del partido  —  CU-27, CU-28 (T-062 · HU-24, HU-25).
 *
 * El analista elige un partido, sube su video grabado por trozos (con barra de
 * progreso, pausa y reanudación aunque se recargue la página) y lanza el
 * procesamiento. El avance y el tiempo restante se actualizan solos mientras un
 * worker lo procesa, y se puede cancelar. Si algo falla se muestra la causa.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useSesion } from "@/features/seguridad";
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Select } from "@/shared/ui";
import type { TonoBadge } from "@/shared/ui/Badge";

import {
  cancelarProceso,
  eliminarVideo,
  enviarTrozo,
  iniciarCarga,
  lanzarProceso,
  listarPartidos,
  listarVideos,
  verVideo,
} from "../api";
import type { EstadoVideo, Video } from "../types";
import {
  ACEPTA,
  ETIQUETA_ESTADO,
  ROLES_PROCESAN,
  ROLES_SUBEN,
  SubidaPausada,
  esElMismoArchivo,
  formatearBytes,
  formatearDuracion,
  formatearRestante,
  hayQueSeguirConsultando,
  partidosParaVideo,
  porcentajeSubida,
  problemaDelArchivo,
  sePuedeProcesar,
  subirPorTrozos,
} from "../videos";
import "../videos.css";

const TONO: Record<EstadoVideo, TonoBadge> = {
  CARGANDO: "aviso",
  SUBIDO: "info",
  PROCESANDO: "info",
  PROCESADO: "ok",
  ERROR: "error",
};

const formatoFecha = new Intl.DateTimeFormat("es-BO", {
  weekday: "short",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Una subida en curso en esta pestaña (solo una a la vez). */
interface Subida {
  videoId: number;
  archivo: File;
  bytes: number;
  total: number;
  estado: "subiendo" | "pausada" | "error";
  error?: string;
}

export function VideosPage() {
  const rol = useSesion()?.usuario.rol;
  const puedeSubir = rol !== undefined && ROLES_SUBEN.includes(rol);
  const puedeProcesar = rol !== undefined && ROLES_PROCESAN.includes(rol);
  const cliente = useQueryClient();

  const partidos = useQuery({ queryKey: ["vision", "partidos"], queryFn: listarPartidos });
  const opciones = useMemo(() => partidosParaVideo(partidos.data ?? []), [partidos.data]);
  const [elegido, setElegido] = useState<number | null>(null);
  const partidoId = elegido ?? opciones[0]?.id ?? null;

  const clave = ["vision", "videos", partidoId] as const;
  const videos = useQuery({
    queryKey: clave,
    queryFn: () => listarVideos(partidoId as number),
    enabled: partidoId !== null,
    // HU-25 · Criterio 2: el avance se actualiza solo mientras algo se procesa.
    refetchInterval: (q) => (hayQueSeguirConsultando(q.state.data ?? []) ? 3000 : false),
  });
  const refrescar = () => cliente.invalidateQueries({ queryKey: ["vision", "videos"] });

  // ---------- Subida ----------

  const [subida, setSubida] = useState<Subida | null>(null);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);
  const control = useRef<AbortController | null>(null);
  const selector = useRef<HTMLInputElement>(null);
  const retomando = useRef<Video | null>(null);
  const subiendo = subida?.estado === "subiendo";

  // Cerrar la pestaña corta la subida: se avisa antes.
  useEffect(() => {
    if (!subiendo) return;
    const avisar = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [subiendo]);

  async function subir(archivo: File, video: Video) {
    const abortar = new AbortController();
    control.current = abortar;
    setSubida({
      videoId: video.id,
      archivo,
      bytes: video.bytes_recibidos,
      total: video.tamano_bytes,
      estado: "subiendo",
    });
    try {
      const final = await subirPorTrozos(
        archivo,
        video,
        { enviarTrozo, verVideo },
        {
          signal: abortar.signal,
          onProgreso: (bytes) => setSubida((s) => (s ? { ...s, bytes } : s)),
        },
      );
      setSubida(null);
      if (final.estado === "ERROR") setErrorArchivo(final.mensaje_error);
    } catch (e) {
      setSubida((s) =>
        s && e instanceof SubidaPausada
          ? { ...s, estado: "pausada" }
          : s && { ...s, estado: "error", error: mensajeDeError(e) },
      );
    } finally {
      void refrescar();
    }
  }

  async function alElegirArchivo(archivo: File | undefined) {
    if (selector.current) selector.current.value = "";
    if (!archivo || partidoId === null) return;
    setErrorArchivo(null);
    const pendiente = retomando.current;
    retomando.current = null;

    if (pendiente) {
      if (!esElMismoArchivo(archivo, pendiente)) {
        setErrorArchivo(
          `Para retomar, elige el mismo archivo: «${pendiente.nombre}» de ` +
            `${formatearBytes(pendiente.tamano_bytes)}.`,
        );
        return;
      }
      await subir(archivo, await verVideo(pendiente.id));
      return;
    }

    // HU-24 · Criterio 1: el formato se valida antes de subir nada.
    const problema = problemaDelArchivo(archivo);
    if (problema) {
      setErrorArchivo(problema);
      return;
    }
    try {
      const video = await iniciarCarga(partidoId, {
        nombre: archivo.name,
        tipo: archivo.type,
        tamano_bytes: archivo.size,
      });
      void refrescar();
      await subir(archivo, video);
    } catch (e) {
      setErrorArchivo(mensajeDeError(e));
    }
  }

  function elegirArchivo(paraRetomar: Video | null = null) {
    retomando.current = paraRetomar;
    selector.current?.click();
  }

  // ---------- Procesamiento ----------

  const navegar = useNavigate();
  const procesar = useMutation({
    mutationFn: ({
      id,
      colorPropio,
      colorRival,
    }: {
      id: number;
      colorPropio: string | null;
      colorRival: string | null;
    }) =>
      lanzarProceso(id, { color_propio: colorPropio, color_rival: colorRival }),
    onSettled: refrescar,
  });
  const cancelar = useMutation({ mutationFn: cancelarProceso, onSettled: refrescar });
  const eliminar = useMutation({ mutationFn: eliminarVideo, onSettled: refrescar });

  // ---------- Vista ----------

  const partido = opciones.find((p) => p.id === partidoId) ?? null;

  return (
    <main className="vid-pagina">
      <Link to="/vision" className="volver">
        ← Visión por Computadora
      </Link>
      <span className="kicker">CU-27 · CU-28 · VIDEO DEL PARTIDO</span>
      <h1>Video del partido</h1>
      <p className="vid-intro">
        Sube el video grabado de un partido (MP4, MOV o MKV) y procésalo para obtener las mismas
        métricas que un partido en vivo. La subida se puede pausar y retomar, incluso otro día.
      </p>

      {partidos.isError && (
        <Alert tono="error" titulo="No se pudo cargar la agenda">
          {mensajeDeError(partidos.error)}
        </Alert>
      )}
      {partidos.isSuccess && opciones.length === 0 && (
        <Alert tono="info" titulo="Todavía no hay partidos">
          Programa un partido en Gestión Deportiva para poder subir su video.
        </Alert>
      )}

      {opciones.length > 0 && (
        <div className="vid-barra-superior">
          <Select
            etiqueta="Partido"
            value={partidoId ?? ""}
            disabled={subiendo}
            onChange={(e) => setElegido(Number(e.currentTarget.value))}
          >
            {opciones.map((p) => (
              <option key={p.id} value={p.id}>
                vs {p.rival} · {formatoFecha.format(new Date(p.fecha_hora))}
              </option>
            ))}
          </Select>
          {puedeSubir && (
            <Button onClick={() => elegirArchivo()} disabled={subiendo || partidoId === null}>
              Subir video
            </Button>
          )}
          <input
            ref={selector}
            type="file"
            accept={ACEPTA}
            hidden
            onChange={(e) => void alElegirArchivo(e.currentTarget.files?.[0])}
          />
        </div>
      )}

      {!puedeSubir && rol && (
        <p className="vid-nota">Tu rol puede ver los videos, pero no subirlos ni procesarlos.</p>
      )}
      {errorArchivo && (
        <Alert tono="error" titulo="No se puede subir ese archivo">
          {errorArchivo}
        </Alert>
      )}

      {partido && videos.isError && (
        <Alert tono="error" titulo="No se pudieron cargar los videos">
          {mensajeDeError(videos.error)}
        </Alert>
      )}
      {partido && videos.isSuccess && videos.data.length === 0 && (
        <p className="vid-vacio">Este partido todavía no tiene video.</p>
      )}

      <ul className="vid-lista">
        {(videos.data ?? []).map((v) => (
          <TarjetaVideo
            key={v.id}
            video={v}
            subida={subida?.videoId === v.id ? subida : null}
            otraSubidaEnCurso={subiendo && subida?.videoId !== v.id}
            puedeSubir={puedeSubir}
            puedeProcesar={puedeProcesar}
            onPausar={() => control.current?.abort()}
            onReanudar={() =>
              subida && void verVideo(v.id).then((fresco) => subir(subida.archivo, fresco))
            }
            onRetomar={() => elegirArchivo(v)}
            onProcesar={({ colorPropio, colorRival }) =>
              procesar.mutate({ id: v.id, colorPropio, colorRival })
            }
            procesando={procesar.isPending && procesar.variables?.id === v.id}
            errorProcesar={procesar.variables?.id === v.id ? procesar.error : null}
            onCancelar={() => {
              if (window.confirm(`¿Cancelar el procesamiento de «${v.nombre}»?`))
                cancelar.mutate(v.id);
            }}
            cancelando={cancelar.isPending && cancelar.variables === v.id}
            onAnalizar={() => navegar(`/analisis?partidoId=${v.partido_id}&videoId=${v.id}`)}
            onEliminar={() => {
              if (window.confirm(`¿Eliminar definitivamente el video «${v.nombre}»?`))
                eliminar.mutate(v.id);
            }}
            eliminando={eliminar.isPending && eliminar.variables === v.id}
          />
        ))}
      </ul>
    </main>
  );
}

// ---------------- Tarjeta de un video ----------------

interface PropsTarjeta {
  video: Video;
  subida: Subida | null;
  otraSubidaEnCurso: boolean;
  puedeSubir: boolean;
  puedeProcesar: boolean;
  onPausar: () => void;
  onReanudar: () => void;
  onRetomar: () => void;
  onProcesar: (colores: { colorPropio: string | null; colorRival: string | null }) => void;
  procesando: boolean;
  errorProcesar: unknown;
  onCancelar: () => void;
  cancelando: boolean;
  onAnalizar: () => void;
  onEliminar: () => void;
  eliminando: boolean;
}

function TarjetaVideo(p: PropsTarjeta) {
  const v = p.video;
  const legible = v.duracion_s !== null;

  return (
    <li className="vid-tarjeta" aria-label={`Video ${v.nombre}`}>
      <div className="vid-tarjeta-cabecera">
        <div>
          <strong className="vid-nombre">{v.nombre}</strong>
          <span className="vid-detalle">
            {formatearBytes(v.tamano_bytes)} · subido el{" "}
            {formatoFecha.format(new Date(v.creado_en))}
          </span>
        </div>
        <Badge tono={TONO[v.estado]}>{ETIQUETA_ESTADO[v.estado]}</Badge>
      </div>

      {/* HU-24 · Criterio 3: metadatos leídos del archivo */}
      {legible && (
        <dl className="vid-metadatos">
          <div>
            <dt>Duración</dt>
            <dd>{formatearDuracion(v.duracion_s ?? 0)}</dd>
          </div>
          <div>
            <dt>Resolución</dt>
            <dd>{v.resolucion}</dd>
          </div>
          <div>
            <dt>FPS</dt>
            <dd>{v.fps}</dd>
          </div>
        </dl>
      )}

      {v.estado === "CARGANDO" && <EstadoCarga {...p} />}
      {v.estado === "PROCESANDO" && <EstadoProceso {...p} />}

      {v.estado === "ERROR" && v.mensaje_error && (
        <Alert tono="error" titulo={legible ? "El procesamiento falló" : "El archivo no sirve"}>
          {v.mensaje_error}
        </Alert>
      )}
      {v.estado === "PROCESADO" && v.procesado_en && (
        <p className="vid-ok">
          Procesado el {formatoFecha.format(new Date(v.procesado_en))}: las métricas del partido ya
          están disponibles.
        </p>
      )}

      {p.puedeProcesar && sePuedeProcesar(v) && <FormularioProceso {...p} />}

      <div
        className="vid-estado-fila"
        style={{
          marginTop: "0.75rem",
          paddingTop: "0.65rem",
          borderTop: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
          justifyContent: "flex-end",
          gap: "0.6rem",
          flexWrap: "wrap",
        }}
      >
        {legible && (
          <Button variante="secundario" onClick={p.onAnalizar}>
            Analizar en panel en vivo
          </Button>
        )}
        {p.puedeSubir && (
          <Button variante="peligro" onClick={p.onEliminar} disabled={p.eliminando}>
            {p.eliminando ? "Eliminando…" : "Eliminar video"}
          </Button>
        )}
      </div>
    </li>
  );
}

function BarraProgreso({ pct, etiqueta }: { pct: number | null; etiqueta: string }) {
  return (
    <div
      className={pct === null ? "vid-progreso vid-progreso--indeterminado" : "vid-progreso"}
      role="progressbar"
      aria-label={etiqueta}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct ?? undefined}
    >
      <span style={{ width: pct === null ? undefined : `${pct}%` }} />
    </div>
  );
}

/** HU-24 · Criterio 1: barra de progreso de la subida, con pausa y reanudación. */
function EstadoCarga({
  video: v,
  subida,
  otraSubidaEnCurso,
  puedeSubir,
  onPausar,
  onReanudar,
  onRetomar,
}: PropsTarjeta) {
  const bytes = subida?.bytes ?? v.bytes_recibidos;
  const pct = porcentajeSubida(bytes, v.tamano_bytes);
  return (
    <div className="vid-estado">
      <BarraProgreso pct={pct} etiqueta={`Subida de ${v.nombre}`} />
      <div className="vid-estado-fila">
        <span>
          <strong>{pct}%</strong> · {formatearBytes(bytes)} de {formatearBytes(v.tamano_bytes)}
          {subida?.estado === "subiendo" && " · no cierres esta pestaña"}
        </span>
        {puedeSubir && subida?.estado === "subiendo" && (
          <Button variante="secundario" onClick={onPausar}>
            Pausar
          </Button>
        )}
        {puedeSubir && subida && subida.estado !== "subiendo" && (
          <Button onClick={onReanudar}>Reanudar</Button>
        )}
        {puedeSubir && !subida && (
          <Button variante="secundario" onClick={onRetomar} disabled={otraSubidaEnCurso}>
            Retomar subida
          </Button>
        )}
      </div>
      {!subida && (
        <p className="vid-nota">
          La subida quedó a medias. Para retomarla, vuelve a elegir el mismo archivo: sigue desde
          donde quedó.
        </p>
      )}
      {subida?.estado === "error" && (
        <Alert tono="error" titulo="La subida se detuvo">
          {subida.error} Revisa la conexión y pulsa Reanudar: no se pierde lo ya subido.
        </Alert>
      )}
    </div>
  );
}

/** HU-25 · Criterios 2 y 3: avance, tiempo restante y cancelación. */
function EstadoProceso({ video: v, puedeProcesar, onCancelar, cancelando }: PropsTarjeta) {
  const enCola = v.iniciado_en === null;
  const restante = formatearRestante(v.tiempo_restante_s);
  return (
    <div className="vid-estado">
      <BarraProgreso
        pct={enCola ? null : v.progreso_pct}
        etiqueta={`Procesamiento de ${v.nombre}`}
      />
      <div className="vid-estado-fila">
        <span aria-live="polite">
          {enCola ? (
            "En cola: iniciando análisis de visión con IA…"
          ) : (
            <>
              <strong>{v.progreso_pct}%</strong>
              {restante ? ` · faltan ${restante}` : " · calculando el tiempo restante…"}
            </>
          )}
        </span>
        {puedeProcesar && (
          <Button variante="peligro" onClick={onCancelar} disabled={cancelando}>
            {cancelando ? "Cancelando…" : "Cancelar procesamiento"}
          </Button>
        )}
      </div>
    </div>
  );
}

function FormularioProceso({ video: v, onProcesar, procesando, errorProcesar }: PropsTarjeta) {
  const [personalizarPropio, setPersonalizarPropio] = useState<boolean>(Boolean(v.color_propio));
  const [colorPropio, setColorPropio] = useState<string>(v.color_propio || "#6CABDD");
  const [conColorRival, setConColorRival] = useState<boolean>(v.color_rival ? true : true);
  const [colorRival, setColorRival] = useState<string>(v.color_rival || "#FFFFFF");
  const sinCalibrar =
    estadoHttp(errorProcesar) === 409 && /calibra/i.test(mensajeDeError(errorProcesar));

  const presetsPropio = [
    { nombre: "Celeste (MCI)", hex: "#6CABDD" },
    { nombre: "Verde (Betis)", hex: "#008855" },
    { nombre: "Azul", hex: "#1E5AA8" },
    { nombre: "Blanco", hex: "#FFFFFF" },
    { nombre: "Rojo", hex: "#C8102E" },
  ];

  const presetsRival = [
    { nombre: "Blanco (TOT)", hex: "#FFFFFF" },
    { nombre: "Rojo", hex: "#C8102E" },
    { nombre: "Celeste", hex: "#6CABDD" },
    { nombre: "Negro", hex: "#1E1E1E" },
    { nombre: "Amarillo", hex: "#FACC15" },
  ];

  return (
    <div className="vid-procesar">
      <div className="vid-colores-seccion">
        {/* Color de nuestro equipo */}
        <div className="vid-color-bloque">
          <label className="vid-check">
            <input
              type="checkbox"
              checked={personalizarPropio}
              onChange={(e) => setPersonalizarPropio(e.target.checked)}
            />
            <strong>Color de nuestro equipo (Local):</strong>
          </label>
          {personalizarPropio ? (
            <div className="vid-color-fila">
              <label className="vid-color">
                <input
                  type="color"
                  value={colorPropio}
                  onChange={(e) => setColorPropio(e.target.value)}
                />
                <span>{colorPropio.toUpperCase()}</span>
              </label>
              <div className="vid-presets">
                {presetsPropio.map((p) => (
                  <button
                    key={p.hex}
                    type="button"
                    className="vid-btn-preset"
                    style={{ borderLeftColor: p.hex }}
                    onClick={() => setColorPropio(p.hex)}
                  >
                    {p.nombre}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="vid-nota">
              Usa por defecto la indumentaria registrada del club para el partido.
            </p>
          )}
        </div>

        {/* Color del equipo rival */}
        <div className="vid-color-bloque">
          <label className="vid-check">
            <input
              type="checkbox"
              checked={conColorRival}
              onChange={(e) => setConColorRival(e.target.checked)}
            />
            <strong>Color del equipo rival (Visitante):</strong>
          </label>
          {conColorRival ? (
            <div className="vid-color-fila">
              <label className="vid-color">
                <input
                  type="color"
                  value={colorRival}
                  onChange={(e) => setColorRival(e.target.value)}
                />
                <span>{colorRival.toUpperCase()}</span>
              </label>
              <div className="vid-presets">
                {presetsRival.map((p) => (
                  <button
                    key={p.hex}
                    type="button"
                    className="vid-btn-preset"
                    style={{ borderLeftColor: p.hex }}
                    onClick={() => setColorRival(p.hex)}
                  >
                    {p.nombre}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="vid-nota">
              Sin el color del rival, los equipos se separan automáticamente por K-means.
            </p>
          )}
        </div>
      </div>

      <Button
        onClick={() =>
          onProcesar({
            colorPropio: personalizarPropio ? colorPropio.toUpperCase() : null,
            colorRival: conColorRival ? colorRival.toUpperCase() : null,
          })
        }
        disabled={procesando}
      >
        {procesando ? "Enviando…" : v.estado === "SUBIDO" ? "Procesar video" : "Volver a procesar"}
      </Button>
      {errorProcesar != null && (
        <Alert tono="error" titulo="No se pudo procesar">
          {mensajeDeError(errorProcesar)}{" "}
          {sinCalibrar && <Link to="/vision/calibracion">Ir a calibrar la cámara</Link>}
        </Alert>
      )}
    </div>
  );
}
