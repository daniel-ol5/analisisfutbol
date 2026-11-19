/**
 * Lógica pura del catálogo de reglas (CU-54, T-092), sin React ni red.
 *
 * El motor evalúa condiciones en JSON (`backend/app/asistencia/motor.py`). La
 * pantalla las muestra en lenguaje de entrenador y deja armarlas como una lista
 * de comparaciones unidas por "y" / "o". Una condición con grupos anidados no
 * entra en ese formulario: se edita como JSON.
 */
import type { TonoBadge } from "@/shared/ui/Badge";

import type { Condicion, Prioridad, Regla, ReglaCrear, ResultadoPrueba } from "./types";

/**
 * Lo único que una regla puede consultar. Mismo conjunto que
 * `METRICAS_DISPONIBLES` del backend: si se agrega una allí, se agrega aquí.
 */
export const METRICAS = {
  minuto: { etiqueta: "Minuto de partido", unidad: "" },
  altura_linea_m: { etiqueta: "Altura de la línea defensiva", unidad: "m" },
  amplitud_propia_m: { etiqueta: "Amplitud propia", unidad: "m" },
  compacidad_propia_m: { etiqueta: "Dispersión del bloque propio", unidad: "m" },
  posesion_propia_pct: { etiqueta: "Posesión propia", unidad: "%" },
  posesion_rival_pct: { etiqueta: "Posesión rival", unidad: "%" },
  pases_intentados_propios: { etiqueta: "Pases intentados propios (30 s)", unidad: "" },
  pases_completados_rival: { etiqueta: "Pases completados del rival (30 s)", unidad: "" },
  precision_pase_propio_pct: { etiqueta: "Precisión de pase propia", unidad: "%" },
  ritmo_propio_m_min: { etiqueta: "Ritmo propio", unidad: "m/min" },
  caida_ritmo_propio_pct: { etiqueta: "Caída del ritmo propio", unidad: "%" },
  amarillas_propias_10min: { etiqueta: "Amarillas propias (últimos 10 min)", unidad: "" },
  rojas_propias: { etiqueta: "Rojas propias", unidad: "" },
} as const;

export type Metrica = keyof typeof METRICAS;

export const OPERADORES = ["<", "<=", ">", ">=", "==", "!="] as const;
export type Operador = (typeof OPERADORES)[number];

const TEXTO_OPERADOR: Record<Operador, string> = {
  "<": "<",
  "<=": "≤",
  ">": ">",
  ">=": "≥",
  "==": "=",
  "!=": "≠",
};

export const PRIORIDADES: readonly Prioridad[] = ["CRITICA", "ALTA", "MEDIA", "BAJA"];

export const ETIQUETA_PRIORIDAD: Record<Prioridad, string> = {
  CRITICA: "Crítica",
  ALTA: "Alta",
  MEDIA: "Media",
  BAJA: "Baja",
};

export const TONO_PRIORIDAD: Record<Prioridad, TonoBadge> = {
  CRITICA: "error",
  ALTA: "aviso",
  MEDIA: "info",
  BAJA: "neutro",
};

/** T-092: actores "Administrador del Club, Director Técnico" (el backend responde 403 al resto). */
export function puedeGestionarReglas(rol: string | null | undefined): boolean {
  return rol === "ADMIN" || rol === "DT";
}

export function esMetrica(valor: unknown): valor is Metrica {
  return typeof valor === "string" && valor in METRICAS;
}

function esOperador(valor: string): valor is Operador {
  return (OPERADORES as readonly string[]).includes(valor);
}

function textoOperando(valor: unknown): string {
  if (esMetrica(valor)) return METRICAS[valor].etiqueta;
  return typeof valor === "number" ? String(valor) : JSON.stringify(valor);
}

