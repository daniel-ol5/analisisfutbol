import { Link } from "react-router-dom";

/** Página 404: la ruta no existe. */
export function NoEncontrada() {
  return (
    <main className="pendiente">
      <p className="paq">404</p>
      <h1>Página no encontrada</h1>
      <p className="aviso">La dirección que buscas no existe o fue movida.</p>
      <Link to="/" className="volver">
        ← Volver al inicio
      </Link>
    </main>
  );
}
