/**
 * Página base de una feature todavía no implementada.
 *
 * Muestra qué casos de uso le corresponden, para que quien la tome sepa de
 * entrada cuál es su alcance.
 */
import { Link } from "react-router-dom";

export function Pendiente({
  paquete,
  titulo,
  casos,
}: {
  paquete: string;
  titulo: string;
  casos: string[];
}) {
  return (
    <main className="pendiente">
      <Link to="/" className="volver">
        ← Inicio
      </Link>
      <p className="paq">{paquete}</p>
      <h1>{titulo}</h1>
      <p className="aviso">
        Pendiente de implementación. Estos son los casos de uso de este paquete:
      </p>
      <ul>
        {casos.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </main>
  );
}
