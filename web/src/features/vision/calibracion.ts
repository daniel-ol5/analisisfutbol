/**
 * Constantes, plantilla de referencias y validadores de calibración (CU-19, CU-20).
 *
 * Lo que no está cerrado en el contrato o en un ADR se declara aquí como
 * constante con nombre y comentario TODO, para poder ajustarlo en un único sitio.
 */
import type { HitoCancha, ParCalibracion, Punto } from "./types";

/**
 * TODO: confirmar con el líder del proyecto la convención del sistema de
 * coordenadas de la cancha y la plantilla de hitos sugeridos. Cuando quede
 * cerrada, poner esta constante en `null` para ocultar el aviso en la pantalla.
 */
export const AVISO_PROPUESTA_CALIBRACION: string | null =
  "Propuesta pendiente de confirmar con el líder: el sistema de coordenadas sitúa el origen (0, 0) en la esquina inferior izquierda del lado de la cámara (tribuna), con X a lo largo (0 a largo_m) e Y a lo ancho (0 a ancho_m), y usa una plantilla de 14 hitos de referencia.";

// ---------- Límites del contrato (backend/app/vision/schemas.py) ----------

export const MIN_PUNTOS_CALIBRACION = 8;

export const LARGO_CANCHA_DEFECTO_M = 105;
export const ANCHO_CANCHA_DEFECTO_M = 68;

/** En el backend `gt=40, lt=130` (exclusivos). */
export const LARGO_MIN_EXCLUSIVO_M = 40;
export const LARGO_MAX_EXCLUSIVO_M = 130;

/** En el backend `gt=25, lt=90` (exclusivos). */
export const ANCHO_MIN_EXCLUSIVO_M = 25;
export const ANCHO_MAX_EXCLUSIVO_M = 90;

/**
 * TODO: medidas reglamentarias FIFA del área penal (16,5 m × 40,32 m). En
 * canchas formativas más angostas o cortas se escalan proporcionalmente para
 * no desbordar el campo.
 */
export const PROFUNDIDAD_AREA_GRANDE_M = 16.5;
export const ANCHO_AREA_GRANDE_M = 40.32;

/** Roles autorizados por el backend para `POST /vision/partidos/{id}/calibracion`. */
export const ROLES_PUEDEN_CALIBRAR: readonly string[] = ["ADMIN", "ANALISTA"];

// ---------- Utilidades numéricas y de coordenadas ----------

export function redondear2(valor: number): number {
  return Math.round(valor * 100) / 100;
}

export function acotar(valor: number, min: number, max: number): number {
  return Math.min(Math.max(valor, min), max);
}

/**
 * Convierte la posición del puntero en pantalla a píxeles reales de la imagen
 * original (`naturalWidth` × `naturalHeight`), redondeados a 2 decimales y
 * acotados a los bordes del cuadro.
 */
export function clienteAPixelesImagen(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  naturalWidth: number,
  naturalHeight: number,
): Punto {
  if (rect.width <= 0 || rect.height <= 0) {
    return { x: 0, y: 0 };
  }
  const relX = (clientX - rect.left) / rect.width;
  const relY = (clientY - rect.top) / rect.height;
  return {
    x: redondear2(acotar(relX * naturalWidth, 0, naturalWidth)),
    y: redondear2(acotar(relY * naturalHeight, 0, naturalHeight)),
  };
}

/**
 * Calcula las medidas del área grande adaptadas a `largoM` y `anchoM` para que
 * nunca excedan las dimensiones de una cancha pequeña.
 */
export function medidasAreaGrande(
  largoM: number,
  anchoM: number,
): { profM: number; anchoAreaM: number; yInfM: number; ySupM: number } {
  const largoSeguro = Number.isFinite(largoM) && largoM > 0 ? largoM : LARGO_CANCHA_DEFECTO_M;
  const anchoSeguro = Number.isFinite(anchoM) && anchoM > 0 ? anchoM : ANCHO_CANCHA_DEFECTO_M;

  const profM = redondear2(Math.min(PROFUNDIDAD_AREA_GRANDE_M, largoSeguro * 0.22));
  const anchoAreaM = redondear2(Math.min(ANCHO_AREA_GRANDE_M, anchoSeguro * 0.65));
  const yInfM = redondear2((anchoSeguro - anchoAreaM) / 2);
  const ySupM = redondear2(anchoSeguro - yInfM);

  return { profM, anchoAreaM, yInfM, ySupM };
}

