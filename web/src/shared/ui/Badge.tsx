import type { ReactNode } from "react";

export type TonoBadge = "neutro" | "ok" | "aviso" | "info" | "error";

export function Badge({ tono = "neutro", children }: { tono?: TonoBadge; children: ReactNode }) {
  return <span className={`ui-badge ui-badge--${tono}`}>{children}</span>;
}
