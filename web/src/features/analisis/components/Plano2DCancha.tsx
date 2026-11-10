/**
 * Plano 2D interactivo con posiciones de jugadores y balón en vivo  —  CU-41 · T-078.
 *
 * Renderiza la cancha de fútbol en SVG con dimensiones oficiales FIFA (105 m × 68 m),
 * líneas reglamentarias, círculos para los 22 jugadores con colores de equipo y dorsales/track IDs,
 * e indicador diferenciado del balón con estela de trayectoria reciente.
 *
 * Soporta actualización en tiempo real a 5 Hz y modo de alto contraste para banco de suplentes.
 */

import { memo, useId, useMemo, useState } from "react";

import type {
  ConfiguracionPlano2D,
  EquipoDetectado,
  PosicionDetectada,
  PuntoTrayectoria,
} from "../types";

interface Props {
  jugadores?: PosicionDetectada[];
  balon?: PosicionDetectada | null;
  estelaBalon?: PuntoTrayectoria[];
  configuracion?: Partial<ConfiguracionPlano2D>;
  nombreLocal?: string;
  nombreVisitante?: string;
  colorLocal?: string;
  colorVisitante?: string;
  className?: string;
}

const CONFIG_DEFECTO: ConfiguracionPlano2D = {
  mostrarEtiquetas: "tid",
  mostrarEstelaBalon: true,
  altoContraste: false,
  invertirLados: false,
};

// Dimensiones oficiales FIFA
const LARGO = 105;
const ANCHO = 68;

export function esColorClaro(hex: string): boolean {
  const limpio = hex.replace("#", "");
  if (limpio.length !== 6) return false;
  const r = parseInt(limpio.slice(0, 2), 16);
  const g = parseInt(limpio.slice(2, 4), 16);
  const b = parseInt(limpio.slice(4, 6), 16);
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 165;
}

function obtenerColorEquipo(
  equipo: EquipoDetectado,
  altoContraste: boolean,
  colorLocal?: string,
  colorVisitante?: string,
): { relleno: string; borde: string; texto: string } {
  if (altoContraste) {
    switch (equipo) {
      case "LOCAL":
        return { relleno: "#0284c7", borde: "#ffffff", texto: "#ffffff" };
      case "VISITANTE":
        return { relleno: "#ef4444", borde: "#ffffff", texto: "#ffffff" };
      case "ARBITRO":
        return { relleno: "#facc15", borde: "#000000", texto: "#000000" };
      default:
        return { relleno: "#64748b", borde: "#ffffff", texto: "#ffffff" };
    }
  }

  const cLocal = colorLocal || "#1d4ed8";
  const cVisitante = colorVisitante || "#dc2626";

  switch (equipo) {
    case "LOCAL": {
      const claro = esColorClaro(cLocal);
      return {
        relleno: cLocal,
        borde: claro ? "#0f172a" : "#ffffff",
        texto: claro ? "#0f172a" : "#ffffff",
      };
    }
    case "VISITANTE": {
      const claro = esColorClaro(cVisitante);
      return {
        relleno: cVisitante,
        borde: claro ? "#0f172a" : "#ffffff",
        texto: claro ? "#0f172a" : "#ffffff",
      };
    }
    case "ARBITRO":
      return { relleno: "#eab308", borde: "#1e293b", texto: "#1e293b" };
    default:
      return { relleno: "#64748b", borde: "#ffffff", texto: "#ffffff" };
  }
}