/**
 * Construye la plantilla de 14 hitos sobre el plano de la cancha:
 * 4 esquinas, 2 intersecciones de mediocampo con bandas y 8 esquinas de áreas grandes.
 *
 * Origen `(0, 0)` en la esquina inferior izquierda (lado de la cámara / tribuna).
 */
export function construirPlantillaCancha(largoM: number, anchoM: number): HitoCancha[] {
  const L = Number.isFinite(largoM) && largoM > 0 ? redondear2(largoM) : LARGO_CANCHA_DEFECTO_M;
  const W = Number.isFinite(anchoM) && anchoM > 0 ? redondear2(anchoM) : ANCHO_CANCHA_DEFECTO_M;
  const medioX = redondear2(L / 2);
  const { profM, yInfM, ySupM } = medidasAreaGrande(L, W);
  const xAreaDer = redondear2(L - profM);

  return [
    {
      id: "esq-inf-izq",
      nombre: "Esquina inferior izquierda (tribuna)",
      nombreCorto: "Esq. inf. izq.",
      x: 0,
      y: 0,
    },
    {
      id: "esq-inf-der",
      nombre: "Esquina inferior derecha (tribuna)",
      nombreCorto: "Esq. inf. der.",
      x: L,
      y: 0,
    },
    {
      id: "esq-sup-der",
      nombre: "Esquina superior derecha (opuesta)",
      nombreCorto: "Esq. sup. der.",
      x: L,
      y: W,
    },
    {
      id: "esq-sup-izq",
      nombre: "Esquina superior izquierda (opuesta)",
      nombreCorto: "Esq. sup. izq.",
      x: 0,
      y: W,
    },
    {
      id: "med-inf",
      nombre: "Mediocampo banda inferior (tribuna)",
      nombreCorto: "Medio inf.",
      x: medioX,
      y: 0,
    },
    {
      id: "med-sup",
      nombre: "Mediocampo banda superior (opuesta)",
      nombreCorto: "Medio sup.",
      x: medioX,
      y: W,
    },
    {
      id: "area-izq-inf-fondo",
      nombre: "Área izq. · unión inferior con línea de meta",
      nombreCorto: "Área izq. meta inf.",
      x: 0,
      y: yInfM,
    },
    {
      id: "area-izq-inf-frontal",
      nombre: "Área izq. · vértice frontal inferior",
      nombreCorto: "Área izq. vért. inf.",
      x: profM,
      y: yInfM,
    },
    {
      id: "area-izq-sup-frontal",
      nombre: "Área izq. · vértice frontal superior",
      nombreCorto: "Área izq. vért. sup.",
      x: profM,
      y: ySupM,
    },
    {
      id: "area-izq-sup-fondo",
      nombre: "Área izq. · unión superior con línea de meta",
      nombreCorto: "Área izq. meta sup.",
      x: 0,
      y: ySupM,
    },
    {
      id: "area-der-inf-fondo",
      nombre: "Área der. · unión inferior con línea de meta",
      nombreCorto: "Área der. meta inf.",
      x: L,
      y: yInfM,
    },
    {
      id: "area-der-inf-frontal",
      nombre: "Área der. · vértice frontal inferior",
      nombreCorto: "Área der. vért. inf.",
      x: xAreaDer,
      y: yInfM,
    },
    {
      id: "area-der-sup-frontal",
      nombre: "Área der. · vértice frontal superior",
      nombreCorto: "Área der. vért. sup.",
      x: xAreaDer,
      y: ySupM,
    },
    {
      id: "area-der-sup-fondo",
      nombre: "Área der. · unión superior con línea de meta",
      nombreCorto: "Área der. meta sup.",
      x: L,
      y: ySupM,
    },
  ];
}

/**
 * Recalcula las coordenadas en metros de los pares ligados a la plantilla
 * cuando el usuario edita `largoM` o `anchoM`. Los puntos libres (`hitoId === null`)
 * conservan sus metros originales.
 */
export function recalcularParesConMedidas(
  pares: readonly ParCalibracion[],
  largoM: number,
  anchoM: number,
): ParCalibracion[] {
  const plantilla = construirPlantillaCancha(largoM, anchoM);
  const mapa = new Map(plantilla.map((h) => [h.id, h]));

  return pares.map((par) => {
    if (par.hitoId === null) return par;
    const hito = mapa.get(par.hitoId);
    if (!hito) return par;
    return {
      ...par,
      cancha: { x: hito.x, y: hito.y },
    };
  });
}

/**
 * Devuelve los números de punto (base 1) de los pares libres cuyas coordenadas
 * en metros quedaron fuera de `[0, largoM] × [0, anchoM]`.
 */
