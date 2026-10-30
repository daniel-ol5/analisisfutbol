import type { InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  id: string;
  etiqueta: string;
  error?: string | undefined;
};

/** Campo de formulario con etiqueta y mensaje de error accesible. */
export function Campo({ id, etiqueta, error, ...resto }: Props) {
  const idError = `${id}-error`;
  return (
    <div className="auth-campo">
      <label htmlFor={id}>{etiqueta}</label>
      <input
        id={id}
        name={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : undefined}
        {...resto}
      />
      {error && (
        <p id={idError} className="auth-error-campo" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
