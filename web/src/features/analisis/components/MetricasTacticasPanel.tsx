import { useQuery } from "@tanstack/react-query";
import { obtenerMetricasTacticas } from "../api";
import type { BloqueFase, MetricaTactica } from "../types";
import { usePartidosAnalisis, usePartidoUrl } from "../hooks/usePartidosAnalisis";
import { SelectorPartido } from "./SelectorPartido";

const num = (v: number | null) => (v == null ? "—" : v.toFixed(1));
const FASES = [
  ["con_balon", "Con balón"],
  ["sin_balon", "Sin balón"],
  ["total", "Total"],
] as const;

function TablaEquipo({ nombre, m }: { nombre: string; m: MetricaTactica }) {
  const filas: [string, BloqueFase][] = FASES.map(([k, etiqueta]) => [etiqueta, m[k]]);
  return (
    <section>
      <h3>{nombre}</h3>
      <table className="analisis-tabla">
        <thead>
          <tr>
            <th>Fase</th>
            <th>Altura de línea (m)</th>
            <th>Ancho (m)</th>
            <th>Compacidad (m²)</th>
            <th>Segundos</th>
          </tr>
        </thead>
        <tbody>
          {filas.map(([etiqueta, f]) => (
            <tr key={etiqueta}>
              <th scope="row">{etiqueta}</th>
              <td>{num(f.altura_linea_m)}</td>
              <td>{num(f.amplitud_m)}</td>
              <td>{num(f.compacidad_m2)}</td>
              <td>{f.muestras}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** CU-45 · Altura de línea defensiva, amplitud y compacidad con y sin balón. */
export function MetricasTacticasPanel() {
  const { partidoId: seleccionado, elegir } = usePartidoUrl();
  const { id, nombreLocal, nombreVisitante } = usePartidosAnalisis(seleccionado);
  const consulta = useQuery({
    queryKey: ["metricas-tacticas", id],
    enabled: id !== null,
    retry: false,
    queryFn: () => obtenerMetricasTacticas(id as number),
  });
  const datos = consulta.data;
  const hayDatos = datos && datos.local.total.muestras + datos.visitante.total.muestras > 0;
  return (
    <div className="analisis-sesion">
      <div className="analisis-sesion-barra">
        <SelectorPartido valor={id} onCambiar={elegir} />
      </div>
      {consulta.isError && <p role="alert">No se pudieron cargar las métricas tácticas.</p>}
      {consulta.isSuccess && !hayDatos && (
        <p className="analisis-nota">Todavía no hay posiciones procesadas de este partido.</p>
      )}
      {datos && hayDatos && (
        <>
          <div className="analisis-resumen">
            <TablaEquipo nombre={nombreLocal} m={datos.local} />
            <TablaEquipo nombre={nombreVisitante} m={datos.visitante} />
          </div>
          {!!datos.intervalos.length && (
            <div className="analisis-resumen">
              <section style={{ gridColumn: "1 / -1" }}>
                <h3>
                  Altura de línea por intervalo de 5 minutos (con balón / sin balón, en metros)
                </h3>
                <table className="analisis-tabla">
                  <thead>
                    <tr>
                      <th>Minutos</th>
                      <th>{nombreLocal}</th>
                      <th>{nombreVisitante}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datos.intervalos.map((i) => (
                      <tr key={i.minuto_desde}>
                        <th scope="row">
                          {i.minuto_desde}–{i.minuto_hasta}
                        </th>
                        <td>
                          {num(i.local.con_balon.altura_linea_m)} /{" "}
                          {num(i.local.sin_balon.altura_linea_m)}
                        </td>
                        <td>
                          {num(i.visitante.con_balon.altura_linea_m)} /{" "}
                          {num(i.visitante.sin_balon.altura_linea_m)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>
          )}
          <p className="analisis-nota">
            Cada equipo se mide atacando hacia la derecha. Altura de línea: distancia al arco propio
            de la posición media de los 4 jugadores de campo más retrasados (el arquero no entra);
            más alto = línea más adelantada. Ancho: distancia entre los dos jugadores más abiertos.
            Compacidad: área del polígono que envuelve a los jugadores de campo; menos área = equipo
            más junto. Si la cámara pierde a un jugador unos segundos, se mantiene su última
            posición para que la línea no salte. En disputa o con el balón fuera de la imagen, el
            tiempo solo cuenta en «Total».
          </p>
        </>
      )}
    </div>
  );
}
