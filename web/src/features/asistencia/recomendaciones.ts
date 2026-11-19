/**
 * Reglas de la lista de recomendaciones activas  —  T-090 (CU-50).
 *
 * Funciones puras, las mismas que aplica el servidor con `solo_activas=true`:
 * como máximo 3, por prioridad (CRITICA, ALTA, MEDIA, BAJA) y, a igual
 * prioridad, la más reciente primero. Una sola por regla: la nueva reemplaza.
 */
import type { DatoSoporte, Prioridad, Recomendacion } from "./types";

export const MAX_ACTIVAS = 3;

const ORDEN: Record<Prioridad, number> = { CRITICA: 0, ALTA: 1, MEDIA: 2, BAJA: 3 };

export function esActiva(r: Recomendacion): boolean {
  return r.estado === "PENDIENTE" || r.estado === "VISTA";
}

export function ordenarActivas(lista: readonly Recomendacion[]): Recomendacion[] {
  return lista
    .filter(esActiva)
    .sort((a, b) => ORDEN[a.prioridad] - ORDEN[b.prioridad] || b.t - a.t || b.id - a.id)
    .slice(0, MAX_ACTIVAS);
}

/** Agrega (o actualiza) una recomendación que llegó por /vivo o por una valoración. */
export function incorporar(
  lista: readonly Recomendacion[],
  nueva: Recomendacion,
): Recomendacion[] {
  const resto = lista.filter((r) => r.id !== nueva.id && r.regla_id !== nueva.regla_id);
  return ordenarActivas([...resto, nueva]);
}

/** Si el WebSocket entregó un objeto con forma de Recomendacion. */
export function esRecomendacion(valor: unknown): valor is Recomendacion {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    typeof v.id === "number" &&
    typeof v.regla_id === "number" &&
    typeof v.t === "number" &&
    typeof v.mensaje === "string" &&
    typeof v.prioridad === "string" &&
    v.prioridad in ORDEN &&
    Array.isArray(v.datos_soporte)
  );
}

// ---------- Cifras legibles (T-090: la justificación con las cifras reales) ----------

const METRICAS: Record<string, { etiqueta: string; unidad: string }> = {
  minuto: { etiqueta: "Minuto", unidad: "'" },
  altura_linea_m: { etiqueta: "Altura de la línea", unidad: " m" },
  amplitud_propia_m: { etiqueta: "Amplitud propia", unidad: " m" },
  compacidad_propia_m: { etiqueta: "Compacidad propia", unidad: " m" },
  posesion_propia_pct: { etiqueta: "Posesión propia", unidad: " %" },
  posesion_rival_pct: { etiqueta: "Posesión rival", unidad: " %" },
  pases_intentados_propios: { etiqueta: "Pases intentados propios", unidad: "" },
  pases_completados_rival: { etiqueta: "Pases completados del rival", unidad: "" },
  precision_pase_propio_pct: { etiqueta: "Precisión de pase propia", unidad: " %" },
  ritmo_propio_m_min: { etiqueta: "Ritmo propio", unidad: " m/min" },
  caida_ritmo_propio_pct: { etiqueta: "Caída del ritmo", unidad: " %" },
  amarillas_propias_10min: { etiqueta: "Amarillas propias (10 min)", unidad: "" },
  rojas_propias: { etiqueta: "Expulsiones propias", unidad: "" },
};

function numero(valor: number): string {
  return Number.isInteger(valor)
    ? String(valor)
    : valor.toLocaleString("es", { maximumFractionDigits: 1 });
}

export interface CifraLegible {
  etiqueta: string;
  valor: string;
  umbral: string | null;
}

export function cifraLegible(dato: DatoSoporte): CifraLegible {
  const meta = METRICAS[dato.metrica] ?? { etiqueta: dato.metrica, unidad: "" };
  return {
    etiqueta: meta.etiqueta,
    valor: `${numero(dato.valor)}${meta.unidad}`,
    umbral: dato.umbral === null ? null : `${numero(dato.umbral)}${meta.unidad}`,
  };
}

export const ETIQUETA_PRIORIDAD: Record<Prioridad, string> = {
  CRITICA: "Crítica",
  ALTA: "Alta",
  MEDIA: "Media",
  BAJA: "Baja",
};
