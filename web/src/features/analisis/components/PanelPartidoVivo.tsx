/**
 * Panel del partido en vivo  —  CU-40 · T-077 (HU-34).
 *
 * Marcador, cronómetro de juego, posesión y métricas de calidad (CU-39)
 * actualizándose en tiempo real por WebSocket sin recargar página.
 * Integra el plano 2D táctico de posiciones (CU-41 · T-078).
 * Diseñado con alto contraste adaptado para uso en banco de suplentes.
 */

import { useEffect, useMemo, useState } from "react";

import { listarEquipos, listarPartidos } from "@/features/deportivo/api";
import type { Equipo, Partido } from "@/features/deportivo/types";

import { usePartidoEnVivo } from "../hooks/usePartidoEnVivo";
import type { ConfiguracionPlano2D } from "../types";
import { Plano2DCancha } from "./Plano2DCancha";

interface Props {
  partidoIdInicial?: number;
}

export function PanelPartidoVivo({ partidoIdInicial }: Props) {
  const [partidos, setPartidos] = useState<Partido[]>([]);
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [partidoIdInput, setPartidoIdInput] = useState<string>(
    partidoIdInicial ? String(partidoIdInicial) : "1",
  );
  const [partidoSeleccionadoId, setPartidoSeleccionadoId] = useState<number>(
    partidoIdInicial ?? 1,
  );

  const [configPlano, setConfigPlano] = useState<ConfiguracionPlano2D>({
    mostrarEtiquetas: "tid",
    mostrarEstelaBalon: true,
    altoContraste: false,
    invertirLados: false,
  });

  // Conexión WebSocket viva al partido
  const {
    estadoConexion,
    datos,
    posesionLocalPct,
    posesionVisitantePct,
    estelaBalon,
    error,
    reconectar,
    desconectar,
  } = usePartidoEnVivo({
    partidoId: partidoSeleccionadoId,
    activo: true,
  });

  // Cargar lista de partidos y equipos para el selector
  useEffect(() => {
    let activo = true;
    async function cargar() {
      try {
        const [listaPartidos, listaEquipos] = await Promise.all([
          listarPartidos(),
          listarEquipos(),
        ]);
        if (activo) {
          setPartidos(listaPartidos);
          setEquipos(listaEquipos);
          if (listaPartidos.length > 0 && !partidoIdInicial) {
            setPartidoSeleccionadoId(listaPartidos[0].id);
            setPartidoIdInput(String(listaPartidos[0].id));
          }
        }
      } catch {
        // En caso de no haber partidos en base de datos, queda con valor por defecto
      }
    }
    void cargar();
    return () => {
      activo = false;
    };
  }, [partidoIdInicial]);

  // Diccionario de equipos por ID
  const mapaEquipos = useMemo(() => {
    const map = new Map<number, Equipo>();
    equipos.forEach((e) => map.set(e.id, e));
    return map;
  }, [equipos]);

  // Partido actual seleccionado de la lista (si existe)
  const partidoActual = useMemo(
    () => partidos.find((p) => p.id === partidoSeleccionadoId) ?? null,
    [partidos, partidoSeleccionadoId],
  );

  const equipoPropio = partidoActual ? mapaEquipos.get(partidoActual.equipo_id) : null;
  const nombreEquipoPropio = equipoPropio?.nombre ?? "Nuestro Club";

  const nombreLocal = partidoActual
    ? partidoActual.es_local
      ? nombreEquipoPropio
      : partidoActual.rival
    : "Local";

  const nombreVisitante = partidoActual
    ? partidoActual.es_local
      ? partidoActual.rival
      : nombreEquipoPropio
    : "Visitante";

  const colorLocal = partidoActual?.es_local ? equipoPropio?.color_local : undefined;
  const colorVisitante = !partidoActual?.es_local ? equipoPropio?.color_visitante : undefined;

  const golesLocal = partidoActual
    ? partidoActual.es_local
      ? partidoActual.goles_favor
      : partidoActual.goles_contra
    : 0;

  const golesVisitante = partidoActual
    ? partidoActual.es_local
      ? partidoActual.goles_contra
      : partidoActual.goles_favor
    : 0;

  // Cronómetro formateado MM:SS a partir de t (segundos transcurridos)
  const tiempoSegundos = datos?.t ?? 0;
  const minutos = Math.floor(tiempoSegundos / 60);
  const segundos = Math.floor(tiempoSegundos % 60);
  const relojFormateado = `${String(minutos).padStart(2, "0")}:${String(segundos).padStart(2, "0")}`;
  const periodo = minutos < 45 ? "1T" : "2T";

  const calidad = datos?.calidad;

  const manejarCambioPartido = (id: number) => {
    setPartidoSeleccionadoId(id);
    setPartidoIdInput(String(id));
  };

  const aplicarIdManual = () => {
    const num = parseInt(partidoIdInput, 10);
    if (!isNaN(num) && num > 0) {
      setPartidoSeleccionadoId(num);
    }
  };

  return (
    <div
      className={`panel-vivo ${configPlano.altoContraste ? "panel-vivo--alto-contraste" : ""}`}
    >
      {/* Barra superior de control y selección de partido */}
      <div className="panel-vivo-barra-superior">
        <div className="panel-vivo-selector-wrap">
          <label htmlFor="select-partido-activo" className="panel-vivo-label">
            Partido:
          </label>
          {partidos.length > 0 ? (
            <select
              id="select-partido-activo"
              className="panel-vivo-select"
              value={partidoSeleccionadoId}
              onChange={(e) => manejarCambioPartido(Number(e.target.value))}
              aria-label="Seleccionar partido"
            >
              {partidos.map((p) => {
                const eq = mapaEquipos.get(p.equipo_id);
                return (
                  <option key={p.id} value={p.id}>
                    Partido #{p.id} — {eq?.nombre ?? "Equipo"} vs {p.rival} ({p.estado})
                  </option>
                );
              })}
            </select>
          ) : (
            <div className="panel-vivo-input-grupo">
              <input
                id="select-partido-activo"
                type="number"
                min="1"
                className="panel-vivo-input"
                value={partidoIdInput}
                onChange={(e) => setPartidoIdInput(e.target.value)}
              />
              <button
                type="button"
                className="panel-vivo-btn-accion"
                onClick={aplicarIdManual}
              >
                Cargar
              </button>
            </div>
          )}
        </div>

        {/* Estado de conexión */}
        <div className="panel-vivo-conexion">
          <span
            className={`panel-conexion-punto panel-conexion-punto--${estadoConexion}`}
            aria-hidden="true"
          />
          <span className="panel-conexion-texto">
            {estadoConexion === "conectado" && "EN VIVO"}
            {estadoConexion === "conectando" && "CONECTANDO"}
            {estadoConexion === "reconectando" && "RECONECTANDO"}
            {estadoConexion === "desconectado" && "DESCONECTADO"}
            {estadoConexion === "error" && "ERROR CONEXION"}
          </span>

          {estadoConexion === "conectado" ? (
            <button
              type="button"
              className="panel-vivo-btn-secundario"
              onClick={desconectar}
            >
              Desconectar
            </button>
          ) : (
            <button
              type="button"
              className="panel-vivo-btn-primario"
              onClick={reconectar}
            >
              Reconectar
            </button>
          )}
        </div>
      </div>

      {/* Banner de error o advertencia */}
      {error && (
        <div className="panel-vivo-alerta panel-vivo-alerta--error" role="alert">
          <span>{error}</span>
        </div>
      )}

      {calidad?.degradado && (
        <div className="panel-vivo-alerta panel-vivo-alerta--aviso" role="alert">
          <strong>Calidad de transmisión degradada:</strong>
          <span>
            {calidad.motivo ??
              "Detección reducida de jugadores o pérdida temporal del balón."}
          </span>
        </div>
      )}

      {/* Marcador, cronómetro y posesión (CU-40) */}
      <section className="panel-vivo-marcador-seccion" aria-label="Marcador y tiempo de juego">
        {/* Equipo Local */}
        <div className="panel-marcador-equipo panel-marcador-equipo--local">
          <span className="panel-marcador-nombre" title={nombreLocal}>
            {nombreLocal}
          </span>
          <span className="panel-marcador-etiqueta-lado">LOCAL</span>
          <span className="panel-marcador-goles">{golesLocal}</span>
        </div>

        {/* Cronómetro central */}
        <div className="panel-marcador-reloj-bloque">
          <span className="panel-reloj-periodo">{periodo}</span>
          <span className="panel-reloj-tiempo" aria-label={`Minuto ${minutos}, segundo ${segundos}`}>
            {relojFormateado}
          </span>
          <span className="panel-reloj-segundos-crudos">{tiempoSegundos.toFixed(1)}s</span>
        </div>

        {/* Equipo Visitante */}
        <div className="panel-marcador-equipo panel-marcador-equipo--visitante">
          <span className="panel-marcador-goles">{golesVisitante}</span>
          <span className="panel-marcador-etiqueta-lado">VISITANTE</span>
          <span className="panel-marcador-nombre" title={nombreVisitante}>
            {nombreVisitante}
          </span>
        </div>
      </section>

      {/* Barra de Posesión en vivo */}
      <section className="panel-posesion-seccion" aria-label="Posesión del intervalo actual">
        <div className="panel-posesion-cabecera">
          <span className="panel-posesion-label">Posesión estimada</span>
          <div className="panel-posesion-valores">
            <span className="panel-posesion-val panel-posesion-val--local">
              {posesionLocalPct}%
            </span>
            <span className="panel-posesion-separador">-</span>
            <span className="panel-posesion-val panel-posesion-val--visitante">
              {posesionVisitantePct}%
            </span>
          </div>
        </div>
        <div className="panel-posesion-barra">
          <div
            className="panel-posesion-segmento panel-posesion-segmento--local"
            style={{ width: `${posesionLocalPct}%` }}
            title={`Local: ${posesionLocalPct}%`}
          />
          <div
            className="panel-posesion-segmento panel-posesion-segmento--visitante"
            style={{ width: `${posesionVisitantePct}%` }}
            title={`Visitante: ${posesionVisitantePct}%`}
          />
        </div>
      </section>

      {/* Barra de controles del radar 2D */}
      <div className="panel-controles-plano">
        <div className="panel-controles-grupo">
          <label className="panel-control-etiqueta" htmlFor="select-etiquetas-plano">
            Etiquetas:
          </label>
          <select
            id="select-etiquetas-plano"
            className="panel-control-select"
            value={configPlano.mostrarEtiquetas}
            onChange={(e) =>
              setConfigPlano((prev) => ({
                ...prev,
                mostrarEtiquetas: e.target.value as "dorsal" | "tid" | "ninguno",
              }))
            }
          >
            <option value="tid">ID de Tracking (tid)</option>
            <option value="dorsal">Dorsal</option>
            <option value="ninguno">Sin etiquetas</option>
          </select>
        </div>

        <button
          type="button"
          className={`panel-toggle-btn ${configPlano.mostrarEstelaBalon ? "panel-toggle-btn--activo" : ""}`}
          onClick={() =>
            setConfigPlano((prev) => ({
              ...prev,
              mostrarEstelaBalon: !prev.mostrarEstelaBalon,
            }))
          }
        >
          {configPlano.mostrarEstelaBalon ? "Estela Balón: ON" : "Estela Balón: OFF"}
        </button>

        <button
          type="button"
          className={`panel-toggle-btn ${configPlano.invertirLados ? "panel-toggle-btn--activo" : ""}`}
          onClick={() =>
            setConfigPlano((prev) => ({
              ...prev,
              invertirLados: !prev.invertirLados,
            }))
          }
        >
          Invertir lados
        </button>

        <button
          type="button"
          className={`panel-toggle-btn ${configPlano.altoContraste ? "panel-toggle-btn--activo" : ""}`}
          onClick={() =>
            setConfigPlano((prev) => ({
              ...prev,
              altoContraste: !prev.altoContraste,
            }))
          }
        >
          {configPlano.altoContraste ? "Alto Contraste: ON" : "Alto Contraste: OFF"}
        </button>
      </div>

      {/* Visualización del Plano 2D interactivo (CU-41 · T-078) */}
      <section className="panel-vivo-cancha-wrapper" aria-label="Plano 2D en vivo de la cancha">
        <div className="panel-cancha-relativa">
          <Plano2DCancha
            jugadores={datos?.jugadores ?? []}
            balon={datos?.balon}
            estelaBalon={estelaBalon}
            configuracion={configPlano}
            nombreLocal={nombreLocal}
            nombreVisitante={nombreVisitante}
            colorLocal={colorLocal}
            colorVisitante={colorVisitante}
          />

          {/* Banner informativo mientras se esperan datos */}
          {!datos && estadoConexion === "conectado" && (
            <div className="plano-esperando-overlay">
              <div className="plano-esperando-card">
                <span className="plano-esperando-pulso" aria-hidden="true" />
                <strong>Canal en vivo conectado (Partido #{partidoSeleccionadoId})</strong>
                <p>
                  Esperando flujo de posiciones del worker de visión o del emisor simulado (a 5 Hz).
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Telemetría y Supervisión de Calidad (CU-39) */}
      <footer className="panel-telemetria-seccion" aria-label="Telemetría y calidad de transmisión">
        <div className="panel-telemetria-card">
          <span className="panel-telemetria-label">Frecuencia de datos</span>
          <span className="panel-telemetria-valor">
            {calidad ? `${calidad.fps.toFixed(1)} Hz` : "0.0 Hz"}
          </span>
          <span className="panel-telemetria-meta">Meta: ~5.0 Hz</span>
        </div>

        <div className="panel-telemetria-card">
          <span className="panel-telemetria-label">Latencia de captura</span>
          <span
            className={`panel-telemetria-valor ${
              (calidad?.retraso_s ?? 0) < 1.0
                ? "texto-verde"
                : (calidad?.retraso_s ?? 0) < 2.0
                  ? "texto-amarillo"
                  : "texto-rojo"
            }`}
          >
            {calidad ? `${calidad.retraso_s.toFixed(2)} s` : "—"}
          </span>
          <span className="panel-telemetria-meta">&lt; 2.0 s requeridos</span>
        </div>

        <div className="panel-telemetria-card">
          <span className="panel-telemetria-label">Jugadores en campo</span>
          <span className="panel-telemetria-valor">
            {calidad ? `${calidad.jugadores_detectados} detectados` : "0"}
          </span>
          <span className="panel-telemetria-meta">22 jugadores esperados</span>
        </div>

        <div className="panel-telemetria-card">
          <span className="panel-telemetria-label">Visibilidad balón</span>
          <span
            className={`panel-telemetria-valor ${
              calidad?.balon_visible ? "texto-verde" : "texto-amarillo"
            }`}
          >
            {calidad?.balon_visible ? "Visible" : "No detectado"}
          </span>
          <span className="panel-telemetria-meta">Cámara táctica</span>
        </div>

        <div className="panel-telemetria-card">
          <span className="panel-telemetria-label">Estado del worker</span>
          <span
            className={`panel-telemetria-valor ${
              calidad?.worker_conectado ? "texto-verde" : "texto-rojo"
            }`}
          >
            {calidad?.worker_conectado ? "Transmitiendo" : "Inactivo"}
          </span>
          <span className="panel-telemetria-meta">Ingesta WebSocket</span>
        </div>
      </footer>
    </div>
  );
}
