/**
 * Cancha del editor de alineación  —  CU-17 · T-051 (HU-14 · Criterios 1 y 2).
 *
 * Horizontal: arco propio a la izquierda, arco rival a la derecha. `pos_x`
 * (largo) crece hacia la derecha y `pos_y` (ancho) hacia abajo, que es la
 * banda derecha mirando al arco rival. Son los mismos ejes del tracking.
 *
 * Las fichas se arrastran con el mouse o el dedo, y con el teclado: flechas
 * mueven 1 %, Mayús + flechas 5 %.
 */
import { useRef, type KeyboardEvent, type PointerEvent } from "react";

import { PUESTOS, type EstadoAlineacion } from "../alineacion";
import { ETIQUETAS_POSICION, type Jugador } from "../types";

interface Props {
  estado: EstadoAlineacion;
  plantel: ReadonlyMap<number, Jugador>;
  editable: boolean;
  onMover: (jugadorId: number, x: number, y: number) => void;
}

export function CanchaTactica({ estado, plantel, editable, onMover }: Props) {
  const cancha = useRef<HTMLDivElement>(null);
  const arrastrando = useRef<number | null>(null);
  const puestos = PUESTOS[estado.formacion];

  const puntoEnCancha = (e: PointerEvent): { x: number; y: number } | null => {
    const caja = cancha.current?.getBoundingClientRect();
    if (!caja) return null;
    return {
      x: ((e.clientX - caja.left) / caja.width) * 100,
      y: ((e.clientY - caja.top) / caja.height) * 100,
    };
  };

  const alPresionar = (e: PointerEvent<HTMLButtonElement>, jugadorId: number) => {
    if (!editable) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    arrastrando.current = jugadorId;
  };

  const alMover = (e: PointerEvent<HTMLButtonElement>) => {
    if (arrastrando.current === null) return;
    const p = puntoEnCancha(e);
    if (p) onMover(arrastrando.current, p.x, p.y);
  };

  const alSoltar = () => {
    arrastrando.current = null;
  };

  const alTeclear = (
    e: KeyboardEvent<HTMLButtonElement>,
    jugadorId: number,
    x: number,
    y: number,
  ) => {
    if (!editable) return;
    const paso = e.shiftKey ? 5 : 1;
    const delta: Record<string, [number, number]> = {
      ArrowRight: [paso, 0],
      ArrowLeft: [-paso, 0],
      ArrowDown: [0, paso],
      ArrowUp: [0, -paso],
    };
    const d = delta[e.key];
    if (!d) return;
    e.preventDefault();
    onMover(jugadorId, x + d[0], y + d[1]);
  };

  return (
    <div className="alin-cancha" ref={cancha} aria-label={`Cancha, formación ${estado.formacion}`}>
      <LineasCancha />
      <span className="alin-cancha-sentido" aria-hidden="true">
        Ataque →
      </span>

      {/* Puestos libres: guía de dónde falta un titular */}
      {estado.titulares.map((t, i) =>
        t === null ? (
          <span
            key={`libre-${i}`}
            className="alin-puesto-libre"
            style={{ left: `${puestos[i].x}%`, top: `${puestos[i].y}%` }}
            title={`Puesto libre: ${ETIQUETAS_POSICION[puestos[i].rol]}`}
          >
            {puestos[i].rol}
          </span>
        ) : null,
      )}

      {estado.titulares.map((t) => {
        if (t === null) return null;
        const j = plantel.get(t.jugadorId);
        if (!j) return null;
        const capitan = estado.capitanId === j.id;
        const arquero = j.posicion === "ARQ";
        return (
          <button
            key={j.id}
            type="button"
            className={[
              "alin-ficha",
              arquero ? "alin-ficha--arquero" : "",
              editable ? "alin-ficha--movible" : "",
            ].join(" ")}
            style={{ left: `${t.x}%`, top: `${t.y}%` }}
            aria-label={
              `${j.dorsal}, ${j.nombre} ${j.apellido}, ${ETIQUETAS_POSICION[j.posicion]}` +
              `${capitan ? ", capitán" : ""}. Largo ${Math.round(t.x)} %, ancho ${Math.round(t.y)} %` +
              (editable ? ". Muévelo con las flechas." : "")
            }
            onPointerDown={(e) => alPresionar(e, j.id)}
            onPointerMove={alMover}
            onPointerUp={alSoltar}
            onPointerCancel={alSoltar}
            onKeyDown={(e) => alTeclear(e, j.id, t.x, t.y)}
          >
            <span className="alin-ficha-dorsal">
              {j.dorsal}
              {capitan && <span className="alin-ficha-capitan">C</span>}
            </span>
            <span className="alin-ficha-nombre">{j.apellido}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Líneas reglamentarias en proporción 105 × 68 m. */
function LineasCancha() {
  return (
    <svg
      className="alin-cancha-lineas"
      viewBox="0 0 105 68"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <g fill="none" stroke="currentColor" strokeWidth="0.4">
        <rect x="0.5" y="0.5" width="104" height="67" />
        <line x1="52.5" y1="0.5" x2="52.5" y2="67.5" />
        <circle cx="52.5" cy="34" r="9.15" />
        <rect x="0.5" y="13.85" width="16.5" height="40.3" />
        <rect x="88" y="13.85" width="16.5" height="40.3" />
        <rect x="0.5" y="24.85" width="5.5" height="18.3" />
        <rect x="99" y="24.85" width="5.5" height="18.3" />
      </g>
      <g fill="currentColor">
        <circle cx="52.5" cy="34" r="0.5" />
        <circle cx="11" cy="34" r="0.5" />
        <circle cx="94" cy="34" r="0.5" />
      </g>
    </svg>
  );
}
