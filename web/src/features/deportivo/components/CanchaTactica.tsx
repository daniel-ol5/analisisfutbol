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
import {
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import {
  PUESTOS,
  puestoCercanoEnCancha,
  type EstadoAlineacion,
} from "../alineacion";
import { ETIQUETAS_POSICION, type Jugador } from "../types";

export const MIME_JUGADOR_ALINEACION = "application/x-jugador-alineacion";

interface Props {
  estado: EstadoAlineacion;
  plantel: ReadonlyMap<number, Jugador>;
  editable: boolean;
  puestoSeleccionado?: number | null;
  onSeleccionarPuesto?: (indice: number | null) => void;
  onMover: (jugadorId: number, x: number, y: number) => void;
  onSoltarJugador?: (jugadorId: number, x: number, y: number) => void;
  onColocarEnPuesto?: (jugadorId: number, indicePuesto: number) => void;
}

export function CanchaTactica({
  estado,
  plantel,
  editable,
  puestoSeleccionado = null,
  onSeleccionarPuesto,
  onMover,
  onSoltarJugador,
  onColocarEnPuesto,
}: Props) {
  const cancha = useRef<HTMLDivElement>(null);
  const arrastrando = useRef<number | null>(null);
  const [puestoHover, setPuestoHover] = useState<number | null>(null);
  const puestos = PUESTOS[estado.formacion];

  const coordsRelativas = (clientX: number, clientY: number): { x: number; y: number } | null => {
    const caja = cancha.current?.getBoundingClientRect();
    if (!caja || caja.width <= 0 || caja.height <= 0) return null;
    return {
      x: ((clientX - caja.left) / caja.width) * 100,
      y: ((clientY - caja.top) / caja.height) * 100,
    };
  };

  const puntoEnCancha = (e: PointerEvent): { x: number; y: number } | null =>
    coordsRelativas(e.clientX, e.clientY);

  const alPresionar = (e: PointerEvent<HTMLButtonElement>, jugadorId: number) => {
    if (!editable) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    arrastrando.current = jugadorId;
  };

  const alMover = (e: PointerEvent<HTMLButtonElement>) => {
    if (arrastrando.current === null) return;
    const p = puntoEnCancha(e);
    if (p) {
      onMover(arrastrando.current, p.x, p.y);
      const cercano = puestoCercanoEnCancha(estado, p.x, p.y, 8);
      setPuestoHover(cercano);
    }
  };

  const alSoltar = (e: PointerEvent<HTMLButtonElement>) => {
    const jugadorId = arrastrando.current;
    arrastrando.current = null;
    setPuestoHover(null);
    if (jugadorId === null || !onColocarEnPuesto) return;
    const p = puntoEnCancha(e);
    if (!p) return;
    const origenIndice = estado.titulares.findIndex((t) => t?.jugadorId === jugadorId);
    // Buscamos si soltó sobre otro puesto (libre u ocupado distinto del propio)
    for (let i = 0; i < puestos.length; i++) {
      if (i === origenIndice) continue;
      const titularDestino = estado.titulares[i];
      const refX = titularDestino ? titularDestino.x : puestos[i].x;
      const refY = titularDestino ? titularDestino.y : puestos[i].y;
      const d2 = (refX - p.x) ** 2 + (refY - p.y) ** 2;
      if (d2 <= 64) {
        onColocarEnPuesto(jugadorId, i);
        break;
      }
    }
  };

  const cancelarArrastrePuntero = () => {
    arrastrando.current = null;
    setPuestoHover(null);
  };

  const alDragOverCancha = (e: DragEvent<HTMLDivElement>) => {
    if (!editable) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const p = coordsRelativas(e.clientX, e.clientY);
    if (!p) return;
    setPuestoHover(puestoCercanoEnCancha(estado, p.x, p.y, 9));
  };

  const alDragLeaveCancha = (e: DragEvent<HTMLDivElement>) => {
    if (!cancha.current?.contains(e.relatedTarget as Node | null)) {
      setPuestoHover(null);
    }
  };

  const alDropCancha = (e: DragEvent<HTMLDivElement>) => {
    if (!editable) return;
    e.preventDefault();
    setPuestoHover(null);
    const raw =
      e.dataTransfer.getData(MIME_JUGADOR_ALINEACION) || e.dataTransfer.getData("text/plain");
    const jugadorId = Number(raw);
    if (!Number.isInteger(jugadorId) || jugadorId <= 0) return;

    const p = coordsRelativas(e.clientX, e.clientY);
    if (!p) return;
    if (onSoltarJugador) {
      onSoltarJugador(jugadorId, p.x, p.y);
    }
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
    <div
      className="alin-cancha"
      ref={cancha}
      aria-label={`Cancha, formación ${estado.formacion}`}
      onDragOver={alDragOverCancha}
      onDragLeave={alDragLeaveCancha}
      onDrop={alDropCancha}
    >
      <LineasCancha />
      <span className="alin-cancha-sentido" aria-hidden="true">
        Ataque
      </span>

      {/* Puestos libres: guía de dónde falta un titular (clicables y destino de arrastre) */}
      {estado.titulares.map((t, i) => {
        if (t !== null) return null;
        const seleccionado = puestoSeleccionado === i;
        const hover = puestoHover === i;
        return (
          <button
            key={`libre-${i}`}
            type="button"
            disabled={!editable}
            onClick={() => onSeleccionarPuesto?.(seleccionado ? null : i)}
            className={[
              "alin-puesto-libre",
              editable ? "alin-puesto-libre--interactivo" : "",
              seleccionado ? "alin-puesto-libre--seleccionado" : "",
              hover ? "alin-puesto-libre--hover" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ left: `${puestos[i].x}%`, top: `${puestos[i].y}%` }}
            title={
              editable
                ? `Puesto ${ETIQUETAS_POSICION[puestos[i].rol]}: arrastra un jugador aquí o haz clic para elegir este puesto`
                : `Puesto libre: ${ETIQUETAS_POSICION[puestos[i].rol]}`
            }
          >
            {puestos[i].rol}
          </button>
        );
      })}

      {estado.titulares.map((t, i) => {
        if (t === null) return null;
        const j = plantel.get(t.jugadorId);
        if (!j) return null;
        const capitan = estado.capitanId === j.id;
        const arquero = j.posicion === "ARQ";
        const hover = puestoHover === i && arrastrando.current !== j.id;
        return (
          <button
            key={j.id}
            type="button"
            className={[
              "alin-ficha",
              arquero ? "alin-ficha--arquero" : "",
              editable ? "alin-ficha--movible" : "",
              hover ? "alin-ficha--hover" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ left: `${t.x}%`, top: `${t.y}%` }}
            aria-label={
              `${j.dorsal}, ${j.nombre} ${j.apellido}, ${ETIQUETAS_POSICION[j.posicion]}` +
              `${capitan ? ", capitán" : ""}. Largo ${Math.round(t.x)} %, ancho ${Math.round(t.y)} %` +
              (editable ? ". Muévelo con las flechas o arrastrando." : "")
            }
            onPointerDown={(e) => alPresionar(e, j.id)}
            onPointerMove={alMover}
            onPointerUp={alSoltar}
            onPointerCancel={cancelarArrastrePuntero}
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
