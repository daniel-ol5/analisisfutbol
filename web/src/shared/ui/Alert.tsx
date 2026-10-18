import type { ReactNode } from "react";

export type TonoAlerta = "ok" | "aviso" | "info" | "error";

/** Mensaje destacado. Los errores se anuncian de inmediato (role="alert"). */
export function Alert({
  tono = "info",
  titulo,
  children,
}: {
  tono?: TonoAlerta;
  titulo?: string;
  children: ReactNode;
}) {
  return (
    <div className={`ui-alerta ui-alerta--${tono}`} role={tono === "error" ? "alert" : "status"}>
      {titulo && <strong className="ui-alerta-titulo">{titulo}</strong>}
      <div>{children}</div>
    </div>
  );
}
