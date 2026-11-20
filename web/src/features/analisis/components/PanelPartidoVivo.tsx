import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listarEquipos, listarPartidos } from "@/features/deportivo/api";
import { RecomendacionesEnVivo } from "@/features/asistencia/components/RecomendacionesEnVivo"; // T-090 (Alejandra)
import type { Video } from "@/features/vision/types";
import { api } from "@/shared/api/client";
import { obtenerMetricasMinuto } from "../api";
import { usePartidoEnVivo } from "../hooks/usePartidoEnVivo";
import type { ConfiguracionPlano2D, ItemLineaTiempo, MensajeWorker } from "../types";
import { LineaTiempoPartido } from "./LineaTiempoPartido";
import { MetricasDelMinuto } from "./MetricasDelMinuto";
import { Plano2DCancha } from "./Plano2DCancha";
import { usePartidoUrl } from "../hooks/usePartidosAnalisis";
import { VisorVideoSincronizado, type ModoDisposicionVivo } from "./VisorVideoSincronizado";

export function PanelPartidoVivo() {
  const equipos = useQuery({ queryKey: ["equipos"], queryFn: () => listarEquipos() });
  const partidos = useQuery({ queryKey: ["partidos"], queryFn: () => listarPartidos() });
  const { partidoId: seleccionado, videoId, elegir } = usePartidoUrl();
  const id = seleccionado ?? partidos.data?.[0]?.id ?? null;
  const partido = partidos.data?.find((p) => p.id === id);
  const equipo = equipos.data?.find((e) => e.id === partido?.equipo_id);
  const nombreLocal = partido?.es_local ? (equipo?.nombre ?? "Local") : (partido?.rival ?? "Local");
  const nombreVisitante = partido?.es_local ? partido.rival : (equipo?.nombre ?? "Visitante");
  const [grabacion, setGrabacion] = useState<Video | null>(null);
  const [paleta, setPaleta] = useState<{ partidoId: number | null; local?: string; visitante?: string }>();
  const videoActual = grabacion?.partido_id === id ? grabacion : null;
  const colorPropio = videoActual?.color_propio ?? (partido?.es_local ? equipo?.color_local : equipo?.color_visitante);
  const colorRival = videoActual?.color_rival;
  const coloresElegidos = paleta?.partidoId === id ? paleta : undefined;
  const colorLocal = coloresElegidos?.local ?? (partido?.es_local ? colorPropio : colorRival) ?? "#c8102e";
  const colorVisitante = coloresElegidos?.visitante ?? (partido?.es_local ? colorRival : colorPropio) ?? "#1e293b";
  const [directo, setDirecto] = useState(false);
  const [muestra, setMuestra] = useState<MensajeWorker | null>(null);
  const [salto, setSalto] = useState<{ t: number; n: number } | null>(null);
  // CU-47: minuto de la jugada elegida en la cronología; filtra las métricas (null = todo el partido).
  const [minutoFiltro, setMinutoFiltro] = useState<number | null>(null);
  const [modo, setModo] = useState<ModoDisposicionVivo>("paralelo");
  const [config, setConfig] = useState<ConfiguracionPlano2D>({
    mostrarEtiquetas: "ninguno",
    mostrarEstelaBalon: false,
    altoContraste: false,
    invertirLados: false,
  });
  const vivo = usePartidoEnVivo({ partidoId: id, activo: directo && id !== null });
  const activo = directo ? vivo.datos : muestra;
  const calidad = activo?.calidad;
  const metricas = useQuery({
    queryKey: ["metricas-partido", id],
    enabled: id !== null,
    queryFn: async () =>
      (
        await api.get<{
          acumulado_local: { posesion_pct: number };
          acumulado_visitante: { posesion_pct: number };
          posesion_disputa_pct: number;
        }>(`/analisis/partidos/${id}/metricas`)
      ).data,
    refetchInterval: directo ? 5000 : false,
    retry: false,
  });
  const delMinuto = useQuery({
    queryKey: ["metricas-minuto", id, minutoFiltro],
    enabled: id !== null && minutoFiltro !== null,
    retry: false,
    queryFn: () => obtenerMetricasMinuto(id as number, minutoFiltro as number),
  });
  const elegirEvento = useCallback((item: ItemLineaTiempo) => {
    setSalto((s) => ({ t: item.t, n: (s?.n ?? 0) + 1 })); // el plano 2D salta al instante exacto
    setMinutoFiltro(Math.floor(item.t / 60)); // y las métricas, a ese minuto
  }, []);
  const cambiarFuente = useCallback((esDirecto: boolean) => {
    setDirecto(esDirecto);
    setMuestra(null);
  }, []);
  const recibirMuestra = useCallback((nueva: MensajeWorker | null) => setMuestra(nueva), []);
  const tiempo = activo?.t;
  const reloj =
    tiempo == null
      ? "—"
      : `${Math.floor(tiempo / 60)
          .toString()
          .padStart(2, "0")}:${Math.floor(tiempo % 60)
          .toString()
          .padStart(2, "0")}`;
  const goles = partido
    ? partido.es_local
      ? [partido.goles_favor, partido.goles_contra]
      : [partido.goles_contra, partido.goles_favor]
    : [0, 0];
  const resumen = metricas.data;
  const observado =
    resumen &&
    resumen.acumulado_local.posesion_pct +
      resumen.acumulado_visitante.posesion_pct +
      resumen.posesion_disputa_pct >
      0;
  const minuto = minutoFiltro !== null ? delMinuto.data : undefined;
  const localPct = minuto
    ? minuto.local.posesion_pct
    : directo
      ? vivo.posesionLocalPct
      : observado
        ? resumen.acumulado_local.posesion_pct
        : null;
  const visitantePct = minuto
    ? minuto.visitante.posesion_pct
    : directo
      ? vivo.posesionVisitantePct
      : observado
        ? resumen.acumulado_visitante.posesion_pct
        : null;

  return (
    <div className="analisis-sesion">
      <div className="analisis-sesion-barra">
        <label>
          Partido{" "}
          <select
            aria-label="Seleccionar partido"
            value={id ?? ""}
            onChange={(e) => elegir(Number(e.target.value))}
          >
            {!partidos.data?.length && (
              <option value="">{partidos.isPending ? "Cargando…" : "Sin partidos"}</option>
            )}
            {partidos.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {equipos.data?.find((e) => e.id === p.equipo_id)?.nombre ?? "Equipo"} · {p.rival}
              </option>
            ))}
          </select>
        </label>
        <span className="analisis-estado">
          {directo ? `Directo · ${vivo.estadoConexion}` : "Grabación"}
        </span>
        <details className="analisis-config">
          <summary>Configurar vista</summary>
          <div className="analisis-config-contenido">
            <label>
              Color local{" "}
              <input
                type="color"
                value={colorLocal}
                onChange={(e) => setPaleta({ ...coloresElegidos, partidoId: id, local: e.target.value })}
              />
            </label>
            <label>
              Color visitante{" "}
              <input
                type="color"
                value={colorVisitante}
                onChange={(e) => setPaleta({ ...coloresElegidos, partidoId: id, visitante: e.target.value })}
              />
            </label>
            <small>
              Los colores cambian la vista. La clasificación se configura al procesar el video.
            </small>
            <label>
              Etiquetas{" "}
              <select
                value={config.mostrarEtiquetas}
                onChange={(e) =>
                  setConfig((c) => ({
                    ...c,
                    mostrarEtiquetas: e.target.value as "tid" | "dorsal" | "ninguno",
                  }))
                }
              >
                <option value="ninguno">Ocultas</option>
                <option value="tid">Identificador</option>
                <option value="dorsal">Dorsal</option>
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={config.invertirLados}
                onChange={(e) => setConfig((c) => ({ ...c, invertirLados: e.target.checked }))}
              />{" "}
              Invertir plano
            </label>
          </div>
        </details>
      </div>
      {(partidos.isError || equipos.isError) && (
        <p role="alert">No se pudieron cargar los partidos. Revisa la conexión con la API.</p>
      )}
      {id !== null && (
        <>
          <div className="analisis-marcador">
            <span>{nombreLocal}</span>
            <strong>
              {goles[0]} — {goles[1]}
            </strong>
            <span>{nombreVisitante}</span>
            <time>{reloj}</time>
          </div>
          <div className={`analisis-espacio analisis-espacio--${modo}`}>
            <VisorVideoSincronizado
              key={id}
              partidoId={id}
              videoInicialId={videoId}
              jugadores={activo?.jugadores ?? []}
              balon={activo?.balon}
              muestra={activo}
              saltarA={salto}
              colorLocal={colorLocal}
              colorVisitante={colorVisitante}
              workerTransmitiendo={Boolean(vivo.datos?.calidad.worker_conectado)}
              modoDisposicion={modo}
              onCambiarModoDisposicion={setModo}
              onMuestraSincronizada={recibirMuestra}
              onCambiarFuente={cambiarFuente}
              onElegirVideo={setGrabacion}
            />
            <section className="analisis-radar" aria-label="Posiciones sobre la cancha">
              <div className="analisis-radar-cabecera">
                <h3>Plano de cancha</h3>
                <span>
                  {calidad?.calibracion_valida === false
                    ? "Buscando referencia de cancha"
                    : activo
                    ? `${calidad?.jugadores_detectados ?? 0} jugadores visibles`
                    : "Esperando datos"}
                </span>
              </div>
              <Plano2DCancha
                jugadores={calidad?.calibracion_valida === false ? [] : activo?.jugadores ?? []}
                balon={calidad?.calibracion_valida === false ? null : activo?.balon}
                arqueros={activo?.detecciones?.filter(d => d.clase === "PORTERO" &&
                  activo.jugadores.some(j => j.tid === d.tid)).map(d => d.tid)}
                configuracion={config}
                nombreLocal={nombreLocal}
                nombreVisitante={nombreVisitante}
                colorLocal={colorLocal}
                colorVisitante={colorVisitante}
                campoVisible={calidad?.campo_visible}
                largoM={calidad?.largo_m}
                anchoM={calidad?.ancho_m}
              />
              <p className="analisis-nota">
                El área resaltada representa el encuadre. Fuera de ella no se conoce la posición
                actual de los jugadores.
              </p>
            </section>
          </div>
          <div className="analisis-resumen">
            <section>
              <h3>{minuto ? `Posesión del minuto ${minutoFiltro}` : "Posesión del partido"}</h3>
              <p className="analisis-dato">
                {localPct == null ? "—" : `${localPct.toFixed(1)}%`} <span>/</span>{" "}
                {visitantePct == null ? "—" : `${visitantePct.toFixed(1)}%`}
              </p>
              <small>Solo tiempo observado. La disputa se cuenta por separado.</small>
            </section>
            <section>
              <h3>Calidad del análisis</h3>
              <p>
                {calidad?.estado_calibracion === "SIN_REFERENCIA"
                  ? "Buscando referencias de cancha"
                  : calidad?.estado_calibracion === "PERDIDA"
                    ? "Referencia perdida; buscando recuperación"
                    : calidad?.estado_calibracion === "VERIFICADA"
                      ? "Cancha verificada"
                      : calidad?.estado_calibracion === "SIGUIENDO"
                        ? "Siguiendo movimiento de cámara"
                        : (calidad?.motivo ??
                          (activo ? "Sin incidencias reportadas" : "Sin telemetría procesada"))}
              </p>
              {calidad?.motivo && <small>{calidad.motivo}</small>}
              {vivo.error && <p role="alert">{vivo.error}</p>}
              <details>
                <summary>Ver diagnóstico</summary>
                <p>
                  Procesamiento: {calidad?.fps?.toFixed(1) ?? "—"} cuadros/s · Balón:{" "}
                  {calidad?.balon_visible ? "observado" : "no observado"}
                </p>
              </details>
            </section>
          </div>
          {id !== null && <RecomendacionesEnVivo partidoId={id} modoGrabacion={!directo} />} {/* T-090: recomendaciones tácticas en vivo y diferido */}
          {minutoFiltro !== null && (
            <MetricasDelMinuto
              minuto={minutoFiltro}
              datos={delMinuto.data}
              cargando={delMinuto.isPending}
              error={delMinuto.isError}
              nombreLocal={nombreLocal}
              nombreVisitante={nombreVisitante}
              onQuitar={() => setMinutoFiltro(null)}
            />
          )}
          <LineaTiempoPartido
            key={id}
            partidoId={id}
            tiempoActual={directo ? null : activo?.t}
            nombreLocal={nombreLocal}
            nombreVisitante={nombreVisitante}
            minutoFiltro={minutoFiltro}
            onQuitarFiltro={() => setMinutoFiltro(null)}
            onSeleccionar={elegirEvento}
          />
        </>
      )}
    </div>
  );
}
