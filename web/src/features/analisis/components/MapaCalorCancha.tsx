/**
 * Mapa de calor táctico dinámico  —  CU-44 · T-079 (HU-38).
 *
 * Muestra la ocupación espacial por equipo, línea o jugador individual,
 * con coordenadas normalizadas por la dirección de ataque (ataca_hacia)
 * compensando el cambio de lado en el entretiempo.
 *
 * Criterio de aceptación:
 * Un partido completo no queda simétrico por el cambio de lado en el entretiempo.
 */

import { useEffect, useMemo, useState } from "react";

import { listarJugadores } from "@/features/deportivo/api";
import type { Jugador } from "@/features/deportivo/types";

import { obtenerMapaCalor } from "../api";
import type { AlcanceMapaCalor, MapaCalor } from "../types";
import { usePartidosAnalisis, usePartidoUrl } from "../hooks/usePartidosAnalisis";

type IntervaloTiempo = "completo" | "primer_tiempo" | "segundo_tiempo";

function obtenerColorCelda(valor: number): string {
  if (valor < 0.2) return "#00b4d8"; // Azul / Cian suave
  if (valor < 0.45) return "#2ec4b6"; // Cian verdoso
  if (valor < 0.7) return "#55a630"; // Verde lima
  if (valor < 0.85) return "#ffb703"; // Ámbar / Amarillo
  return "#e63946"; // Rojo intenso
}

function obtenerOpacidadCelda(valor: number): number {
  return 0.85 * Math.sqrt(Math.max(0, valor));
}

