import { useId, type InputHTMLAttributes } from "react";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  etiqueta: string;
  error?: string;
  ayuda?: string;
  id?: string;
}

/** Campo de texto con etiqueta obligatoria, ayuda y mensaje de error accesibles. */
export function Input({ etiqueta, error, ayuda, id, className, ...resto }: Props) {
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
      <input
        id={idCampo}
        className={["ui-control", className].filter(Boolean).join(" ")}
        aria-invalid={error ? true : undefined}
        aria-describedby={descritoPor || undefined}
        {...resto}
      />
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
