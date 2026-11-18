import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listarEquipos, listarPartidos } from "@/features/deportivo/api";
import { api } from "@/shared/api/client";
import { usePartidoEnVivo } from "../hooks/usePartidoEnVivo";
import type { ConfiguracionPlano2D, MensajeWorker } from "../types";
import { Plano2DCancha } from "./Plano2DCancha";
import { VisorVideoSincronizado, type ModoDisposicionVivo } from "./VisorVideoSincronizado";

export function PanelPartidoVivo({ partidoIdInicial }: { partidoIdInicial?: number }) {
  const equipos = useQuery({ queryKey: ["equipos"], queryFn: () => listarEquipos() });
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const [seleccionado, setSeleccionado] = useState<number | null>(partidoIdInicial ?? null);
  const id = seleccionado ?? partidos.data?.[0]?.id ?? null;
  const partido = partidos.data?.find(p => p.id === id);
  const equipo = equipos.data?.find(e => e.id === partido?.equipo_id);
  const nombreLocal = partido?.es_local ? equipo?.nombre ?? "Local" : partido?.rival ?? "Local";
  const nombreVisitante = partido?.es_local ? partido.rival : equipo?.nombre ?? "Visitante";
  const [colorLocal, setColorLocal] = useState("#c8102e");
  const [colorVisitante, setColorVisitante] = useState("#1e293b");
  const [directo, setDirecto] = useState(false);
  const [muestra, setMuestra] = useState<MensajeWorker | null>(null);
  const [modo, setModo] = useState<ModoDisposicionVivo>("paralelo");
  const [config, setConfig] = useState<ConfiguracionPlano2D>({
    mostrarEtiquetas: "ninguno", mostrarEstelaBalon: false, altoContraste: false, invertirLados: false,
  });
  const vivo = usePartidoEnVivo({ partidoId: id, activo: directo && id !== null });
  const activo = directo ? vivo.datos : muestra;
  const calidad = activo?.calidad;
  const metricas = useQuery({
    queryKey: ["metricas-partido", id], enabled: id !== null,
    queryFn: async () => (await api.get<{
      acumulado_local: { posesion_pct: number }; acumulado_visitante: { posesion_pct: number };
      posesion_disputa_pct: number;
    }>(`/analisis/partidos/${id}/metricas`)).data,
    refetchInterval: directo ? 5000 : false, retry: false,
  });
  const cambiarFuente = useCallback((esDirecto: boolean) => { setDirecto(esDirecto); setMuestra(null); }, []);
  const recibirMuestra = useCallback((nueva: MensajeWorker | null) => setMuestra(nueva), []);
  const tiempo = activo?.t;
  const reloj = tiempo == null ? "—" : `${Math.floor(tiempo / 60).toString().padStart(2, "0")}:${Math.floor(tiempo % 60).toString().padStart(2, "0")}`;
  const goles = partido ? (partido.es_local ? [partido.goles_favor, partido.goles_contra] : [partido.goles_contra, partido.goles_favor]) : [0, 0];
  const resumen = metricas.data;
  const observado = resumen && resumen.acumulado_local.posesion_pct + resumen.acumulado_visitante.posesion_pct + resumen.posesion_disputa_pct > 0;
  const localPct = directo ? vivo.posesionLocalPct : observado ? resumen.acumulado_local.posesion_pct : null;
  const visitantePct = directo ? vivo.posesionVisitantePct : observado ? resumen.acumulado_visitante.posesion_pct : null;

  return <div className="analisis-sesion">
    <div className="analisis-sesion-barra">
      <label>Partido <select aria-label="Seleccionar partido" value={id ?? ""} onChange={e => {
        setSeleccionado(Number(e.target.value)); setMuestra(null); setDirecto(false);
      }}>
        {!partidos.data?.length && <option value="">{partidos.isPending ? "Cargando…" : "Sin partidos"}</option>}
        {partidos.data?.map(p => <option key={p.id} value={p.id}>{equipos.data?.find(e => e.id === p.equipo_id)?.nombre ?? "Equipo"} · {p.rival}</option>)}
      </select></label>
      <span className="analisis-estado">{directo ? `Directo · ${vivo.estadoConexion}` : "Grabación"}</span>
      <details className="analisis-config"><summary>Configurar vista</summary>
        <div className="analisis-config-contenido">
          <label>Color local <input type="color" value={colorLocal} onChange={e => setColorLocal(e.target.value)} /></label>
          <label>Color visitante <input type="color" value={colorVisitante} onChange={e => setColorVisitante(e.target.value)} /></label>
          <small>Los colores cambian la vista. La clasificación se configura al procesar el video.</small>
          <label>Etiquetas <select value={config.mostrarEtiquetas} onChange={e => setConfig(c => ({ ...c, mostrarEtiquetas: e.target.value as "tid" | "dorsal" | "ninguno" }))}>
            <option value="ninguno">Ocultas</option><option value="tid">Identificador</option><option value="dorsal">Dorsal</option>
          </select></label>
          <label><input type="checkbox" checked={config.invertirLados} onChange={e => setConfig(c => ({ ...c, invertirLados: e.target.checked }))} /> Invertir plano</label>
        </div>
      </details>
    </div>
    {(partidos.isError || equipos.isError) && <p role="alert">No se pudieron cargar los partidos. Revisa la conexión con la API.</p>}
    {id !== null && <>
      <div className="analisis-marcador"><span>{nombreLocal}</span><strong>{goles[0]} — {goles[1]}</strong><span>{nombreVisitante}</span><time>{reloj}</time></div>
      <div className={`analisis-espacio analisis-espacio--${modo}`}>
        <VisorVideoSincronizado key={id} partidoId={id} jugadores={activo?.jugadores ?? []} balon={activo?.balon}
          muestra={activo}
          colorLocal={colorLocal} colorVisitante={colorVisitante} workerTransmitiendo={Boolean(vivo.datos?.calidad.worker_conectado)}
          modoDisposicion={modo} onCambiarModoDisposicion={setModo} onMuestraSincronizada={recibirMuestra} onCambiarFuente={cambiarFuente} />
        <section className="analisis-radar" aria-label="Posiciones sobre la cancha">
          <div className="analisis-radar-cabecera"><h3>Plano de cancha</h3><span>{activo ? `${calidad?.jugadores_detectados ?? 0} jugadores visibles` : "Esperando datos"}</span></div>
          <Plano2DCancha jugadores={activo?.jugadores ?? []} balon={activo?.balon} configuracion={config}
            nombreLocal={nombreLocal} nombreVisitante={nombreVisitante} colorLocal={colorLocal} colorVisitante={colorVisitante}
            campoVisible={calidad?.campo_visible} largoM={calidad?.largo_m} anchoM={calidad?.ancho_m} />
          <p className="analisis-nota">El área resaltada representa el encuadre. Fuera de ella no se conoce la posición actual de los jugadores.</p>
        </section>
      </div>
      <div className="analisis-resumen">
        <section><h3>Posesión del partido</h3><p className="analisis-dato">{localPct == null ? "—" : `${localPct.toFixed(1)}%`} <span>/</span> {visitantePct == null ? "—" : `${visitantePct.toFixed(1)}%`}</p>
          <small>Solo tiempo observado. La disputa se cuenta por separado.</small></section>
        <section><h3>Calidad del análisis</h3><p>{calidad?.estado_calibracion === "SIN_REFERENCIA" ? "Buscando referencias de cancha" : calidad?.estado_calibracion === "PERDIDA" ? "Referencia perdida; buscando recuperación" : calidad?.estado_calibracion === "VERIFICADA" ? "Cancha verificada" : calidad?.estado_calibracion === "SIGUIENDO" ? "Siguiendo movimiento de cámara" : calidad?.motivo ?? (activo ? "Sin incidencias reportadas" : "Sin telemetría procesada")}</p>
          {calidad?.motivo && <small>{calidad.motivo}</small>}
          {vivo.error && <p role="alert">{vivo.error}</p>}
          <details><summary>Ver diagnóstico</summary><p>Procesamiento: {calidad?.fps?.toFixed(1) ?? "—"} cuadros/s · Balón: {calidad?.balon_visible ? "observado" : "no observado"}</p></details>
        </section>
      </div>
    </>}
  </div>;
}
