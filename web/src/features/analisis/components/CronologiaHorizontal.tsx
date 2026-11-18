import { useMemo } from "react";
import {
  asignarFilas,
  ETIQUETA_TIPO,
  formatoTiempo,
  ICONO_TIPO,
  marcasEje,
  MINUTOS_REGLAMENTARIOS,
  porcentajeEnEje,
} from "../lineaTiempo";
import type { ItemLineaTiempo, LadoPartido } from "../types";

const SEPARACION_PCT = 2.4;
const MAX_FILAS = 3;
const ALTO_FILA_PX = 28;
const ENCABEZADO_PX = 14; // franja superior del carril: ahí va su rótulo

interface Props {
  /** Eventos visibles, ordenados por `t`. */
  items: ItemLineaTiempo[];
  /** Largo del eje en minutos (90 o más si hay descuento). */
  duracion: number;
  /** Índice en `items` del evento elegido (el que filtra las métricas). */
  elegido: number | null;
  /** Instante actual del plano 2D (segundos): el cursor del eje. */
  tiempoActual?: number | null;
  onElegir: (indice: number) => void;
  nombreEquipo: (lado: LadoPartido | null) => string;
}

interface Marca {
  indice: number;
  item: ItemLineaTiempo;
  pct: number;
  fila: number;
}

const CARRILES = [
  { origen: "MANUAL", titulo: "Cuerpo técnico" },
  { origen: "CAMARA", titulo: "Cámara" },
] as const;

/**
 * CU-47 · Cronología horizontal del minuto 0 al 90+. Los eventos cargados a mano y los
 * detectados por la cámara van en carriles separados (origen MANUAL / CAMARA), con un
 * ícono por tipo; al elegir uno, el panel filtra métricas y plano 2D a esa jugada.
 */
export function CronologiaHorizontal({
  items,
  duracion,
  elegido,
  tiempoActual,
  onElegir,
  nombreEquipo,
}: Props) {
  const carriles = useMemo(
    () =>
      CARRILES.map((c) => {
        const delCarril = items
          .map((item, indice) => ({ item, indice }))
          .filter((e) => e.item.origen === c.origen);
        const pcts = delCarril.map((e) => porcentajeEnEje(e.item.t, duracion));
        const filas = asignarFilas(pcts, SEPARACION_PCT, MAX_FILAS);
        const marcas: Marca[] = delCarril.map((e, n) => ({ ...e, pct: pcts[n], fila: filas[n] }));
        return { ...c, marcas, nFilas: Math.max(1, ...filas.map((f) => f + 1)) };
      }),
    [items, duracion],
  );

  const marcas = useMemo(() => marcasEje(duracion), [duracion]);
  const elegida = elegido !== null ? items[elegido] : null;
  const minutoElegido = elegida ? Math.floor(elegida.t / 60) : null;

  return (
    <div className="cronologia" role="group" aria-label="Cronología horizontal del partido">
      <div className="cronologia-escala">
        <Carril
          carril={carriles[0]}
          elegido={elegido}
          onElegir={onElegir}
          nombreEquipo={nombreEquipo}
        />
        <div className="cronologia-eje" aria-hidden="true">
          {duracion > MINUTOS_REGLAMENTARIOS && (
            <span
              className="cronologia-descuento"
              style={{ left: `${porcentajeEnEje(MINUTOS_REGLAMENTARIOS * 60, duracion)}%` }}
            />
          )}
          {marcas.map((m) => (
            <span
              key={m.minuto}
              className="cronologia-tick"
              style={{ left: `${porcentajeEnEje(m.minuto * 60, duracion)}%` }}
            >
              <i />
              {m.etiqueta}
            </span>
          ))}
        </div>
        <Carril
          carril={carriles[1]}
          elegido={elegido}
          onElegir={onElegir}
          nombreEquipo={nombreEquipo}
        />
        {minutoElegido !== null && (
          <span
            className="cronologia-minuto"
            aria-hidden="true"
            style={{
              left: `${porcentajeEnEje(minutoElegido * 60, duracion)}%`,
              width: `${porcentajeEnEje(60, duracion)}%`,
            }}
          />
        )}
        {tiempoActual != null && (
          <span
            className="cronologia-cursor"
            aria-hidden="true"
            style={{ left: `${porcentajeEnEje(tiempoActual, duracion)}%` }}
          />
        )}
      </div>
    </div>
  );
}

function Carril({
  carril,
  elegido,
  onElegir,
  nombreEquipo,
}: {
  carril: { origen: string; titulo: string; marcas: Marca[]; nFilas: number };
  elegido: number | null;
  onElegir: (indice: number) => void;
  nombreEquipo: (lado: LadoPartido | null) => string;
}) {
  return (
    <div
      className={`cronologia-carril cronologia-carril--${carril.origen.toLowerCase()}`}
      style={{ height: carril.nFilas * ALTO_FILA_PX + ENCABEZADO_PX + 6 }}
    >
      <span className="cronologia-carril-titulo">{carril.titulo}</span>
      {carril.marcas.map(({ indice, item, pct, fila }) => {
        const equipo = item.equipo ? ` · ${nombreEquipo(item.equipo)}` : "";
        return (
          <button
            key={`${indice}-${item.t}-${item.tipo}`}
            type="button"
            className={`cronologia-marca cronologia-marca--${item.tipo.toLowerCase()} ${indice === elegido ? "elegido" : ""}`}
            data-equipo={item.equipo ?? ""}
            aria-pressed={indice === elegido}
            style={{ left: `${pct}%`, top: fila * ALTO_FILA_PX + ENCABEZADO_PX + 2 }}
            title={`${formatoTiempo(item.t)} · ${ETIQUETA_TIPO[item.tipo]}${equipo}\n${item.descripcion}`}
            aria-label={`Ir al minuto ${formatoTiempo(item.t)}: ${item.descripcion}`}
            onClick={() => onElegir(indice)}
          >
            <span aria-hidden="true">{ICONO_TIPO[item.tipo]}</span>
          </button>
        );
      })}
    </div>
  );
}
