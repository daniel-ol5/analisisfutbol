import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { obtenerLineaTiempo } from "../api";
import {
  contarPorTipo,
  duracionEje,
  ETIQUETA_TIPO,
  filtrarItems,
  formatoTiempo,
  ICONO_TIPO,
  indiceActivo,
  TIPOS_CAMARA,
  TIPOS_INICIALES,
  TIPOS_MANUALES,
} from "../lineaTiempo";
import type { ItemLineaTiempo, LadoPartido, TipoEventoLinea } from "../types";
import { CronologiaHorizontal } from "./CronologiaHorizontal";

interface Props {
  partidoId: number;
  /** Instante actual del plano 2D (segundos), para resaltar el último evento ocurrido. */
  tiempoActual?: number | null;
  /** CU-47: al elegir un evento, el plano 2D salta a su instante y las métricas se filtran a su minuto. */
  onSeleccionar: (item: ItemLineaTiempo) => void;
  /** Minuto al que están filtradas las métricas (null: todo el partido). */
  minutoFiltro?: number | null;
  onQuitarFiltro?: () => void;
  nombreLocal?: string;
  nombreVisitante?: string;
}

export function LineaTiempoPartido({
  partidoId,
  tiempoActual,
  onSeleccionar,
  minutoFiltro = null,
  onQuitarFiltro,
  nombreLocal = "Local",
  nombreVisitante = "Visitante",
}: Props) {
  const [tipos, setTipos] = useState<Set<TipoEventoLinea>>(() => new Set(TIPOS_INICIALES));
  const [equipo, setEquipo] = useState<LadoPartido | null>(null);
  const [elegido, setElegido] = useState<number | null>(null);
  const consulta = useQuery({
    queryKey: ["linea-tiempo", partidoId],
    queryFn: () => obtenerLineaTiempo(partidoId),
    retry: false,
  });
  const todos = useMemo(() => consulta.data?.items ?? [], [consulta.data]);
  const cuenta = useMemo(() => contarPorTipo(todos), [todos]);
  const visibles = useMemo(() => filtrarItems(todos, tipos, equipo), [todos, tipos, equipo]);
  const duracion = useMemo(() => duracionEje(todos), [todos]);
  const activo = indiceActivo(visibles, tiempoActual);
  // Quitar el filtro desde el panel de métricas también suelta el evento elegido.
  const elegidoVigente = minutoFiltro === null ? null : elegido;
  const alternar = (tipo: TipoEventoLinea) => {
    setElegido(null);
    setTipos((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(tipo)) nuevo.delete(tipo);
      else nuevo.add(tipo);
      return nuevo;
    });
  };
  const nombre = (lado: LadoPartido | null) =>
    lado === "LOCAL" ? nombreLocal : lado === "VISITANTE" ? nombreVisitante : "";
  const elegir = (indice: number) => {
    setElegido(indice);
    onSeleccionar(visibles[indice]);
  };

  return (
    <section className="analisis-linea" aria-label="Línea de tiempo del partido">
      <div className="analisis-radar-cabecera">
        <h3>Línea de tiempo</h3>
        <span>
          {consulta.isPending ? "Cargando…" : `${visibles.length} de ${todos.length} eventos`}
        </span>
      </div>
      <div className="analisis-linea-filtros">
        <div role="group" aria-label="Tipos de evento">
          {[...TIPOS_CAMARA, ...TIPOS_MANUALES]
            .filter((t) => cuenta.has(t))
            .map((t) => (
              <button
                key={t}
                type="button"
                aria-pressed={tipos.has(t)}
                className={tipos.has(t) ? "activo" : ""}
                onClick={() => alternar(t)}
              >
                <span aria-hidden="true">{ICONO_TIPO[t]}</span> {ETIQUETA_TIPO[t]}{" "}
                <small>{cuenta.get(t)}</small>
              </button>
            ))}
        </div>
        <label>
          Equipo{" "}
          <select
            value={equipo ?? ""}
            onChange={(e) => {
              setElegido(null);
              setEquipo((e.target.value || null) as LadoPartido | null);
            }}
          >
            <option value="">Ambos</option>
            <option value="LOCAL">{nombreLocal}</option>
            <option value="VISITANTE">{nombreVisitante}</option>
          </select>
        </label>
      </div>
      {consulta.isError && <p role="alert">No se pudo cargar la línea de tiempo.</p>}
      {consulta.isSuccess && !todos.length && (
        <p className="analisis-nota">
          Sin eventos todavía: se llenan al procesar el video o al cargar eventos del partido.
        </p>
      )}
      {consulta.isSuccess && !!todos.length && !visibles.length && (
        <p className="analisis-nota">Ningún evento coincide con los filtros.</p>
      )}
      {consulta.isSuccess && !!todos.length && (
        <>
          <CronologiaHorizontal
            items={visibles}
            duracion={duracion}
            elegido={elegidoVigente}
            tiempoActual={tiempoActual}
            onElegir={elegir}
            nombreEquipo={nombre}
          />
          {minutoFiltro !== null && (
            <p className="analisis-linea-filtro" role="status">
              Plano 2D y métricas en el minuto {minutoFiltro}.{" "}
              {onQuitarFiltro && (
                <button type="button" onClick={onQuitarFiltro}>
                  Ver todo el partido
                </button>
              )}
            </p>
          )}
        </>
      )}
      <ol className="analisis-linea-lista">
        {visibles.map((i, n) => (
          <li key={`${i.t}-${i.tipo}-${i.equipo}-${n}`}>
            <button
              type="button"
              className={`${n === activo ? "actual" : ""} ${n === elegidoVigente ? "elegido" : ""}`}
              aria-label={`Ir al minuto ${formatoTiempo(i.t)}: ${i.descripcion}`}
              onClick={() => elegir(n)}
            >
              <time>{formatoTiempo(i.t)}</time>
              <span className={`analisis-evento analisis-evento--${i.tipo.toLowerCase()}`}>
                {ETIQUETA_TIPO[i.tipo]}
              </span>
              <span>
                {i.descripcion}
                {i.equipo && <small> · {nombre(i.equipo)}</small>}
              </span>
              <small className="analisis-origen">
                {i.origen === "CAMARA" ? "Cámara" : "Manual"}
              </small>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
