/** Pasos para bajar el error de calibración, en lenguaje llano (CU-21). */
import { Link } from "react-router-dom";

export function GuiaCorreccion({ titulo }: { titulo: string }) {
  return (
    <div className="cal-guia-correccion">
      <h3>{titulo}</h3>
      <ul>
        <li>
          Revisa el punto señalado como «Mayor error» y los que están cerca de él: seguramente
          alguno quedó mal puesto sobre la imagen. Arrástralo o muévelo con las flechas.
        </li>
        <li>
          Reparte los puntos por toda la cancha (esquinas, mediocampo y áreas) y evita ponerlos en
          fila o muy juntos.
        </li>
        <li>Confirma que el largo y el ancho de la cancha sean las medidas reales.</li>
        <li>
          Comprueba que el cuadro no esté deformado (zoom, recorte o lente muy angular) y que los
          puntos estén sobre el suelo, no sobre el travesaño.
        </li>
      </ul>
      <p>
        Si sigue sin mejorar, revisa el <Link to="/vision/guia-montaje">montaje de la cámara</Link>.
      </p>
    </div>
  );
}
