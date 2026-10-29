/**
 * Visor del cuadro congelado de la cámara (CU-19).
 *
 * Superpone un `<svg viewBox="0 0 {naturalWidth} {naturalHeight}">` sobre la
 * imagen original para que las marcas sigan siendo exactas aunque cambie el
 * tamaño de la ventana. Usa Pointer Events con `setPointerCapture` y distingue
 * entre hacer clic (crear punto) y arrastrar un marcador existente (corregir).
 */
import { useRef, type PointerEvent as ReactPointerEvent } from "react";

import { clienteAPixelesImagen } from "../calibracion";
import type { ParCalibracion, Punto } from "../types";

const UMBRAL_ARRASTRE_PX = 4;

interface EstadoPuntero {
  tipo: "fondo" | "marcador";
  pointerId: number;
  parId: string | null;
  inicioClienteX: number;
  inicioClienteY: number;
  movido: boolean;
}

export interface VisorCuadroProps {
  imagenUrl: string | null;
  nombreArchivo: string | null;
  dimensiones: { ancho: number; alto: number } | null;
  pares: readonly ParCalibracion[];
  parSeleccionadoId: string | null;
  etiquetaDestinoActual: string;
  /**
   * Punto de extensión para T-031: índice base 0 sobre `pares` del punto con
   * mayor error de reproyección (`ErrorCalibracion.punto_peor`).
   */
  indicePeor?: number | null;
  onCargarDimensiones: (ancho: number, alto: number) => void;
  onClicNuevoPunto: (puntoPx: Punto) => void;
  onSeleccionarPar: (parId: string) => void;
  onInicioArrastreMarcador: (parId: string) => void;
  onMoverMarcador: (parId: string, puntoPx: Punto) => void;
}