export const Plano2DCancha = memo(function Plano2DCancha({
  jugadores = [],
  balon = null,
  estelaBalon = [],
  configuracion = {},
  nombreLocal = "Local",
  nombreVisitante = "Visitante",
  colorLocal,
  colorVisitante,
  className = "",
}: Props) {
  const [jugadorSeleccionado, setJugadorSeleccionado] = useState<PosicionDetectada | null>(null);
  const clipId = useId();

  // Deduplica jugadores por Track ID asegurando una sola ficha por jugador en el radar
  const jugadoresUnicos = useMemo(() => {
    const mapa = new Map<number, PosicionDetectada>();
    for (const j of jugadores) {
      const actual = mapa.get(j.tid);
      if (!actual || j.conf > (actual.conf ?? 0)) {
        mapa.set(j.tid, j);
      }
    }
    return Array.from(mapa.values());
  }, [jugadores]);

  const cfg: ConfiguracionPlano2D = { ...CONFIG_DEFECTO, ...configuracion };
  const { mostrarEtiquetas, mostrarEstelaBalon, altoContraste, invertirLados } = cfg;

  // Franjas de corte de césped para realismo y contraste (19 franjas de 5.52 m)
  const anchoFranja = LARGO / 19;
  const colorCespedOscuro = altoContraste ? "#0f2e18" : "#1a5127";
  const colorCespedClaro = altoContraste ? "#13381e" : "#1e5b2c";
  const colorLineas = altoContraste ? "#ffffff" : "rgba(255, 255, 255, 0.88)";

  // Coordenadas transformadas si está invertido
  const transformarX = (x: number) => (invertirLados ? LARGO - x : x);
  const transformarY = (y: number) => (invertirLados ? ANCHO - y : y);

  return (
    <div className={`plano-cancha-contenedor ${altoContraste ? "plano-alto-contraste" : ""} ${className}`}>
      {/* Vista previa SVG escalable */}
      <svg
        viewBox="-4 -4 113 76"
        className="plano-cancha-svg"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Plano táctico 2D de posiciones en vivo"
      >
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={LARGO} height={ANCHO} rx="1" />
          </clipPath>
          {/* Patrón de red de arco */}
          <pattern id="red-arco" width="0.8" height="0.8" patternUnits="userSpaceOnUse">
            <path d="M 0 0 L 0.8 0.8 M 0.8 0 L 0 0.8" stroke="rgba(255,255,255,0.25)" strokeWidth="0.1" />
          </pattern>
        </defs>

        {/* Zona exterior de césped / bandas */}
        <rect
          x="-4"
          y="-4"
          width="113"
          height="76"
          fill={altoContraste ? "#0b2011" : "#143f1f"}
          rx="2"
        />

        {/* Cancha con franjas alternadas */}
        <g clipPath={`url(#${clipId})`}>
          {Array.from({ length: 19 }).map((_, i) => (
            <rect
              key={i}
              x={i * anchoFranja}
              y="0"
              width={anchoFranja}
              height={ANCHO}
              fill={i % 2 === 0 ? colorCespedOscuro : colorCespedClaro}
            />
          ))}
        </g>

        {/* Líneas reglamentarias reglamentarias de la cancha (FIFA 105 × 68 m) */}
        <g fill="none" stroke={colorLineas} strokeWidth="0.38" strokeLinecap="round">
          {/* Perímetro */}
          <rect x="0" y="0" width={LARGO} height={ANCHO} />

          {/* Línea de medio campo */}
          <line x1="52.5" y1="0" x2="52.5" y2={ANCHO} />

          {/* Círculo central (radio 9.15 m) y punto central */}
          <circle cx="52.5" cy="34" r="9.15" />
          <circle cx="52.5" cy="34" r="0.4" fill={colorLineas} />

          {/* Área grande local (izquierda, 16.5 × 40.32 m) */}
          <rect x="0" y="13.84" width="16.5" height="40.32" />

          {/* Área grande visitante (derecha, 16.5 × 40.32 m) */}
          <rect x="88.5" y="13.84" width="16.5" height="40.32" />

          {/* Área chica local (5.5 × 18.32 m) */}
          <rect x="0" y="24.84" width="5.5" height="18.32" />

          {/* Área chica visitante (5.5 × 18.32 m) */}
          <rect x="99.5" y="24.84" width="5.5" height="18.32" />

          {/* Puntos penales (a 11 m de la línea de meta) */}
          <circle cx="11" cy="34" r="0.4" fill={colorLineas} />
          <circle cx="94" cy="34" r="0.4" fill={colorLineas} />

          {/* Semicírculo área local (radio 9.15 m con centro en el penal) */}
          <path d="M 16.5 26.69 A 9.15 9.15 0 0 1 16.5 41.31" />

          {/* Semicírculo área visitante (radio 9.15 m) */}
          <path d="M 88.5 26.69 A 9.15 9.15 0 0 0 88.5 41.31" />

          {/* Arcos de esquina (radio 1 m) */}
          <path d="M 0 1 A 1 1 0 0 0 1 0" />
          <path d="M 104 0 A 1 1 0 0 0 105 1" />
          <path d="M 0 67 A 1 1 0 0 1 1 68" />
          <path d="M 104 68 A 1 1 0 0 1 105 67" />

          {/* Arcos (7.32 × 2.44 m detrás de la línea) */}
          <rect x="-2.44" y="30.34" width="2.44" height="7.32" fill="url(#red-arco)" />
          <rect x="105" y="30.34" width="2.44" height="7.32" fill="url(#red-arco)" />
        </g>

        {/* Estela de trayectoria reciente del balón (resaltada en color ámbar neón) */}
        {mostrarEstelaBalon && estelaBalon.length > 1 && (
          <g className="plano-estela-grupo">
            {estelaBalon.map((p, idx) => {
              const opacidad = ((idx + 1) / estelaBalon.length) * 0.75;
              const radio = 0.35 + ((idx + 1) / estelaBalon.length) * 0.45;
              const ex = transformarX(Math.min(LARGO - 0.5, Math.max(0.5, p.x)));
              const ey = transformarY(Math.min(ANCHO - 0.5, Math.max(0.5, p.y)));
              return (
                <circle
                  key={`estela-${idx}`}
                  cx={ex}
                  cy={ey}
                  r={radio}
                  fill="#ff8533"
                  opacity={opacidad}
                />
              );
            })}
          </g>
        )}

        {/* Jugadores detectados con interpolación fluida de posición y acotados al campo */}
        {jugadoresUnicos.map((j) => {
          const col = obtenerColorEquipo(j.equipo, altoContraste, colorLocal, colorVisitante);
          const px = transformarX(Math.min(LARGO - 0.8, Math.max(0.8, j.x)));
          const py = transformarY(Math.min(ANCHO - 0.8, Math.max(0.8, j.y)));
          const esSeleccionado = jugadorSeleccionado?.tid === j.tid;

          const etiqueta =
            mostrarEtiquetas === "dorsal"
              ? j.dorsal != null
                ? String(j.dorsal)
                : ""
              : mostrarEtiquetas === "tid"
                ? String(j.tid)
                : "";

          const tamanoFuente = etiqueta.length > 3 ? "0.95" : etiqueta.length > 2 ? "1.15" : "1.35";

          return (
            <g
              key={j.tid}
              className={`plano-jugador-grupo ${esSeleccionado ? "plano-jugador--activo" : ""}`}
              transform={`translate(${px}, ${py})`}
              style={{
                cursor: "pointer",
                transition: "transform 0.22s cubic-bezier(0.25, 0.1, 0.25, 1)",
              }}
              onClick={() => setJugadorSeleccionado(j)}
            >
              {/* Halo de selección */}
              {esSeleccionado && (
                <circle
                  cx={0}
                  cy={0}
                  r="2.6"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="0.5"
                  strokeDasharray="1 0.6"
                />
              )}

              {/* Ficha circular del jugador (radio 1.55 m) */}
              <circle
                cx={0}
                cy={0}
                r="1.55"
                fill={col.relleno}
                stroke={col.borde}
                strokeWidth={altoContraste ? "0.45" : "0.35"}
              />

              {/* Etiqueta / Número */}
              {etiqueta && (
                <text
                  x={0}
                  y={0.1}
                  fill={col.texto}
                  fontSize={tamanoFuente}
                  fontWeight="bold"
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{ userSelect: "none", pointerEvents: "none" }}
                >
                  {etiqueta}
                </text>
              )}

              <title>
                {`Jugador ${j.tid} (${j.equipo})\n` +
                  `Dorsal: ${j.dorsal ?? "Sin asignar"}\n` +
                  `Posición: (${j.x.toFixed(1)} m, ${j.y.toFixed(1)} m)\n` +
                  `Confianza: ${(j.conf * 100).toFixed(0)}%`}
              </title>
            </g>
          );
        })}

        {/* Balón táctico: SIEMPRE por encima de todos los jugadores y en color naranja neón resaltante */}
        {balon && (
          <g
            className="plano-balon-grupo"
            transform={`translate(${transformarX(Math.min(LARGO - 0.5, Math.max(0.5, balon.x)))}, ${transformarY(Math.min(ANCHO - 0.5, Math.max(0.5, balon.y)))})`}
            style={{
              transition: "transform 0.18s cubic-bezier(0.25, 0.1, 0.25, 1)",
              filter: "drop-shadow(0 0 3px rgba(255, 107, 0, 0.75))",
            }}
          >
            {/* Halo pulsante de visibilidad máxima */}
            <circle
              cx={0}
              cy={0}
              r="2.2"
              fill="rgba(255, 107, 0, 0.45)"
            />
            {/* Esfera del balón en Naranja Neón Eléctrico */}
            <circle
              cx={0}
              cy={0}
              r="1.15"
              fill="#ff6b00"
              stroke="#ffffff"
              strokeWidth="0.4"
            />
            {/* Núcleo reflectivo de alto contraste */}
            <circle
              cx={-0.25}
              cy={-0.25}
              r="0.4"
              fill="#ffffff"
            />
            <circle
              cx={0.2}
              cy={0.2}
              r="0.28"
              fill="#0f172a"
            />
            <title>{`Balón\nPosición: (${balon.x.toFixed(1)} m, ${balon.y.toFixed(1)} m)\nConfianza: ${(balon.conf * 100).toFixed(0)}%`}</title>
          </g>
        )}
      </svg>

      {/* Barra de estado inferior del plano */}
      <div className="plano-pie-info">
        <div className="plano-leyenda">
          <span className="plano-leyenda-item">
            <span
              className="plano-leyenda-color"
              style={{
                backgroundColor: obtenerColorEquipo("LOCAL", altoContraste, colorLocal).relleno,
              }}
            />
            {nombreLocal}
          </span>
          <span className="plano-leyenda-item">
            <span
              className="plano-leyenda-color"
              style={{
                backgroundColor: obtenerColorEquipo(
                  "VISITANTE",
                  altoContraste,
                  undefined,
                  colorVisitante,
                ).relleno,
              }}
            />
            {nombreVisitante}
          </span>
          <span className="plano-leyenda-item">
            <span
              className="plano-leyenda-color"
              style={{ backgroundColor: obtenerColorEquipo("ARBITRO", altoContraste).relleno }}
            />
            Árbitro
          </span>
          <span className="plano-leyenda-item">
            <span className="plano-leyenda-color plano-leyenda-balon" />
            Balón
          </span>
        </div>

        <div className="plano-orientacion-nota">
          {invertirLados
            ? `← Ataque ${nombreLocal} | Ataque ${nombreVisitante} →`
            : `Ataque ${nombreLocal} → | ← Ataque ${nombreVisitante}`}
        </div>
      </div>

      {/* Detalle del jugador seleccionado */}
      {jugadorSeleccionado && (
        <div className="plano-detalle-seleccion">
          <div className="plano-detalle-contenido">
            <strong>
              Track {jugadorSeleccionado.tid} ({jugadorSeleccionado.equipo})
            </strong>
            <span>
              X: {jugadorSeleccionado.x.toFixed(1)} m | Y: {jugadorSeleccionado.y.toFixed(1)} m
            </span>
            <span>Confianza: {(jugadorSeleccionado.conf * 100).toFixed(0)} %</span>
          </div>
          <button
            type="button"
            className="plano-detalle-cerrar"
            onClick={() => setJugadorSeleccionado(null)}
          >
            Cerrar
          </button>
        </div>
      )}
    </div>
  );
});

