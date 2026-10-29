/**
 * Plano cenital interactivo de la cancha en metros (CU-19, CU-20).
 *
 * Respeta `largoM` y `anchoM` editables. El origen `(0, 0)` se ubica en la
 * esquina inferior izquierda del lado de la cámara (tribuna). En SVG el eje Y
 * crece hacia abajo, por lo que cada coordenada `y` en metros se dibuja en
 * `anchoM - y`.
 */
import { useRef, type MouseEvent as ReactMouseEvent } from "react";

import {
  ANCHO_CANCHA_DEFECTO_M,
  LARGO_CANCHA_DEFECTO_M,
  acotar,
  medidasAreaGrande,
  redondear2,
} from "../calibracion";
import type { HitoCancha, ParCalibracion, Punto } from "../types";

export interface PlanoCanchaProps {
  largoM: number;
  anchoM: number;
  plantilla: readonly HitoCancha[];
  hitoActivoId: string | null;
  modoLibre: boolean;
  puntoLibrePendiente: Punto | null;
  pares: readonly ParCalibracion[];
  parSeleccionadoId: string | null;
  /** Punto de extensión para T-031 (`ErrorCalibracion.punto_peor`, base 0). */
  indicePeor?: number | null;
  onSeleccionarHito: (hitoId: string) => void;
  onSeleccionarPar: (parId: string) => void;
  onElegirPuntoLibre: (puntoMetros: Punto) => void;
}

