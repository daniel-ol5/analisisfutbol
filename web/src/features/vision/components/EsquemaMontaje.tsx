import { ALTURA_M } from "../guia";

/**
 * Esquemas del montaje, en SVG inline (sin imágenes externas):
 *  1. Vista desde arriba: la cancha y la cámara en la tribuna, a la altura del mediocampo.
 *  2. Vista lateral: la altura de la cámara.
 * Son ilustrativos y no están a escala.
 */
export function EsquemaMontaje() {
  return (
    <div className="guia-esquemas">
      <figure className="guia-figura">
        <svg
          viewBox="0 0 400 300"
          role="img"
          aria-labelledby="guia-arriba-titulo guia-arriba-desc"
          className="guia-svg"
        >
          <title id="guia-arriba-titulo">Vista desde arriba</title>
          <desc id="guia-arriba-desc">
            La cancha vista desde arriba. Debajo, la tribuna principal con la cámara en el centro, a
            la altura de la línea de mediocampo. Dos líneas punteadas muestran lo que ve la cámara.
          </desc>

          {/* Cancha */}
          <rect x="40" y="20" width="320" height="207" className="guia-campo" />
          <line x1="200" y1="20" x2="200" y2="227" className="guia-campo" />
          <circle cx="200" cy="123" r="26" className="guia-campo" />
          <rect x="40" y="62" width="52" height="123" className="guia-campo" />
          <rect x="308" y="62" width="52" height="123" className="guia-campo" />

          {/* Campo de visión */}
          <line x1="200" y1="252" x2="40" y2="20" className="guia-vision" />
          <line x1="200" y1="252" x2="360" y2="20" className="guia-vision" />

          {/* Tribuna y cámara */}
          <rect x="40" y="238" width="320" height="28" className="guia-tribuna" />
          <circle cx="200" cy="252" r="8" className="guia-camara" />

          <text x="200" y="14" textAnchor="middle" className="guia-texto">
            Línea de mediocampo
          </text>
          <text x="120" y="258" textAnchor="middle" className="guia-texto">
            Tribuna principal
          </text>
          <text x="200" y="288" textAnchor="middle" className="guia-texto">
            Cámara en el centro de la tribuna
          </text>
        </svg>
        <figcaption>Vista desde arriba. Esquema ilustrativo, sin escala.</figcaption>
      </figure>

      <figure className="guia-figura">
        <svg
          viewBox="0 0 400 200"
          role="img"
          aria-labelledby="guia-lado-titulo guia-lado-desc"
          className="guia-svg"
        >
          <title id="guia-lado-titulo">Vista lateral</title>
          <desc id="guia-lado-desc">
            La cámara montada en la tribuna a {ALTURA_M} metros de altura, mirando hacia la cancha.
          </desc>

          {/* Suelo y tribuna */}
          <line x1="20" y1="170" x2="380" y2="170" className="guia-campo" />
          <rect x="20" y="130" width="90" height="40" className="guia-tribuna" />

          {/* Soporte y cámara */}
          <line x1="80" y1="130" x2="80" y2="60" className="guia-campo" />
          <circle cx="80" cy="56" r="9" className="guia-camara" />

          {/* Lo que ve la cámara */}
          <line x1="80" y1="56" x2="380" y2="170" className="guia-vision" />
          <line x1="80" y1="56" x2="130" y2="170" className="guia-vision" />

          {/* Cota de la altura */}
          <line x1="48" y1="56" x2="48" y2="170" className="guia-cota" />
          <line x1="42" y1="56" x2="54" y2="56" className="guia-cota" />
          <line x1="42" y1="170" x2="54" y2="170" className="guia-cota" />
          <text x="40" y="118" textAnchor="end" className="guia-texto guia-texto-fuerte">
            {ALTURA_M} m
          </text>

          <text x="270" y="190" textAnchor="middle" className="guia-texto">
            Cancha
          </text>
          <text x="65" y="150" textAnchor="middle" className="guia-texto">
            Tribuna
          </text>
        </svg>
        <figcaption>Vista lateral. Esquema ilustrativo, sin escala.</figcaption>
      </figure>
    </div>
  );
}
