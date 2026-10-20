import { useId, type SelectHTMLAttributes } from "react";

interface Props extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  etiqueta: string;
  error?: string;
  ayuda?: string;
  id?: string;
}

/** Lista desplegable nativa (accesible por teclado) con la misma anatomía que Input. */
export function Select({ etiqueta, error, ayuda, id, className, children, ...resto }: Props) {
  const generado = useId();
  const idCampo = id ?? generado;
  const idAyuda = `${idCampo}-ayuda`;
  const idError = `${idCampo}-error`;
  const descritoPor = [ayuda ? idAyuda : null, error ? idError : null].filter(Boolean).join(" ");

  return (
    <div className="ui-campo">
      <label htmlFor={idCampo} className="ui-etiqueta">
        {etiqueta}
      </label>
      <select
        id={idCampo}
        className={["ui-control", className].filter(Boolean).join(" ")}
        aria-invalid={error ? true : undefined}
        aria-describedby={descritoPor || undefined}
        {...resto}
      >
        {children}
      </select>
      {ayuda && (
        <p id={idAyuda} className="ui-ayuda">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="ui-error">
          {error}
        </p>
      )}
    </div>
  );
}
