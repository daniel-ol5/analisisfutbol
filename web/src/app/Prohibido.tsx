import { Link } from "react-router-dom";

/** Página 403: hay sesión, pero el rol no tiene permiso para esta sección. */
export function Prohibido() {
  return (
    <main className="pendiente">
      <p className="paq">403</p>
      <h1>Acceso denegado</h1>
      <p className="aviso">Tu rol no tiene permiso para ver esta sección.</p>
      <Link to="/" className="volver">
        ← Volver al inicio
      </Link>
    </main>
  );
}