export function PlanoCancha({
  largoM,
  anchoM,
  plantilla,
  hitoActivoId,
  modoLibre,
  puntoLibrePendiente,
  pares,
  parSeleccionadoId,
  indicePeor = null,
  onSeleccionarHito,
  onSeleccionarPar,
  onElegirPuntoLibre,
}: PlanoCanchaProps) {
  const rectCanchaRef = useRef<SVGRectElement | null>(null);

  const L =
    Number.isFinite(largoM) && largoM > 20 && largoM < 200 ? largoM : LARGO_CANCHA_DEFECTO_M;
  const W =
    Number.isFinite(anchoM) && anchoM > 15 && anchoM < 150 ? anchoM : ANCHO_CANCHA_DEFECTO_M;

  const { profM, anchoAreaM, yInfM } = medidasAreaGrande(L, W);
  const radioCirculoCentral = redondear2(Math.min(9.15, W * 0.18));

  const margenX = 10;
  const margenSup = 8;
  const margenInf = 12;
  const viewBoxW = L + margenX * 2;
  const viewBoxH = W + margenSup + margenInf;

  // En SVG (0, 0) del campo se traslada por (margenX, margenSup) y el eje Y se invierte: ySvg = W - yMetros.
  const aSvgX = (xM: number) => margenX + xM;
  const aSvgY = (yM: number) => margenSup + (W - yM);

  const paresPorHito = new Map<string, { par: ParCalibracion; indice: number }>();
  pares.forEach((par, idx) => {
    if (par.hitoId !== null) {
      paresPorHito.set(par.hitoId, { par, indice: idx });
    }
  });

  function alHacerClicEnCampo(e: ReactMouseEvent<SVGSVGElement>) {
    if (!modoLibre) return;
    const rectEl = rectCanchaRef.current;
    if (!rectEl) return;
    const rect = rectEl.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const relX = (e.clientX - rect.left) / rect.width;
    const relY = (e.clientY - rect.top) / rect.height;
    const xM = redondear2(acotar(relX * L, 0, L));
    const yM = redondear2(acotar((1 - relY) * W, 0, W));
    onElegirPuntoLibre({ x: xM, y: yM });
  }

  return (
    <div className="cal-panel">
      <div className="cal-panel-cabecera">
        <div>
          <h2 className="cal-panel-titulo">
            2. Plano de la cancha ({L} × {W} m)
          </h2>
          <p className="cal-panel-subtitulo">
            {modoLibre
              ? "Modo libre activo: haz clic en cualquier punto del plano para fijar los metros."
              : "El punto resaltado indica qué marca de la cancha estás ubicando en la imagen."}
          </p>
        </div>
      </div>

      <div className="cal-plano-marco">
        <div className="cal-plano-rotulo-sup">Banda opuesta (Y = {W} m)</div>
        <svg
          className={`cal-plano-svg ${modoLibre ? "es-modo-libre" : ""}`}
          viewBox={`0 0 ${viewBoxW} ${viewBoxH}`}
          role="img"
          aria-label={`Plano cenital de la cancha de ${L} por ${W} metros`}
          onClick={alHacerClicEnCampo}
        >
          {/* Césped / Contorno exterior */}
          <rect
            ref={rectCanchaRef}
            x={aSvgX(0)}
            y={aSvgY(W)}
            width={L}
            height={W}
            className="cal-cancha-fondo"
          />

          {/* Línea de mediocampo y círculo central */}
          <line
            x1={aSvgX(L / 2)}
            y1={aSvgY(0)}
            x2={aSvgX(L / 2)}
            y2={aSvgY(W)}
            className="cal-cancha-linea"
          />
          <circle
            cx={aSvgX(L / 2)}
            cy={aSvgY(W / 2)}
            r={radioCirculoCentral}
            className="cal-cancha-linea"
          />

          {/* Área grande izquierda */}
          <rect
            x={aSvgX(0)}
            y={aSvgY(yInfM + anchoAreaM)}
            width={profM}
            height={anchoAreaM}
            className="cal-cancha-linea"
          />

          {/* Área grande derecha */}
          <rect
            x={aSvgX(L - profM)}
            y={aSvgY(yInfM + anchoAreaM)}
            width={profM}
            height={anchoAreaM}
            className="cal-cancha-linea"
          />

          {/* Cota de origen (0,0) en esquina inferior izquierda */}
          <text x={aSvgX(0)} y={aSvgY(0) + 5.2} textAnchor="start" className="cal-cancha-cota">
            (0, 0)
          </text>
          <text x={aSvgX(L)} y={aSvgY(0) + 5.2} textAnchor="end" className="cal-cancha-cota">
            ({L}, 0)
          </text>
          <text x={aSvgX(0)} y={aSvgY(W) - 2.2} textAnchor="start" className="cal-cancha-cota">
            (0, {W})
          </text>
          <text x={aSvgX(L)} y={aSvgY(W) - 2.2} textAnchor="end" className="cal-cancha-cota">
            ({L}, {W})
          </text>

          {/* Hitos de la plantilla que AÚN NO están marcados */}
          {plantilla.map((hito) => {
            if (paresPorHito.has(hito.id)) return null;
            const esActivo = !modoLibre && hito.id === hitoActivoId;
            const cx = aSvgX(hito.x);
            const cy = aSvgY(hito.y);
            return (
              <g
                key={hito.id}
                className={`cal-hito ${esActivo ? "es-activo" : ""}`}
                transform={`translate(${cx}, ${cy})`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSeleccionarHito(hito.id);
                }}
              >
                <title>{`${hito.nombre} (${hito.x} m, ${hito.y} m) — Clic para elegir este punto`}</title>
                {esActivo && <circle r={3.8} className="cal-hito-pulso" />}
                <circle r={esActivo ? 2.3 : 1.6} className="cal-hito-punto" />
              </g>
            );
          })}

          {/* Punto libre pendiente de clic en imagen */}
          {modoLibre && puntoLibrePendiente && (
            <g
              className="cal-hito es-activo"
              transform={`translate(${aSvgX(puntoLibrePendiente.x)}, ${aSvgY(puntoLibrePendiente.y)})`}
            >
              <circle r={3.8} className="cal-hito-pulso" />
              <circle r={2.3} className="cal-hito-punto" />
            </g>
          )}

          {/* Pares ya marcados sobre la cancha */}
          {pares.map((par, idx) => {
            const seleccionado = par.id === parSeleccionadoId;
            const esPeor = indicePeor === idx;
            const cx = aSvgX(par.cancha.x);
            const cy = aSvgY(par.cancha.y);
            return (
              <g
                key={par.id}
                className={`cal-marcador-cancha ${seleccionado ? "es-seleccionado" : ""} ${
                  esPeor ? "es-peor" : ""
                }`}
                transform={`translate(${cx}, ${cy})`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSeleccionarPar(par.id);
                }}
              >
                <title>{`#${idx + 1} ${par.etiqueta} (${par.cancha.x} m, ${par.cancha.y} m)`}</title>
                <circle r={seleccionado ? 3.2 : 2.6} className="cal-marcador-cancha-circulo" />
                <text y={0.9} textAnchor="middle" className="cal-marcador-cancha-texto">
                  {idx + 1}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="cal-plano-rotulo-inf">
          ▲ Lado de la cámara (tribuna) · Origen (0, 0) en la esquina inferior izquierda
        </div>
      </div>

      <p className="cal-ayuda-pie">
        Haz clic en cualquier hito vacío del plano si prefieres marcar las referencias en otro
        orden.
      </p>
    </div>
  );
}
