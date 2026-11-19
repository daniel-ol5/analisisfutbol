/** CU-18 · Guía de montaje de cámara. Contenido estático: no llama a la API. */
import { Link } from "react-router-dom";

import "@/features/vision/guia.css";

import { EsquemaMontaje } from "../components/EsquemaMontaje";
import { ListaComprobacion } from "../components/ListaComprobacion";
import { AVISO_ESTADO_ADR, DATOS_RECOMENDADOS, REFERENCIA_TAMANOS } from "../guia";

export function GuiaMontajePage() {
  return (
    <section className="guia">
      <h2>Montaje de cámara</h2>

      {AVISO_ESTADO_ADR && (
        <p className="guia-aviso" role="note">
          {AVISO_ESTADO_ADR}
        </p>
      )}

      <section aria-labelledby="guia-datos">
        <h2 id="guia-datos">1. Datos recomendados</h2>
        <dl className="guia-datos">
          {DATOS_RECOMENDADOS.map((dato) => (
            <div key={dato.id} className="guia-dato">
              <dt>{dato.etiqueta}</dt>
              <dd>
                {dato.valor === null ? (
                  <span className="guia-por-definir">Por definir</span>
                ) : (
                  dato.valor
                )}
                {dato.detalle && <span className="guia-detalle">{dato.detalle}</span>}
              </dd>
            </div>
          ))}
        </dl>

        <h3>Qué tamaño tendrán las personas en la imagen</h3>
        <p className="guia-texto-suave">
          Con la cámara a 1080p y toda la cancha en cuadro, esto es lo que ocupan en la imagen (un
          píxel es cada punto de la imagen). Es el límite de lo detectable.
        </p>
        <ul className="guia-tamanos">
          {REFERENCIA_TAMANOS.map((ref) => (
            <li key={ref.objeto}>
              <strong>{ref.objeto}:</strong> de {ref.minPx} a {ref.maxPx} píxeles
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="guia-esquema">
        <h2 id="guia-esquema">2. Cómo debe quedar</h2>
        <EsquemaMontaje />
      </section>

      <section aria-labelledby="guia-lista">
        <h2 id="guia-lista">3. Lista de comprobación antes de calibrar</h2>
        <ListaComprobacion />
      </section>

      <section aria-labelledby="guia-siguiente">
        <h2 id="guia-siguiente">4. Siguiente paso</h2>
        <Link to="/vision/calibracion" className="guia-boton" aria-describedby="guia-calibrar-nota">
          Ir a calibrar
        </Link>
        <p id="guia-calibrar-nota" className="guia-texto-suave">
          Configura la fuente de video y toma una referencia de la cancha.
        </p>
      </section>
    </section>
  );
}
