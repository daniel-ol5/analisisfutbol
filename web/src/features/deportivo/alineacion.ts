/**
 * Lógica del editor de alineación  —  CU-17 · T-051 (HU-14).
 *
 * Sin React ni red: formaciones, reglas y armado del pedido. Las mismas reglas
 * que valida el backend (HU-14 · Criterio 3), para avisar antes de guardar.
 */
import type {
  Alineacion,
  AlineacionGuardar,
  Formacion,
  Jugador,
  JugadorAlineado,
  Partido,
  Posicion,
} from "./types";
import type { Rol } from "@/features/seguridad";

export const TITULARES = 11;

/** Roles que el backend deja guardar la alineación; el resto solo la ve. */
export const ROLES_EDITAN_ALINEACION: readonly Rol[] = ["ADMIN", "DT", "ASISTENTE"];

export function puedeEditarAlineacion(rol: Rol | undefined): boolean {
  return rol !== undefined && ROLES_EDITAN_ALINEACION.includes(rol);
}

/**
 * Con el partido terminado la alineación ya alimentó el análisis: el backend
 * solo deja cambiarla mientras está PROGRAMADO o EN_CURSO (409 si no).
 */
export function partidoEditable(partido: Pick<Partido, "estado">): boolean {
  return partido.estado === "PROGRAMADO" || partido.estado === "EN_CURSO";
}

