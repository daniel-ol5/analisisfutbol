/**
 * Datos de la guía de montaje de cámara (CU-18).
 *
 * Fuente de los valores: docs/adr/ADR-001-montaje-de-camara.md. Si el ADR
 * cambia, se cambia SOLO este archivo: la interfaz no repite ningún valor.
 * Lo que el ADR deja en blanco va como `null` y se muestra «Por definir»;
 * nunca se inventa.
 */

/** De dónde sale un dato: del ADR o de una propuesta que el equipo debe confirmar. */
export type Origen = "adr" | "propuesta";

/**
 * TODO: el ADR-001 sigue en estado «pendiente de decisión». Cuando se cierre,
 * confirmar los valores de abajo y poner esta constante en `null`: es el único
 * lugar que hay que tocar para quitar el aviso de la pantalla.
 */
export const AVISO_ESTADO_ADR: string | null =
  "Estos valores vienen del ADR-001, que todavía figura como «pendiente de decisión». Pueden cambiar.";

// ---------- Valores del ADR-001 ----------

export const ALTURA_M = 7;
export const ALTURA_MIN_M = 5;
export const ALTURA_MAX_M = 8;
export const UBICACION = "Tribuna principal, alineada con la línea de mediocampo";
export const RESOLUCION_ANCHO_PX = 1920;
export const RESOLUCION_ALTO_PX = 1080;
export const FPS = 30;
export const CANTIDAD_CAMARAS = 1;

// ---------- Datos recomendados ----------

export interface DatoMontaje {
  id: string;
  etiqueta: string;
  /** `null` = el ADR lo deja en blanco: se muestra «Por definir». */
  valor: string | null;
  detalle?: string;
  origen: Origen;
}

export const DATOS_RECOMENDADOS: readonly DatoMontaje[] = [
  {
    id: "altura",
    etiqueta: "Altura de la cámara",
    valor: `${ALTURA_M} m`,
    detalle: `Rango recomendado: de ${ALTURA_MIN_M} a ${ALTURA_MAX_M} m.`,
    origen: "adr",
  },
  {
    id: "altura-referencia",
    etiqueta: "Altura medida desde",
    // El ADR no dice si se mide desde el suelo de la cancha o desde la grada.
    valor: null,
    origen: "adr",
  },
  {
    id: "ubicacion",
    etiqueta: "Ubicación",
    valor: UBICACION,
    origen: "adr",
  },
  {
    id: "encuadre",
    etiqueta: "Encuadre",
    valor: "Toda la cancha en cuadro",
    detalle: "Deben verse las cuatro esquinas y las líneas de banda.",
    origen: "adr",
  },
  {
    id: "resolucion",
    etiqueta: "Resolución",
    valor: `1080p (${RESOLUCION_ANCHO_PX}×${RESOLUCION_ALTO_PX}) a ${FPS} FPS`,
    origen: "adr",
  },
  {
    id: "cantidad",
    etiqueta: "Cantidad de cámaras",
    valor: `${CANTIDAD_CAMARAS} cámara`,
    origen: "adr",
  },
  {
    id: "modelo",
    etiqueta: "Modelo de cámara",
    // El ADR deja el modelo en blanco.
    valor: null,
    origen: "adr",
  },
];

// ---------- Referencia de tamaños a 1080p en plano abierto ----------

export interface ReferenciaTamano {
  objeto: string;
  minPx: number;
  maxPx: number;
}

export const REFERENCIA_TAMANOS: readonly ReferenciaTamano[] = [
  { objeto: "Un jugador (alto)", minPx: 25, maxPx: 40 },
  { objeto: "El balón", minPx: 5, maxPx: 12 },
];

// ---------- Lista de comprobación previa a calibrar ----------

export interface ItemComprobacion {
  id: string;
  texto: string;
  origen: Origen;
}

/** Ítems que salen del ADR-001. */
export const ITEMS_ADR: readonly ItemComprobacion[] = [
  {
    id: "altura",
    texto: `Cámara montada a la altura acordada (${ALTURA_M} m, entre ${ALTURA_MIN_M} y ${ALTURA_MAX_M}).`,
    origen: "adr",
  },
  {
    id: "mediocampo",
    texto: "Cámara alineada con la línea de mediocampo, en la tribuna principal.",
    origen: "adr",
  },
  {
    id: "cancha-completa",
    texto: "Toda la cancha visible, incluidas las líneas de banda y las cuatro esquinas.",
    origen: "adr",
  },
  {
    id: "resolucion",
    texto: `Resolución configurada a ${RESOLUCION_ANCHO_PX}×${RESOLUCION_ALTO_PX} y ${FPS} FPS.`,
    origen: "adr",
  },
];

/** Ítems que NO vienen del ADR: el equipo debe confirmarlos. */
export const ITEMS_PROPUESTA: readonly ItemComprobacion[] = [
  {
    id: "camara-fija",
    texto: "Cámara fija y estable (trípode o soporte firme, sin vibración).",
    origen: "propuesta",
  },
  {
    id: "sin-zoom",
    texto: "Imagen sin zoom automático ni cambios de enfoque durante el partido.",
    origen: "propuesta",
  },
  {
    id: "sin-contraluz",
    texto: "Sin contraluz fuerte ni sombras que cubran las líneas del campo.",
    origen: "propuesta",
  },
  {
    id: "flujo-video",
    texto: "Flujo de video recibido en el sistema (RTSP o USB).",
    origen: "propuesta",
  },
];