/** "Altura de la línea defensiva < 22 m y Minuto de partido ≥ 5". */
export function describirCondicion(condicion: unknown, anidada = false): string {
  if (typeof condicion !== "object" || condicion === null) return "Condición inválida";
  const entradas = Object.entries(condicion);
  if (entradas.length !== 1) return "Condición inválida";
  const [op, args] = entradas[0];
  if (!Array.isArray(args)) return "Condición inválida";

  if (op === "y" || op === "o") {
    const partes = args.map((a) => describirCondicion(a, true));
    const texto = partes.join(op === "y" ? " y " : " o ");
    return anidada && partes.length > 1 ? `(${texto})` : texto;
  }
  if (!esOperador(op) || args.length !== 2) return "Condición inválida";
  const [izq, der] = args;
  // Unidad junto al número, si el otro lado es una métrica con unidad.
  const unidad = esMetrica(izq) ? METRICAS[izq].unidad : esMetrica(der) ? METRICAS[der].unidad : "";
  const conUnidad = (v: unknown) =>
    typeof v === "number" && unidad ? `${v} ${unidad}` : textoOperando(v);
  return `${conUnidad(izq)} ${TEXTO_OPERADOR[op]} ${conUnidad(der)}`;
}

/** "30 s", "5 min", "1 h 30 min". */
export function formatoEspera(segundos: number): string {
  if (segundos < 60) return `${segundos} s`;
  const horas = Math.floor(segundos / 3600);
  const minutos = Math.floor((segundos % 3600) / 60);
  const resto = segundos % 60;
  const partes = [horas && `${horas} h`, minutos && `${minutos} min`, resto && `${resto} s`];
  return partes.filter(Boolean).join(" ");
}

/** Prioridad más alta primero; a igual prioridad, por nombre. */
export function ordenarReglas(reglas: readonly Regla[]): Regla[] {
  return [...reglas].sort(
    (a, b) =>
      PRIORIDADES.indexOf(a.prioridad) - PRIORIDADES.indexOf(b.prioridad) ||
      a.nombre.localeCompare(b.nombre, "es"),
  );
}

// ---------- Formulario: condición como lista de comparaciones ----------

export interface Comparacion {
  metrica: Metrica;
  operador: Operador;
  /** Texto del campo; se valida al enviar. */
  valor: string;
}

export interface CondicionPlana {
  union: "y" | "o";
  comparaciones: Comparacion[];
}

export const COMPARACION_VACIA: Comparacion = { metrica: "minuto", operador: ">=", valor: "" };

/**
 * La condición como lista de comparaciones "métrica operador número", o null si
 * no entra en ese formato (grupos anidados, número a la izquierda...).
 */
export function aCondicionPlana(condicion: Condicion): CondicionPlana | null {
  const entradas = Object.entries(condicion);
  if (entradas.length !== 1) return null;
  const [op, args] = entradas[0];
  const grupo = op === "y" || op === "o";
  const lista = grupo ? args : [condicion];
  const comparaciones: Comparacion[] = [];
  for (const item of lista) {
    if (typeof item !== "object" || item === null) return null;
    const pares = Object.entries(item as Record<string, unknown>);
    if (pares.length !== 1) return null;
    const [operador, operandos] = pares[0];
    if (!esOperador(operador) || !Array.isArray(operandos) || operandos.length !== 2) return null;
    const [metrica, valor] = operandos;
    if (!esMetrica(metrica) || typeof valor !== "number") return null;
    comparaciones.push({ metrica, operador, valor: String(valor) });
  }
  return { union: grupo ? (op as "y" | "o") : "y", comparaciones };
}

export function deCondicionPlana(plana: CondicionPlana): Condicion {
  return {
    [plana.union]: plana.comparaciones.map((c) => ({
      [c.operador]: [c.metrica, Number(c.valor.replace(",", "."))],
    })),
  };
}

export interface FormularioRegla {
  nombre: string;
  prioridad: Prioridad;
  /** En minutos en el formulario; el backend lo guarda en segundos. */
  espera_min: string;
  /** null: se edita como JSON (`condicion_json`). */
  condicion: CondicionPlana | null;
  condicion_json: string;
  plantilla_mensaje: string;
  plantilla_justificacion: string;
}