export function MapaCalorCancha() {
  const { partidoId, elegir } = usePartidoUrl();
  const {
    id: partidoSeleccionadoId, partido: partidoActual,
    partidos: consultaPartidos, equipos: consultaEquipos,
  } = usePartidosAnalisis(partidoId);
  const partidos = consultaPartidos.data ?? [];
  const equipos = consultaEquipos.data ?? [];
  const [jugadores, setJugadores] = useState<Jugador[]>([]);

  const [alcance, setAlcance] = useState<AlcanceMapaCalor>("equipo");
  const [lineaSeleccionada, setLineaSeleccionada] = useState<number>(2); // 1: Def, 2: Med, 3: Del
  const [jugadorSeleccionadoId, setJugadorSeleccionadoId] = useState<number | null>(null);
  const [intervalo, setIntervalo] = useState<IntervaloTiempo>("completo");
  const [altoContraste, setAltoContraste] = useState<boolean>(false);

  const [mapa, setMapa] = useState<MapaCalor | null>(null);
  const [cargando, setCargando] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Cargar jugadores cuando cambia el partido
  useEffect(() => {
    let activo = true;
    if (!partidoActual) return;
    async function cargarPlantel() {
      try {
        const lista = await listarJugadores(partidoActual!.equipo_id, true, "dorsal");
        if (activo) {
          setJugadores(lista);
          if (lista.length > 0 && !jugadorSeleccionadoId) {
            setJugadorSeleccionadoId(lista[0].id);
          }
        }
      } catch {
        // Silenciar si no hay jugadores asignados aún
      }
    }
    void cargarPlantel();
    return () => {
      activo = false;
    };
  }, [partidoActual, jugadorSeleccionadoId]);

  // Cargar datos del mapa de calor
  useEffect(() => {
    let activo = true;
    if (partidoSeleccionadoId === null) return;
    async function cargarMapa(id: number) {
      setCargando(true);
      setError(null);
      setMapa(null);

      let desdeMin = 0;
      let hastaMin = 90;
      if (intervalo === "primer_tiempo") {
        desdeMin = 0;
        hastaMin = 44;
      } else if (intervalo === "segundo_tiempo") {
        desdeMin = 45;
        hastaMin = 90;
      }

      let refId: number | undefined;
      if (alcance === "linea") {
        refId = lineaSeleccionada;
      } else if (alcance === "jugador") {
        refId = jugadorSeleccionadoId ?? undefined;
      }

      try {
        const res = await obtenerMapaCalor(id, {
          alcance,
          referencia_id: refId,
          desde_minuto: desdeMin,
          hasta_minuto: hastaMin,
        });
        if (activo) {
          setMapa(res);
        }
      } catch (err) {
        if (activo) {
          setError(
            err instanceof Error
              ? err.message
              : "No se pudo generar el mapa de calor para este partido.",
          );
        }
      } finally {
        if (activo) setCargando(false);
      }
    }

    void cargarMapa(partidoSeleccionadoId);
    return () => {
      activo = false;
    };
  }, [
    partidoSeleccionadoId,
    alcance,
    lineaSeleccionada,
    jugadorSeleccionadoId,
    intervalo,
  ]);

  // Métricas agregadas de distribución espacial
  const estadisticas = useMemo(() => {
    if (!mapa || mapa.celdas.length === 0) {
      return {
        campoPropioPct: 0,
        campoRivalPct: 0,
        bandaIzquierdaPct: 0,
        carrilCentralPct: 0,
        bandaDerechaPct: 0,
        totalPuntos: 0,
      };
    }

    let sumaTotal = 0;
    let sumaPropio = 0;
    let sumaRival = 0;
    let sumaBandaIzq = 0;
    let sumaCentro = 0;
    let sumaBandaDer = 0;

    for (const c of mapa.celdas) {
      sumaTotal += c.valor;
      if (c.x < mapa.largo_m / 2) {
        sumaPropio += c.valor;
      } else {
        sumaRival += c.valor;
      }

      if (c.y < mapa.ancho_m / 3) {
        sumaBandaIzq += c.valor;
      } else if (c.y <= 2 * mapa.ancho_m / 3) {
        sumaCentro += c.valor;
      } else {
        sumaBandaDer += c.valor;
      }
    }

    const t = sumaTotal > 0 ? sumaTotal : 1;
    return {
      campoPropioPct: Math.round((sumaPropio / t) * 100),
      campoRivalPct: Math.round((sumaRival / t) * 100),
      bandaIzquierdaPct: Math.round((sumaBandaIzq / t) * 100),
      carrilCentralPct: Math.round((sumaCentro / t) * 100),
      bandaDerechaPct: Math.round((sumaBandaDer / t) * 100),
      totalPuntos: mapa.celdas.length,
    };
  }, [mapa]);

  const nombreEquipoLocal = equipos.find((e) => e.id === partidoActual?.equipo_id)?.nombre ?? "Equipo local";

  return (
    <div
      className={`mapa-calor-contenedor ${
        altoContraste ? "mapa-calor-contenedor--alto-contraste" : ""
      }`}
    >
      {/* Barra superior de configuración de filtros */}
      <div className="mapa-calor-filtros-bar">
        <div className="mapa-calor-filtro-item">
          <label className="mapa-calor-label" htmlFor="selector-partido-calor">
            Partido a analizar
          </label>
          <select
            id="selector-partido-calor"
            className="panel-vivo-selector"
            value={partidoSeleccionadoId ?? ""}
            onChange={(e) => elegir(Number(e.target.value))}
          >
            {partidos.length === 0 && (
              <option value="">{consultaPartidos.isPending ? "Cargando partidos…" : "Sin partidos"}</option>
            )}
            {partidos.map((p) => {
              const eq = equipos.find((e) => e.id === p.equipo_id);
              const nombreEq = eq ? eq.nombre : `Equipo ${p.equipo_id}`;
              const fecha = p.fecha_hora ? p.fecha_hora.split("T")[0] : "";
              return (
                <option key={p.id} value={p.id}>
                  {nombreEq} vs. {p.rival} ({fecha})
                </option>
              );
            })}
          </select>
        </div>

        <div className="mapa-calor-filtro-item">
          <label className="mapa-calor-label" htmlFor="selector-intervalo-calor">
            Intervalo de tiempo
          </label>
          <select
            id="selector-intervalo-calor"
            className="panel-vivo-selector"
            value={intervalo}
            onChange={(e) => setIntervalo(e.target.value as IntervaloTiempo)}
          >
            <option value="completo">Todo el partido (0' - 90')</option>
            <option value="primer_tiempo">Primer tiempo (0' - 45')</option>
            <option value="segundo_tiempo">Segundo tiempo (45' - 90')</option>
          </select>
        </div>

        <div className="mapa-calor-filtro-item">
          <label className="mapa-calor-label" htmlFor="selector-alcance-calor">
            Alcance táctico
          </label>
          <div className="mapa-calor-btn-grupo">
            <button
              type="button"
              className={`mapa-calor-btn-pill ${
                alcance === "equipo" ? "mapa-calor-btn-pill--activo" : ""
              }`}
              onClick={() => setAlcance("equipo")}
            >
              Equipo
            </button>
            <button
              type="button"
              className={`mapa-calor-btn-pill ${
                alcance === "linea" ? "mapa-calor-btn-pill--activo" : ""
              }`}
              onClick={() => setAlcance("linea")}
            >
              Línea
            </button>
            <button
              type="button"
              className={`mapa-calor-btn-pill ${
                alcance === "jugador" ? "mapa-calor-btn-pill--activo" : ""
              }`}
              onClick={() => setAlcance("jugador")}
            >
              Jugador
            </button>
          </div>
        </div>

        {alcance === "linea" && (
          <div className="mapa-calor-filtro-item">
            <label className="mapa-calor-label" htmlFor="selector-sublinea">
              Línea de juego
            </label>
            <select
              id="selector-sublinea"
              className="panel-vivo-selector"
              value={lineaSeleccionada}
              onChange={(e) => setLineaSeleccionada(Number(e.target.value))}
            >
              <option value={1}>Línea Defensiva</option>
              <option value={2}>Línea de Mediocampo</option>
              <option value={3}>Línea Delantera</option>
            </select>
          </div>
        )}

        {alcance === "jugador" && (
          <div className="mapa-calor-filtro-item">
            <label className="mapa-calor-label" htmlFor="selector-jugador-calor">
              Jugador
            </label>
            <select
              id="selector-jugador-calor"
              className="panel-vivo-selector"
              value={jugadorSeleccionadoId ?? ""}
              onChange={(e) => setJugadorSeleccionadoId(Number(e.target.value))}
            >
              {jugadores.map((j) => (
                <option key={j.id} value={j.id}>
                  #{j.dorsal} {j.nombre} {j.apellido} ({j.posicion || "JUG"})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="mapa-calor-filtro-acciones">
          <button
            type="button"
            className={`mapa-calor-btn-aux ${
              altoContraste ? "mapa-calor-btn-aux--activo" : ""
            }`}
            onClick={() => setAltoContraste((v) => !v)}
          >
            Alto Contraste: {altoContraste ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {/* Banner de normalización táctica según criterio de aceptación */}
      <div className="mapa-calor-banner-normalizacion">
        <span className="mapa-calor-banner-titulo">
          Ataque normalizado hacia la derecha
        </span>
        <span className="mapa-calor-banner-desc">
          Las coordenadas de ambos periodos se orientan ofensivamente hacia la portería
          derecha. La rotación de campo reglamentaria del descanso no genera simetría
          artificial en el acumulado global del partido.
        </span>
      </div>

      {error && <div className="mapa-calor-error">{error}</div>}
      {mapa && !mapa.celdas.length && (
        <p role="status">
          {alcance === "equipo"
            ? "Sin posiciones válidas del equipo en este intervalo."
            : "Sin posiciones vinculadas a este filtro en el intervalo seleccionado."}
        </p>
      )}

      {/* Cancha con capa de mapa de calor */}
      <div className="mapa-calor-cancha-wrapper">
        {cargando && (
          <div className="mapa-calor-cargando-overlay">
            <span>Generando mapa de calor...</span>
          </div>
        )}

        <div className="mapa-calor-orientacion-barra">
          <span className="mapa-calor-orientacion-mitad">Zona Defensiva Propia</span>
          <span className="mapa-calor-orientacion-flecha">
            Dirección de ataque ofensivo
          </span>
          <span className="mapa-calor-orientacion-mitad">Portería Rival Atacada</span>
        </div>

        <svg
          viewBox="-4 -4 113 76"
          className="mapa-calor-svg"
          preserveAspectRatio="xMidYMid meet"
          aria-label="Mapa de calor táctico de la cancha"
        >
          <defs>
            {/* Filtro de desenfoque gaussiano para fusión térmica fluida */}
            <filter id="calor-blur" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3.6" />
            </filter>
            <clipPath id="calor-limite-cancha">
              <rect x="0" y="0" width="105" height="68" />
            </clipPath>

            {/* Césped reglamentario con franjas */}
            <pattern
              id="franjas-cesped-calor"
              width="10"
              height="68"
              patternUnits="userSpaceOnUse"
            >
              <rect
                x="0"
                y="0"
                width="5"
                height="68"
                fill={altoContraste ? "#0f172a" : "#1b4d2e"}
              />
              <rect
                x="5"
                y="0"
                width="5"
                height="68"
                fill={altoContraste ? "#0b1220" : "#174327"}
              />
            </pattern>
          </defs>

          {/* Fondo del campo */}
          <rect
            x="-4"
            y="-4"
            width="113"
            height="76"
            fill={altoContraste ? "#050811" : "#133820"}
          />
          <rect
            x="0"
            y="0"
            width="105"
            height="68"
            fill="url(#franjas-cesped-calor)"
          />

          {/* CAPA DE CALOR: Celdas de densidad agrupadas con desenfoque */}
          {mapa && mapa.celdas.length > 0 && (
            <g clipPath="url(#calor-limite-cancha)" filter="url(#calor-blur)" opacity="0.9">
              {mapa.celdas.map((c, idx) => (
                <circle
                  key={`heat-${idx}`}
                  cx={c.x * 105 / mapa.largo_m}
                  cy={c.y * 68 / mapa.ancho_m}
                  r={4}
                  fill={obtenerColorCelda(c.valor)}
                  opacity={obtenerOpacidadCelda(c.valor)}
                />
              ))}
            </g>
          )}

          {/* LÍNEAS REGLAMENTARIAS FIFA (105 × 68 m) */}
          <g
            stroke={altoContraste ? "#ffffff" : "#ffffff"}
            strokeWidth="0.5"
            fill="none"
            opacity={altoContraste ? 0.9 : 0.75}
          >
            {/* Perímetro */}
            <rect x="0" y="0" width="105" height="68" />

            {/* Línea media */}
            <line x1="52.5" y1="0" x2="52.5" y2="68" />

            {/* Círculo central y punto de saque */}
            <circle cx="52.5" cy="34" r="9.15" />
            <circle cx="52.5" cy="34" r="0.6" fill="#ffffff" />

            {/* Área Grande Izquierda */}
            <rect x="0" y="13.84" width="16.5" height="40.32" />
            {/* Área Chica Izquierda */}
            <rect x="0" y="24.84" width="5.5" height="18.32" />
            {/* Punto de penal Izquierdo */}
            <circle cx="11" cy="34" r="0.6" fill="#ffffff" />
            {/* Arco de penal Izquierdo */}
            <path d="M 16.5 26.68 A 9.15 9.15 0 0 1 16.5 41.32" />

            {/* Área Grande Derecha */}
            <rect x="88.5" y="13.84" width="16.5" height="40.32" />
            {/* Área Chica Derecha */}
            <rect x="99.5" y="24.84" width="5.5" height="18.32" />
            {/* Punto de penal Derecho */}
            <circle cx="94" cy="34" r="0.6" fill="#ffffff" />
            {/* Arco de penal Derecho */}
            <path d="M 88.5 26.68 A 9.15 9.15 0 0 0 88.5 41.32" />

            {/* Porterías */}
            <rect x="-2" y="30.34" width="2" height="7.32" />
            <rect x="105" y="30.34" width="2" height="7.32" />

            {/* Arcos de esquina */}
            <path d="M 0 1 A 1 1 0 0 0 1 0" />
            <path d="M 0 67 A 1 1 0 0 1 1 68" />
            <path d="M 104 0 A 1 1 0 0 0 105 1" />
            <path d="M 104 68 A 1 1 0 0 1 105 67" />
          </g>
        </svg>

        {/* Leyenda de intensidad térmica */}
        <div className="mapa-calor-leyenda">
          <span className="mapa-calor-leyenda-txt">Baja presencia</span>
          <div className="mapa-calor-gradiente-barra" />
          <span className="mapa-calor-leyenda-txt">Máxima ocupación</span>
        </div>
      </div>

      {/* Tarjetas analíticas de distribución espacial */}
      {estadisticas.totalPuntos > 0 && <div className="mapa-calor-metricas-grid">
        <div className="mapa-calor-card">
          <span className="mapa-calor-card-titulo">Ocupación Longitudinal</span>
          <div className="mapa-calor-progreso-wrap">
            <div className="mapa-calor-progreso-item">
              <span>Campo propio (defensa)</span>
              <strong>{estadisticas.campoPropioPct}%</strong>
            </div>
            <div className="mapa-calor-barra-dual">
              <div
                className="mapa-calor-barra-propia"
                style={{ width: `${estadisticas.campoPropioPct}%` }}
              />
              <div
                className="mapa-calor-barra-rival"
                style={{ width: `${estadisticas.campoRivalPct}%` }}
              />
            </div>
            <div className="mapa-calor-progreso-item">
              <span>Campo rival (ataque)</span>
              <strong>{estadisticas.campoRivalPct}%</strong>
            </div>
          </div>
        </div>

        <div className="mapa-calor-card">
          <span className="mapa-calor-card-titulo">Distribución por Carriles</span>
          <div className="mapa-calor-carriles-lista">
            <div className="mapa-calor-carril-fila">
              <span className="mapa-calor-carril-nom">Banda izquierda</span>
              <div className="mapa-calor-carril-prog">
                <div
                  className="mapa-calor-carril-fill"
                  style={{ width: `${estadisticas.bandaIzquierdaPct}%` }}
                />
              </div>
              <strong className="mapa-calor-carril-num">
                {estadisticas.bandaIzquierdaPct}%
              </strong>
            </div>
            <div className="mapa-calor-carril-fila">
              <span className="mapa-calor-carril-nom">Carril central</span>
              <div className="mapa-calor-carril-prog">
                <div
                  className="mapa-calor-carril-fill"
                  style={{ width: `${estadisticas.carrilCentralPct}%` }}
                />
              </div>
              <strong className="mapa-calor-carril-num">
                {estadisticas.carrilCentralPct}%
              </strong>
            </div>
            <div className="mapa-calor-carril-fila">
              <span className="mapa-calor-carril-nom">Banda derecha</span>
              <div className="mapa-calor-carril-prog">
                <div
                  className="mapa-calor-carril-fill"
                  style={{ width: `${estadisticas.bandaDerechaPct}%` }}
                />
              </div>
              <strong className="mapa-calor-carril-num">
                {estadisticas.bandaDerechaPct}%
              </strong>
            </div>
          </div>
        </div>

        <div className="mapa-calor-card">
          <span className="mapa-calor-card-titulo">Resumen Táctico</span>
          <div className="mapa-calor-resumen-lista">
            <div className="mapa-calor-resumen-item">
              <span className="mapa-calor-resumen-lbl">Equipo:</span>
              <span className="mapa-calor-resumen-val">{nombreEquipoLocal}</span>
            </div>
            <div className="mapa-calor-resumen-item">
              <span className="mapa-calor-resumen-lbl">Filtro aplicado:</span>
              <span className="mapa-calor-resumen-val">
                {alcance === "equipo"
                  ? "Equipo Completo"
                  : alcance === "linea"
                    ? `Línea ${lineaSeleccionada === 1 ? "Defensiva" : lineaSeleccionada === 2 ? "Mediocampo" : "Delantera"}`
                    : `Jugador #${jugadorSeleccionadoId}`}
              </span>
            </div>
            <div className="mapa-calor-resumen-item">
              <span className="mapa-calor-resumen-lbl">Intervalo:</span>
              <span className="mapa-calor-resumen-val">
                {intervalo === "completo"
                  ? "Partido Completo (0'-90')"
                  : intervalo === "primer_tiempo"
                    ? "Primer Tiempo (0'-45')"
                    : "Segundo Tiempo (45'-90')"}
              </span>
            </div>
            <div className="mapa-calor-resumen-item">
              <span className="mapa-calor-resumen-lbl">Celdas activas:</span>
              <span className="mapa-calor-resumen-val">
                {estadisticas.totalPuntos} zonas registradas
              </span>
            </div>
          </div>
        </div>
      </div>}
    </div>
  );
}
