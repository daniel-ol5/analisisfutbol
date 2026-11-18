import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { obtenerRedPases } from "../api";
import {
  ANCHO_CANCHA,
  dentroDeCancha,
  flechasDeRed,
  LARGO_CANCHA,
  radioNodo,
} from "../circulacion";
import type { LadoPartido, NodoPase } from "../types";
import { SelectorPartido, usePartidosAnalisis } from "./SelectorPartido";

const LINEA = "rgba(255,255,255,.88)";
const FLECHA = "#f9d65c";
const DESTACADO = "#facc15";

const etiqueta = (n: NodoPase) => `${n.dorsal != null ? `#${n.dorsal} ` : ""}${n.nombre}`;

/** CU-48 · Red de pases sobre el plano de cancha. Cada equipo se ve atacando hacia la derecha. */
export function RedPasesCancha() {
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [equipo, setEquipo] = useState<LadoPartido>("LOCAL");
  const [desde, setDesde] = useState(0);
  const [hasta, setHasta] = useState(90);
  const [minimo, setMinimo] = useState(2);
  const { id, nombreLocal, nombreVisitante } = usePartidosAnalisis(seleccionado);
  const rangoValido = hasta >= desde;
  const red = useQuery({
    queryKey: ["red-pases", id, equipo, desde, hasta],
    enabled: id !== null && rangoValido,
    retry: false,
    queryFn: () =>
      obtenerRedPases(id as number, { desde_minuto: desde, hasta_minuto: hasta, equipo }),
  });
  const nodos = useMemo(() => red.data?.nodos ?? [], [red.data]);
  const flechas = useMemo(
    () => flechasDeRed(red.data?.aristas ?? [], nodos, minimo),
    [red.data, nodos, minimo],
  );
  const porId = useMemo(() => new Map(nodos.map((n) => [n.jugador_id, n])), [nodos]);
  const maxRecibidos = Math.max(0, ...nodos.map((n) => n.pases_recibidos));
  const total = (red.data?.aristas ?? []).reduce((s, a) => s + a.pases, 0);
  const masRecibidos = useMemo(
    () =>
      nodos
        .filter((n) => n.mayor_recepcion)
        .sort((a, b) => b.pases_recibidos - a.pases_recibidos || a.jugador_id - b.jugador_id),
    [nodos],
  );
  const aislados = useMemo(() => nodos.filter((n) => n.aislado), [nodos]);

  return (
    <div className="analisis-sesion">
      <div className="analisis-sesion-barra">
        <SelectorPartido valor={id} onCambiar={setSeleccionado} />
        <label>
          Equipo{" "}
          <select value={equipo} onChange={(e) => setEquipo(e.target.value as LadoPartido)}>
            <option value="LOCAL">{nombreLocal}</option>
            <option value="VISITANTE">{nombreVisitante}</option>
          </select>
        </label>
        <label>
          Desde el min{" "}
          <input
            type="number"
            min={0}
            max={150}
            value={desde}
            onChange={(e) => setDesde(Math.max(0, Number(e.target.value)))}
          />
        </label>
        <label>
          Hasta el min{" "}
          <input
            type="number"
            min={0}
            max={150}
            value={hasta}
            onChange={(e) => setHasta(Math.max(0, Number(e.target.value)))}
          />
        </label>
        <label>
          Pases mínimos{" "}
          <input
            type="number"
            min={1}
            max={50}
            value={minimo}
            onChange={(e) => setMinimo(Math.max(1, Number(e.target.value)))}
          />
        </label>
      </div>
      {!rangoValido && <p role="alert">El minuto final no puede ser menor que el inicial.</p>}
      {red.isError && <p role="alert">No se pudo cargar la red de pases.</p>}
      <section className="analisis-radar" aria-label="Red de pases sobre la cancha">
        <div className="analisis-radar-cabecera">
          <h3>Circulación del balón</h3>
          <span>
            {red.isPending ? "Cargando…" : `${total} pases entre ${nodos.length} jugadores`}
          </span>
        </div>
        <svg
          viewBox="-4 -4 113 76"
          className="plano-cancha-svg"
          role="img"
          aria-label="Grafo de pases sobre la cancha"
        >
          <rect x="-4" y="-4" width="113" height="76" fill="#143f1f" rx="2" />
          <rect
            x="0"
            y="0"
            width={LARGO_CANCHA}
            height={ANCHO_CANCHA}
            fill="#1a5127"
            stroke={LINEA}
            strokeWidth=".3"
          />
          <line x1="52.5" y1="0" x2="52.5" y2="68" stroke={LINEA} strokeWidth=".3" />
          <circle cx="52.5" cy="34" r="9.15" fill="none" stroke={LINEA} strokeWidth=".3" />
          {[0, 1].map((lado) => (
            <g key={lado} fill="none" stroke={LINEA} strokeWidth=".3">
              <rect x={lado ? LARGO_CANCHA - 16.5 : 0} y="13.84" width="16.5" height="40.32" />
              <rect x={lado ? LARGO_CANCHA - 5.5 : 0} y="24.84" width="5.5" height="18.32" />
            </g>
          ))}
          {flechas.map((f) => {
            const origen = porId.get(f.origen_id);
            const destino = porId.get(f.destino_id);
            const opacidad = 0.55 + 0.4 * Math.min(1, f.grosor / 2.2);
            return (
              <g
                key={`${f.origen_id}-${f.destino_id}`}
                className="red-flecha"
                fill={FLECHA}
                stroke={FLECHA}
                opacity={opacidad}
              >
                <title>{`${origen ? etiqueta(origen) : f.origen_id} → ${destino ? etiqueta(destino) : f.destino_id}: ${f.pases} pases`}</title>
                <line
                  x1={f.x1}
                  y1={f.y1}
                  x2={f.x2}
                  y2={f.y2}
                  strokeWidth={f.grosor}
                  strokeLinecap="butt"
                />
                <polygon points={f.cabeza} stroke="none" />
              </g>
            );
          })}
          {nodos.map((n) => {
            const p = dentroDeCancha(n);
            const r = radioNodo(n.pases_recibidos, maxRecibidos);
            const color = n.aislado ? "#64748b" : n.equipo === "VISITANTE" ? "#1e293b" : "#c8102e";
            return (
              <g
                key={n.jugador_id}
                className={n.aislado ? "red-nodo red-nodo--aislado" : "red-nodo"}
              >
                {n.mayor_recepcion && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={r + 0.9}
                    fill="none"
                    stroke={DESTACADO}
                    strokeWidth=".7"
                  />
                )}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={color}
                  fillOpacity={n.aislado ? 0.7 : 1}
                  stroke="#fff"
                  strokeWidth=".4"
                  strokeDasharray={n.aislado ? ".9 .7" : undefined}
                >
                  <title>{`${etiqueta(n)}: envió ${n.pases} y recibió ${n.pases_recibidos} pases${n.mayor_recepcion ? " · de los que más reciben" : ""}${n.aislado ? " · desconectado del circuito" : ""}`}</title>
                </circle>
                <text
                  x={p.x}
                  y={p.y}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize="2.2"
                  fill="#fff"
                  fontWeight="700"
                >
                  {n.dorsal ?? ""}
                </text>
              </g>
            );
          })}
        </svg>
        {red.isSuccess && !nodos.length && (
          <p className="analisis-nota">
            No hay jugadores con identificador asignado a la vista en ese rango. Asigna los
            identificadores a jugadores del plantel para ver la red.
          </p>
        )}
        {red.isSuccess && !!nodos.length && (
          <div className="red-resumen">
            <section>
              <h4>
                <span className="red-leyenda red-leyenda--recepcion" aria-hidden="true" />
                Más pases reciben
              </h4>
              {masRecibidos.length ? (
                <ol>
                  {masRecibidos.map((n) => (
                    <li key={n.jugador_id}>
                      {etiqueta(n)}{" "}
                      <small>
                        {n.pases_recibidos} recibidos · {n.pases} enviados
                      </small>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="analisis-nota">Nadie recibió pases completados en este rango.</p>
              )}
            </section>
            <section>
              <h4>
                <span className="red-leyenda red-leyenda--aislado" aria-hidden="true" />
                Desconectados del circuito
              </h4>
              {aislados.length ? (
                <ul>
                  {aislados.map((n) => (
                    <li key={n.jugador_id}>
                      {etiqueta(n)}{" "}
                      <small>
                        {n.pases} enviados · {n.pases_recibidos} recibidos
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="analisis-nota">
                  Todos los jugadores a la vista participan del circuito.
                </p>
              )}
            </section>
          </div>
        )}
        <p className="analisis-nota">
          Cada nodo está en la posición media del jugador en el rango. Las flechas van de quien pasa
          a quien recibe; más gruesa = más pases completados en ese sentido. El tamaño del nodo
          crece con los pases que recibe; el anillo dorado marca a los que más reciben y el trazo
          punteado gris, a quienes casi no pasan ni reciben respecto al promedio del equipo. Solo
          cuentan los jugadores con identificador asignado.
        </p>
      </section>
    </div>
  );
}