export function VisorCuadro({
  imagenUrl,
  nombreArchivo,
  dimensiones,
  pares,
  parSeleccionadoId,
  etiquetaDestinoActual,
  indicePeor = null,
  onCargarDimensiones,
  onClicNuevoPunto,
  onSeleccionarPar,
  onInicioArrastreMarcador,
  onMoverMarcador,
}: VisorCuadroProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const punteroRef = useRef<EstadoPuntero | null>(null);

  function calcularPunto(clientX: number, clientY: number): Punto | null {
    const svg = svgRef.current;
    if (!svg || !dimensiones) return null;
    const rect = svg.getBoundingClientRect();
    return clienteAPixelesImagen(clientX, clientY, rect, dimensiones.ancho, dimensiones.alto);
  }

  function alBajarEnFondo(e: ReactPointerEvent<SVGSVGElement>) {
    if (e.button !== 0 || !dimensiones) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    punteroRef.current = {
      tipo: "fondo",
      pointerId: e.pointerId,
      parId: null,
      inicioClienteX: e.clientX,
      inicioClienteY: e.clientY,
      movido: false,
    };
  }

  function alBajarEnMarcador(e: ReactPointerEvent<SVGGElement>, parId: string) {
    if (e.button !== 0 || !dimensiones) return;
    e.stopPropagation();
    const svg = svgRef.current;
    if (svg) {
      svg.setPointerCapture(e.pointerId);
    }
    onSeleccionarPar(parId);
    punteroRef.current = {
      tipo: "marcador",
      pointerId: e.pointerId,
      parId,
      inicioClienteX: e.clientX,
      inicioClienteY: e.clientY,
      movido: false,
    };
  }

  function alMoverPuntero(e: ReactPointerEvent<SVGSVGElement>) {
    const estado = punteroRef.current;
    if (!estado || estado.pointerId !== e.pointerId) return;

    const dist = Math.hypot(e.clientX - estado.inicioClienteX, e.clientY - estado.inicioClienteY);
    if (!estado.movido && dist >= UMBRAL_ARRASTRE_PX) {
      estado.movido = true;
      if (estado.tipo === "marcador" && estado.parId !== null) {
        onInicioArrastreMarcador(estado.parId);
      }
    }

    if (estado.tipo === "marcador" && estado.parId !== null && estado.movido) {
      const punto = calcularPunto(e.clientX, e.clientY);
      if (punto) {
        onMoverMarcador(estado.parId, punto);
      }
    }
  }

  function alSoltarPuntero(e: ReactPointerEvent<SVGSVGElement>) {
    const estado = punteroRef.current;
    if (!estado || estado.pointerId !== e.pointerId) return;

    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }

    if (estado.tipo === "fondo" && !estado.movido) {
      const punto = calcularPunto(e.clientX, e.clientY);
      if (punto) {
        onClicNuevoPunto(punto);
      }
    }

    punteroRef.current = null;
  }

  function alCancelarPuntero(e: ReactPointerEvent<SVGSVGElement>) {
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    punteroRef.current = null;
  }

  // Escala visual del marcador en unidades del viewBox para que sea legible en 720p, 1080p o 4K.
  const radioBase = dimensiones ? Math.max(12, Math.round(dimensiones.ancho * 0.011)) : 16;
  const tamFuente = Math.max(11, Math.round(radioBase * 0.95));

  return (
    <div className="cal-panel">
      <div className="cal-panel-cabecera">
        <div>
          <h2 className="cal-panel-titulo">1. Cuadro de la cámara</h2>
          <p className="cal-panel-subtitulo">
            {dimensiones
              ? `${nombreArchivo ?? "Imagen cargada"} · ${dimensiones.ancho} × ${dimensiones.alto} px`
              : "Carga un fotograma congelado del partido (no se sube al servidor)."}
          </p>
        </div>
      </div>

      {!imagenUrl ? (
        <div className="cal-visor-vacio">
          <p>Selecciona una imagen del campo tomada desde la cámara fija.</p>
          <p className="cal-texto-suave">
            Cada clic se convierte a los píxeles reales de la imagen original, sin importar el
            tamaño de tu pantalla.
          </p>
        </div>
      ) : (
        <>
          <div className="cal-instruccion-clic" role="status" aria-live="polite">
            <span>Siguiente marca en imagen:</span> <strong>{etiquetaDestinoActual}</strong>
          </div>

          <div className="cal-visor-marco">
            <img
              src={imagenUrl}
              alt="Cuadro congelado de la cancha para calibración"
              className="cal-visor-img"
              draggable={false}
              onLoad={(e) => {
                const img = e.currentTarget;
                onCargarDimensiones(img.naturalWidth, img.naturalHeight);
              }}
            />
            {dimensiones && (
              <svg
                ref={svgRef}
                className="cal-visor-svg"
                viewBox={`0 0 ${dimensiones.ancho} ${dimensiones.alto}`}
                preserveAspectRatio="none"
                role="application"
                aria-label="Lienzo de marcado de puntos sobre el cuadro de cámara"
                onPointerDown={alBajarEnFondo}
                onPointerMove={alMoverPuntero}
                onPointerUp={alSoltarPuntero}
                onPointerCancel={alCancelarPuntero}
              >
                {pares.map((par, idx) => {
                  const seleccionado = par.id === parSeleccionadoId;
                  const esPeor = indicePeor === idx;
                  const r = seleccionado ? radioBase * 1.2 : radioBase;
                  return (
                    <g
                      key={par.id}
                      className={`cal-marcador ${seleccionado ? "es-seleccionado" : ""} ${
                        esPeor ? "es-peor" : ""
                      }`}
                      transform={`translate(${par.imagen.x}, ${par.imagen.y})`}
                      onPointerDown={(e) => alBajarEnMarcador(e, par.id)}
                    >
                      <title>{`#${idx + 1} ${par.etiqueta} (${par.imagen.x} px, ${par.imagen.y} px) — Arrastra para corregir`}</title>
                      <circle r={r * 1.45} className="cal-marcador-halo" />
                      <circle
                        r={r}
                        className="cal-marcador-circulo"
                        strokeWidth={radioBase * 0.18}
                      />
                      <line
                        x1={-r * 0.45}
                        y1={0}
                        x2={r * 0.45}
                        y2={0}
                        className="cal-marcador-cruz"
                        strokeWidth={Math.max(1.5, radioBase * 0.1)}
                      />
                      <line
                        x1={0}
                        y1={-r * 0.45}
                        x2={0}
                        y2={r * 0.45}
                        className="cal-marcador-cruz"
                        strokeWidth={Math.max(1.5, radioBase * 0.1)}
                      />
                      <text
                        y={-r - Math.max(4, radioBase * 0.35)}
                        textAnchor="middle"
                        fontSize={tamFuente}
                        className="cal-marcador-numero"
                      >
                        {idx + 1}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
          <p className="cal-ayuda-pie">
            Haz clic en la imagen para situar el punto activo. Arrastra cualquier marcador numerado
            para corregirlo o ajústalo con las flechas del teclado.
          </p>
        </>
      )}
    </div>
  );
}