export const FORMULARIO_NUEVO: FormularioRegla = {
  nombre: "",
  prioridad: "MEDIA",
  espera_min: "5",
  condicion: { union: "y", comparaciones: [{ ...COMPARACION_VACIA, valor: "5" }] },
  condicion_json: "",
  plantilla_mensaje: "",
  plantilla_justificacion: "",
};

export function formularioDesdeRegla(regla: Regla): FormularioRegla {
  return {
    nombre: regla.nombre,
    prioridad: regla.prioridad,
    espera_min: String(regla.cooldown_s / 60),
    condicion: aCondicionPlana(regla.condicion),
    condicion_json: JSON.stringify(regla.condicion, null, 2),
    plantilla_mensaje: regla.plantilla_mensaje,
    plantilla_justificacion: regla.plantilla_justificacion,
  };
}

export type ErroresFormulario = Partial<Record<keyof FormularioRegla | "comparaciones", string>>;

export type ResultadoFormulario =
  { ok: true; datos: Omit<ReglaCrear, "activa"> } | { ok: false; errores: ErroresFormulario };

function numero(texto: string): number | null {
  const limpio = texto.trim().replace(",", ".");
  if (limpio === "") return null;
  const n = Number(limpio);
  return Number.isFinite(n) ? n : null;
}

/**
 * Valida lo que se puede validar sin el servidor. Que las métricas de las
 * plantillas existan lo comprueba el backend (422), que es la fuente de verdad.
 */
export function validarFormulario(form: FormularioRegla): ResultadoFormulario {
  const errores: ErroresFormulario = {};
  if (!form.nombre.trim()) errores.nombre = "Ponle un nombre a la regla.";
  if (!form.plantilla_mensaje.trim())
    errores.plantilla_mensaje = "Escribe qué se le recomienda al DT.";

  const espera = numero(form.espera_min);
  const cooldown = espera === null ? null : Math.round(espera * 60);
  if (cooldown === null || cooldown < 30 || cooldown > 3600) {
    errores.espera_min = "Entre 0,5 y 60 minutos.";
  }

  let condicion: Condicion | null = null;
  if (form.condicion) {
    if (form.condicion.comparaciones.length === 0) {
      errores.comparaciones = "Agrega al menos una comparación.";
    } else if (form.condicion.comparaciones.some((c) => numero(c.valor) === null)) {
      errores.comparaciones = "Cada comparación necesita un número.";
    } else {
      condicion = deCondicionPlana(form.condicion);
    }
  } else {
    try {
      const leida: unknown = JSON.parse(form.condicion_json);
      if (typeof leida !== "object" || leida === null || Array.isArray(leida)) throw new Error();
      condicion = leida as Condicion;
    } catch {
      errores.condicion_json = "No es un JSON válido.";
    }
  }

  if (Object.keys(errores).length > 0 || condicion === null || cooldown === null) {
    return { ok: false, errores };
  }
  return {
    ok: true,
    datos: {
      nombre: form.nombre.trim(),
      prioridad: form.prioridad,
      cooldown_s: cooldown,
      condicion,
      plantilla_mensaje: form.plantilla_mensaje.trim(),
      plantilla_justificacion: form.plantilla_justificacion.trim(),
    },
  };
}

// ---------- Probar contra un partido ----------

export function textoResultadoPrueba(resultado: ResultadoPrueba): string {
  if (resultado.evaluaciones === 0) {
    return "Ese partido no tiene posiciones guardadas: no hay con qué probar la regla.";
  }
  if (resultado.disparos === 0) {
    return "No se habría disparado en ese partido.";
  }
  const distintos = [...new Set(resultado.minutos)];
  const minutos = distintos.map((m) => `${m}'`).join(", ");
  const veces = resultado.disparos === 1 ? "1 vez" : `${resultado.disparos} veces`;
  const donde = distintos.length === 1 ? `en el minuto ${minutos}` : `en los minutos ${minutos}`;
  return `Se habría disparado ${veces}, ${donde}.`;
}
