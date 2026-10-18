import type { ButtonHTMLAttributes } from "react";

export type VarianteBoton = "primario" | "secundario" | "peligro" | "fantasma";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton;
}

/** Botón base. `type` es "button" por defecto para no enviar formularios sin querer. */
export function Button({ variante = "primario", className, type = "button", ...resto }: Props) {
  const clases = ["ui-btn", `ui-btn--${variante}`, className].filter(Boolean).join(" ");
  return <button type={type} className={clases} {...resto} />;
}
