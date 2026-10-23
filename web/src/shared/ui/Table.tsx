import type { ReactNode, TableHTMLAttributes } from "react";

interface Props extends TableHTMLAttributes<HTMLTableElement> {
  /** Descripción de la tabla para lectores de pantalla (se usa como <caption>). */
  titulo: string;
  children: ReactNode;
}

/**
 * Tabla con desplazamiento horizontal accesible por teclado.
 * Se compone con <thead>, <tbody>, <tr>, <th scope="col"> y <td> estándar.
 */
export function Table({ titulo, children, className, ...resto }: Props) {
  return (
    <div className="ui-tabla-wrap" role="region" aria-label={titulo} tabIndex={0}>
      <table className={["ui-tabla", className].filter(Boolean).join(" ")} {...resto}>
        <caption className="ui-solo-lectores">{titulo}</caption>
        {children}
      </table>
    </div>
  );
}