export function paresLibresFueraDeCancha(
  pares: readonly ParCalibracion[],
  largoM: number,
  anchoM: number,
): number[] {
  if (!Number.isFinite(largoM) || !Number.isFinite(anchoM)) return [];
  const fuera: number[] = [];
  pares.forEach((par, idx) => {
    if (
      par.hitoId === null &&
      (par.cancha.x < 0 || par.cancha.x > largoM || par.cancha.y < 0 || par.cancha.y > anchoM)
    ) {
      fuera.push(idx + 1);
    }
  });
  return fuera;
}

function indicesDuplicados(puntos: readonly Punto[]): number[] {
  const vistos = new Set<string>();
  const duplicados: number[] = [];
  puntos.forEach((p, idx) => {
    const clave = `${redondear2(p.x)},${redondear2(p.y)}`;
    if (vistos.has(clave)) {
      duplicados.push(idx + 1);
    }
    vistos.add(clave);
  });
  return duplicados;
}

export interface ValidacionCalibracionCliente {
  valido: boolean;
  partidoId: number | null;
  erroresMedidas: string[];
  erroresPuntos: string[];
}

export function validarEstadoCalibracion(
  partidoIdTexto: string,
  largoM: number,
  anchoM: number,
  pares: readonly ParCalibracion[],
): ValidacionCalibracionCliente {
  const erroresMedidas: string[] = [];
  const erroresPuntos: string[] = [];

  const limpio = partidoIdTexto.trim();
  const numPartido = Number(limpio);
  const partidoId =
    limpio !== "" && Number.isInteger(numPartido) && numPartido >= 1 ? numPartido : null;

  if (partidoId === null) {
    erroresMedidas.push("Ingresa un ID de partido entero positivo (por ejemplo, 1).");
  }

  if (
    !Number.isFinite(largoM) ||
    largoM <= LARGO_MIN_EXCLUSIVO_M ||
    largoM >= LARGO_MAX_EXCLUSIVO_M
  ) {
    erroresMedidas.push(
      `El largo debe ser mayor a ${LARGO_MIN_EXCLUSIVO_M} m y menor a ${LARGO_MAX_EXCLUSIVO_M} m.`,
    );
  }

  if (
    !Number.isFinite(anchoM) ||
    anchoM <= ANCHO_MIN_EXCLUSIVO_M ||
    anchoM >= ANCHO_MAX_EXCLUSIVO_M
  ) {
    erroresMedidas.push(
      `El ancho debe ser mayor a ${ANCHO_MIN_EXCLUSIVO_M} m y menor a ${ANCHO_MAX_EXCLUSIVO_M} m.`,
    );
  }

  if (pares.length < MIN_PUNTOS_CALIBRACION) {
    const faltan = MIN_PUNTOS_CALIBRACION - pares.length;
    erroresPuntos.push(
      `Se requieren al menos ${MIN_PUNTOS_CALIBRACION} pares de puntos (faltan ${faltan}).`,
    );
  }

  const dupImg = indicesDuplicados(pares.map((p) => p.imagen));
  if (dupImg.length > 0) {
    erroresPuntos.push(
      `Hay puntos de imagen repetidos en las filas: ${dupImg.join(", ")}. Cada marca debe ser distinta.`,
    );
  }

  const dupCancha = indicesDuplicados(pares.map((p) => p.cancha));
  if (dupCancha.length > 0) {
    erroresPuntos.push(
      `Hay puntos de cancha repetidos en las filas: ${dupCancha.join(", ")}. Cada referencia en metros debe ser distinta.`,
    );
  }

  return {
    valido: erroresMedidas.length === 0 && erroresPuntos.length === 0,
    partidoId,
    erroresMedidas,
    erroresPuntos,
  };
}

/**
 * Lee el rol de la sesión guardada en `localStorage` sin importar de la
 * feature `seguridad` (respetando la regla de aislamiento entre features).
 */
export function obtenerRolSesionActual(): string | null {
  try {
    const crudo = localStorage.getItem("areatecnica.sesion");
    if (!crudo) return null;
    const parsed: unknown = JSON.parse(crudo);
    if (typeof parsed !== "object" || parsed === null) return null;
    const usuario = (parsed as Record<string, unknown>)["usuario"];
    if (typeof usuario !== "object" || usuario === null) return null;
    const rol = (usuario as Record<string, unknown>)["rol"];
    return typeof rol === "string" ? rol : null;
  } catch {
    return null;
  }
}

export function rolPuedeGuardarCalibracion(rol: string | null): boolean {
  return rol !== null && ROLES_PUEDEN_CALIBRAR.includes(rol);
}
