import type { MetricaEquipoMinuto, MetricasMinuto } from "../types";

const num = (v: number | null, decimales = 1) => (v == null ? "—" : v.toFixed(decimales));

interface Props {
  minuto: number;
  datos: MetricasMinuto | undefined;
  cargando: boolean;
  error: boolean;
  nombreLocal: string;
  nombreVisitante: string;
  onQuitar: () => void;
}

const FILAS: [string, (m: MetricaEquipoMinuto) => string][] = [
  ["Posesión (%)", (m) => num(m.posesion_pct)],
  ["Pases completados / intentados", (m) => `${m.pases_completados} / ${m.pases_intentados}`],
  ["Distancia recorrida (m)", (m) => num(m.distancia_m, 0)],
  ["Altura de línea (m)", (m) => num(m.altura_linea_m)],
  ["Ancho (m)", (m) => num(m.amplitud_m)],
  ["Compacidad (m²)", (m) => num(m.compacidad_m2, 0)],
];

/** CU-47 · Las métricas del minuto de la jugada elegida en la cronología. */
export function MetricasDelMinuto({
  minuto,
  datos,
  cargando,
  error,
  nombreLocal,
  nombreVisitante,
  onQuitar,
}: Props) {
  const sinDatos =
    datos !== undefined &&
    datos.local.altura_linea_m == null &&
    datos.visitante.altura_linea_m == null &&
    datos.local.posesion_pct + datos.visitante.posesion_pct + datos.posesion_disputa_pct === 0;
  return (
    <section className="analisis-minuto" aria-label={`Métricas del minuto ${minuto}`}>
      <div className="analisis-radar-cabecera">
        <h3>Métricas del minuto {minuto}</h3>
        <button type="button" className="analisis-minuto-quitar" onClick={onQuitar}>
          Ver todo el partido
        </button>
      </div>
      {cargando && <p className="analisis-nota">Calculando el minuto…</p>}
      {error && <p role="alert">No se pudieron cargar las métricas de ese minuto.</p>}
      {sinDatos && <p className="analisis-nota">No hay posiciones procesadas en ese minuto.</p>}
      {datos && !sinDatos && (
        <>
          <table className="analisis-tabla">
            <thead>
              <tr>
                <th>Métrica</th>
                <th>{nombreLocal}</th>
                <th>{nombreVisitante}</th>
              </tr>
            </thead>
            <tbody>
              {FILAS.map(([etiqueta, valor]) => (
                <tr key={etiqueta}>
                  <th scope="row">{etiqueta}</th>
                  <td>{valor(datos.local)}</td>
                  <td>{valor(datos.visitante)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="analisis-nota">
            Balón en disputa: {num(datos.posesion_disputa_pct)} % del minuto. Cada equipo se mide
            atacando hacia la derecha.
          </p>
        </>
      )}
    </section>
  );
}