const formatoFecha = new Intl.DateTimeFormat("es-BO", {
  weekday: "short",
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

/** "vs Bolívar · sáb 15 nov, 16:00" */
export function nombrePartido(p: Partido): string {
  return `vs ${p.rival} · ${formatoFecha.format(new Date(p.fecha_hora))}`;
}

/** Un puesto de la formación: dónde va y qué posición le corresponde. */
export interface Puesto {
  rol: Posicion;
  x: number;
  y: number;
}

const ARQ: Puesto = { rol: "ARQ", x: 5, y: 50 };
const LINEA_DE_4: Puesto[] = [
  { rol: "DEF", x: 22, y: 85 },
  { rol: "DEF", x: 19, y: 62 },
  { rol: "DEF", x: 19, y: 38 },
  { rol: "DEF", x: 22, y: 15 },
];

/**
 * Los 11 puestos de cada formación. El puesto 0 es siempre el del arquero.
 * `y` crece hacia la banda derecha mirando al arco rival.
 */
export const PUESTOS: Record<Formacion, readonly Puesto[]> = {
  "4-3-3": [
    ARQ,
    ...LINEA_DE_4,
    { rol: "MED", x: 42, y: 75 },
    { rol: "MED", x: 38, y: 50 },
    { rol: "MED", x: 42, y: 25 },
    { rol: "DEL", x: 66, y: 82 },
    { rol: "DEL", x: 70, y: 50 },
    { rol: "DEL", x: 66, y: 18 },
  ],
  "4-4-2": [
    ARQ,
    ...LINEA_DE_4,
    { rol: "MED", x: 43, y: 88 },
    { rol: "MED", x: 40, y: 62 },
    { rol: "MED", x: 40, y: 38 },
    { rol: "MED", x: 43, y: 12 },
    { rol: "DEL", x: 66, y: 65 },
    { rol: "DEL", x: 66, y: 35 },
  ],
  "4-2-3-1": [
    ARQ,
    ...LINEA_DE_4,
    { rol: "MED", x: 35, y: 65 },
    { rol: "MED", x: 35, y: 35 },
    { rol: "MED", x: 53, y: 85 },
    { rol: "MED", x: 55, y: 50 },
    { rol: "MED", x: 53, y: 15 },
    { rol: "DEL", x: 71, y: 50 },
  ],
  "3-5-2": [
    ARQ,
    { rol: "DEF", x: 20, y: 75 },
    { rol: "DEF", x: 18, y: 50 },
    { rol: "DEF", x: 20, y: 25 },
    { rol: "MED", x: 43, y: 92 },
    { rol: "MED", x: 38, y: 70 },
    { rol: "MED", x: 35, y: 50 },
    { rol: "MED", x: 38, y: 30 },
    { rol: "MED", x: 43, y: 8 },
    { rol: "DEL", x: 66, y: 65 },
    { rol: "DEL", x: 66, y: 35 },
  ],
};

/** Un titular ocupa un puesto, pero su punto puede moverse a mano. */
export interface Titular {
  jugadorId: number;
  x: number;
  y: number;
}

/**
 * Estado del editor. `titulares` tiene siempre 11 lugares, uno por puesto de
 * la formación (null = puesto libre); así, al cambiar de formación cada
 * titular conserva su lugar.
 */
export interface EstadoAlineacion {
  formacion: Formacion;
  titulares: (Titular | null)[];
  suplentes: number[];
  capitanId: number | null;
}

export function alineacionVacia(formacion: Formacion = "4-3-3"): EstadoAlineacion {
  return {
    formacion,
    titulares: Array.from({ length: TITULARES }, () => null),
    suplentes: [],
    capitanId: null,
  };
}

const redondear = (v: number) => Math.round(Math.min(100, Math.max(0, v)) * 10) / 10;

/**
 * Pasa la alineación guardada al estado del editor. Cada titular conserva su
 * punto y ocupa el puesto libre más cercano. Los jugadores que ya no están en
 * el plantel activo se descartan y se devuelven aparte, para avisar.
 */
export function estadoDesdeAlineacion(
  alineacion: Alineacion,
  plantel: readonly Jugador[],
): { estado: EstadoAlineacion; descartados: Alineacion["jugadores"] } {
  const enPlantel = new Set(plantel.map((j) => j.id));
  const descartados = alineacion.jugadores.filter((j) => !enPlantel.has(j.jugador_id));
  const vigentes = alineacion.jugadores.filter((j) => enPlantel.has(j.jugador_id));

  const estado = alineacionVacia(alineacion.formacion);
  const puestos = PUESTOS[alineacion.formacion];
  // El arquero primero, para que se quede con el puesto 0.
  const titulares = vigentes
    .filter((j) => j.es_titular)
    .sort((a, b) => Number(b.posicion === "ARQ") - Number(a.posicion === "ARQ"));

  for (const j of titulares) {
    const libre = puestoLibreMasCercano(estado.titulares, puestos, j.pos_x, j.pos_y);
    if (libre === -1) break;
    estado.titulares[libre] = { jugadorId: j.jugador_id, x: j.pos_x, y: j.pos_y };
  }
  estado.suplentes = vigentes.filter((j) => !j.es_titular).map((j) => j.jugador_id);
  const capitan = vigentes.find((j) => j.es_capitan && j.es_titular);
  estado.capitanId = capitan ? capitan.jugador_id : null;
  return { estado, descartados };
}

function puestoLibreMasCercano(
  ocupados: readonly (Titular | null)[],
  puestos: readonly Puesto[],
  x: number,
  y: number,
): number {
  let mejor = -1;
  let distancia = Infinity;
  puestos.forEach((p, i) => {
    if (ocupados[i] !== null) return;
    const d = (p.x - x) ** 2 + (p.y - y) ** 2;
    if (d < distancia) {
      distancia = d;
      mejor = i;
    }
  });
  return mejor;
}

/** Puesto libre para un jugador nuevo: primero uno de su posición, si no cualquiera. */
export function puestoParaJugador(estado: EstadoAlineacion, posicion: Posicion): number {
  const puestos = PUESTOS[estado.formacion];
  const libres = estado.titulares.flatMap((t, i) => (t === null ? [i] : []));
  return libres.find((i) => puestos[i].rol === posicion) ?? libres[0] ?? -1;
}

/** Quita al jugador de titulares y suplentes (y la capitanía, si la tenía). */
function sinJugador(estado: EstadoAlineacion, jugadorId: number): EstadoAlineacion {
  return {
    ...estado,
    titulares: estado.titulares.map((t) => (t?.jugadorId === jugadorId ? null : t)),
    suplentes: estado.suplentes.filter((id) => id !== jugadorId),
    capitanId: estado.capitanId === jugadorId ? null : estado.capitanId,
  };
}

export type RolEnAlineacion = "titular" | "suplente" | "fuera";

export function rolDe(estado: EstadoAlineacion, jugadorId: number): RolEnAlineacion {
  if (estado.titulares.some((t) => t?.jugadorId === jugadorId)) return "titular";
  if (estado.suplentes.includes(jugadorId)) return "suplente";
  return "fuera";
}

export function cantidadTitulares(estado: EstadoAlineacion): number {
  return estado.titulares.filter((t) => t !== null).length;
}

/** Pone al jugador como titular, suplente o fuera de la convocatoria. */
export function asignar(
  estado: EstadoAlineacion,
  jugador: Jugador,
  destino: RolEnAlineacion,
): EstadoAlineacion {
  if (rolDe(estado, jugador.id) === destino) return estado;
  const base = sinJugador(estado, jugador.id);
  if (destino === "suplente") return { ...base, suplentes: [...base.suplentes, jugador.id] };
  if (destino === "fuera") return base;

  const puesto = puestoParaJugador(base, jugador.posicion);
  if (puesto === -1) return estado; // ya hay 11 titulares
  const { x, y } = PUESTOS[base.formacion][puesto];
  const titulares = [...base.titulares];
  titulares[puesto] = { jugadorId: jugador.id, x, y };
  return { ...base, titulares };
}

/** Cambia la formación: cada titular va al punto de su puesto en la nueva. */
export function cambiarFormacion(estado: EstadoAlineacion, formacion: Formacion): EstadoAlineacion {
  const puestos = PUESTOS[formacion];
  return {
    ...estado,
    formacion,
    titulares: estado.titulares.map((t, i) =>
      t === null ? null : { ...t, x: puestos[i].x, y: puestos[i].y },
    ),
  };
}

/** Vuelve a poner a todos los titulares en el punto de su puesto. */
export function reubicar(estado: EstadoAlineacion): EstadoAlineacion {
  return cambiarFormacion(estado, estado.formacion);
}

export function mover(
  estado: EstadoAlineacion,
  jugadorId: number,
  x: number,
  y: number,
): EstadoAlineacion {
  return {
    ...estado,
    titulares: estado.titulares.map((t) =>
      t?.jugadorId === jugadorId ? { ...t, x: redondear(x), y: redondear(y) } : t,
    ),
  };
}

export function marcarCapitan(estado: EstadoAlineacion, jugadorId: number): EstadoAlineacion {
  if (rolDe(estado, jugadorId) !== "titular") return estado;
  return { ...estado, capitanId: jugadorId };
}

/**
 * HU-14 · Criterio 3. Lista de problemas que impiden guardar; vacía si se
 * puede. Mismas reglas que el backend, con los mismos números en el mensaje.
 */
export function problemas(estado: EstadoAlineacion, plantel: readonly Jugador[]): string[] {
  const porId = new Map(plantel.map((j) => [j.id, j]));
  const lista: string[] = [];

  const titulares = estado.titulares.filter((t): t is Titular => t !== null);
  if (titulares.length !== TITULARES) {
    const faltan = TITULARES - titulares.length;
    lista.push(
      `${faltan === 1 ? "Falta 1 titular" : `Faltan ${faltan} titulares`} (hay ${titulares.length} de ${TITULARES}).`,
    );
  }

  const arqueros = titulares.filter((t) => porId.get(t.jugadorId)?.posicion === "ARQ").length;
  if (arqueros === 0) lista.push("Falta un arquero entre los titulares.");
  if (arqueros > 1) lista.push(`Tiene que haber un solo arquero titular (hay ${arqueros}).`);

  if (estado.capitanId === null) lista.push("Falta designar al capitán.");
  else if (rolDe(estado, estado.capitanId) !== "titular") {
    lista.push("El capitán tiene que ser titular.");
  }
  return lista;
}

/** Arma el cuerpo del PUT. Los suplentes no tienen punto: van al centro. */
export function aPedido(estado: EstadoAlineacion): AlineacionGuardar {
  const titulares: JugadorAlineado[] = estado.titulares
    .filter((t): t is Titular => t !== null)
    .map((t) => ({
      jugador_id: t.jugadorId,
      es_titular: true,
      es_capitan: t.jugadorId === estado.capitanId,
      pos_x: redondear(t.x),
      pos_y: redondear(t.y),
    }));
  const suplentes: JugadorAlineado[] = estado.suplentes.map((id) => ({
    jugador_id: id,
    es_titular: false,
    es_capitan: false,
    pos_x: 50,
    pos_y: 50,
  }));
  return { formacion: estado.formacion, jugadores: [...titulares, ...suplentes] };
}

/** Para saber si hay cambios sin guardar: dos estados con el mismo pedido son iguales. */
export function huella(estado: EstadoAlineacion): string {
  const pedido = aPedido(estado);
  const orden = (a: JugadorAlineado, b: JugadorAlineado) => a.jugador_id - b.jugador_id;
  return JSON.stringify({ ...pedido, jugadores: [...pedido.jugadores].sort(orden) });
}
