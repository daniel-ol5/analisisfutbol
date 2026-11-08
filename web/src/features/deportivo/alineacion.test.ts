/** Pruebas del editor de alineación  —  CU-17 · T-051 (HU-14). */
import { describe, expect, it } from "vitest";

import {
  PUESTOS,
  TITULARES,
  aPedido,
  alineacionVacia,
  asignar,
  cambiarFormacion,
  cantidadTitulares,
  estadoDesdeAlineacion,
  huella,
  marcarCapitan,
  mover,
  nombrePartido,
  partidoEditable,
  problemas,
  puedeEditarAlineacion,
  reubicar,
  rolDe,
  type EstadoAlineacion,
} from "./alineacion";
import { FORMACIONES, type Alineacion, type Jugador, type Partido, type Posicion } from "./types";

/** Plantel de 14: 2 arqueros (1 y 12), 4 DEF, 4 MED (6-8 y 13), 3 DEL, y uno más (14). */
const POSICIONES: Posicion[] = [
  "ARQ",
  "DEF",
  "DEF",
  "DEF",
  "DEF",
  "MED",
  "MED",
  "MED",
  "DEL",
  "DEL",
  "DEL",
  "ARQ",
  "MED",
  "DEF",
];
const plantel: Jugador[] = POSICIONES.map((posicion, i) => ({
  id: i + 1,
  equipo_id: 1,
  nombre: `N${i + 1}`,
  apellido: `A${i + 1}`,
  dorsal: i + 1,
  posicion,
  pie_habil: "DER",
  altura_cm: 180,
  peso_kg: null,
  fecha_nacimiento: null,
  activo: true,
}));
const jugador = (id: number) => plantel[id - 1];

/** Los 11 primeros como titulares (un solo arquero), 12 y 13 al banco, 5 capitán. */
function alineacionCompleta(): EstadoAlineacion {
  let e = alineacionVacia();
  for (const j of plantel.slice(0, 11)) e = asignar(e, j, "titular");
  e = asignar(e, jugador(12), "suplente");
  e = asignar(e, jugador(13), "suplente");
  return marcarCapitan(e, 5);
}

describe("formaciones", () => {
  it.each(FORMACIONES)("%s tiene 11 puestos, el arquero en el 0 y dentro de la cancha", (f) => {
    const puestos = PUESTOS[f];
    expect(puestos).toHaveLength(TITULARES);
    expect(puestos[0].rol).toBe("ARQ");
    expect(puestos.filter((p) => p.rol === "ARQ")).toHaveLength(1);
    for (const p of puestos) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(100);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(100);
    }
  });

  it("la cantidad de jugadores por línea coincide con el nombre", () => {
    for (const f of FORMACIONES) {
      const lineas = f.split("-").map(Number);
      const campo = PUESTOS[f].slice(1);
      expect(campo).toHaveLength(lineas.reduce((a, b) => a + b, 0));
      expect(campo.filter((p) => p.rol === "DEF")).toHaveLength(lineas[0]);
      expect(campo.filter((p) => p.rol === "DEL")).toHaveLength(lineas[lineas.length - 1]);
    }
  });
});

describe("asignar jugadores", () => {
  it("cada titular va a un puesto libre de su posición", () => {
    const e = alineacionCompleta();
    expect(cantidadTitulares(e)).toBe(11);
    expect(e.titulares[0]?.jugadorId).toBe(1); // el arquero, al arco
    const puestos = PUESTOS[e.formacion];
    e.titulares.forEach((t, i) => {
      expect(jugador(t!.jugadorId).posicion).toBe(puestos[i].rol);
    });
  });

  it("no entra un titular número 12", () => {
    const e = alineacionCompleta();
    expect(asignar(e, jugador(14), "titular")).toBe(e);
    expect(rolDe(e, 14)).toBe("fuera");
  });

  it("si no queda puesto de su posición, ocupa cualquiera libre", () => {
    let e = alineacionCompleta();
    e = asignar(e, jugador(9), "fuera"); // libera un puesto de DEL
    e = asignar(e, jugador(14), "titular"); // un DEF
    expect(rolDe(e, 14)).toBe("titular");
    expect(cantidadTitulares(e)).toBe(11);
  });

  it("pasar de titular a suplente y a fuera mueve al jugador", () => {
    let e = alineacionCompleta();
    e = asignar(e, jugador(8), "suplente");
    expect(rolDe(e, 8)).toBe("suplente");
    expect(cantidadTitulares(e)).toBe(10);
    e = asignar(e, jugador(8), "fuera");
    expect(rolDe(e, 8)).toBe("fuera");
    expect(e.suplentes).not.toContain(8);
  });

  it("el capitán que sale del once pierde la capitanía", () => {
    const e = asignar(alineacionCompleta(), jugador(5), "suplente");
    expect(e.capitanId).toBeNull();
  });

  it("solo un titular puede ser capitán", () => {
    const e = alineacionCompleta();
    expect(marcarCapitan(e, 12)).toBe(e); // suplente
    expect(marcarCapitan(e, 9).capitanId).toBe(9);
  });
});

describe("HU-14 · Criterio 3: reglas antes de guardar", () => {
  it("una alineación completa no tiene problemas", () => {
    expect(problemas(alineacionCompleta(), plantel)).toEqual([]);
  });

  it("una alineación vacía pide titulares, arquero y capitán", () => {
    expect(problemas(alineacionVacia(), plantel)).toEqual([
      "Faltan 11 titulares (hay 0 de 11).",
      "Falta un arquero entre los titulares.",
      "Falta designar al capitán.",
    ]);
  });

  it("con 10 titulares lo dice en singular", () => {
    const e = asignar(alineacionCompleta(), jugador(8), "fuera");
    expect(problemas(e, plantel)).toContain("Falta 1 titular (hay 10 de 11).");
  });

  it("dos arqueros titulares no se pueden guardar", () => {
    let e = asignar(alineacionCompleta(), jugador(2), "fuera");
    e = asignar(e, jugador(12), "titular");
    expect(problemas(e, plantel)).toEqual(["Tiene que haber un solo arquero titular (hay 2)."]);
  });

  it("sin arquero titular no se puede guardar", () => {
    let e = asignar(alineacionCompleta(), jugador(1), "fuera");
    e = asignar(e, jugador(14), "titular");
    expect(problemas(e, plantel)).toEqual(["Falta un arquero entre los titulares."]);
  });
});

describe("HU-14 · Criterio 2: posiciones en la cancha", () => {
  it("mover redondea a un decimal y no sale de la cancha", () => {
    const e = mover(alineacionCompleta(), 2, 150, -3.33);
    const t = e.titulares.find((x) => x?.jugadorId === 2)!;
    expect([t.x, t.y]).toEqual([100, 0]);
    const f = mover(e, 2, 33.333, 66.666);
    const u = f.titulares.find((x) => x?.jugadorId === 2)!;
    expect([u.x, u.y]).toEqual([33.3, 66.7]);
  });

  it("cambiar de formación conserva los titulares y los pone en sus puestos", () => {
    const e = cambiarFormacion(alineacionCompleta(), "3-5-2");
    expect(e.formacion).toBe("3-5-2");
    expect(cantidadTitulares(e)).toBe(11);
    e.titulares.forEach((t, i) => {
      expect([t!.x, t!.y]).toEqual([PUESTOS["3-5-2"][i].x, PUESTOS["3-5-2"][i].y]);
    });
  });

  it("reubicar deshace lo que se movió a mano", () => {
    const original = alineacionCompleta();
    const movida = mover(original, 9, 90, 90);
    expect(huella(reubicar(movida))).toBe(huella(original));
  });
});

describe("pedido al backend", () => {
  it("11 titulares con su punto, un capitán y los suplentes", () => {
    const pedido = aPedido(alineacionCompleta());
    expect(pedido.formacion).toBe("4-3-3");
    expect(pedido.jugadores).toHaveLength(13);
    expect(pedido.jugadores.filter((j) => j.es_titular)).toHaveLength(11);
    expect(pedido.jugadores.filter((j) => j.es_capitan).map((j) => j.jugador_id)).toEqual([5]);
    const suplentes = pedido.jugadores.filter((j) => !j.es_titular);
    expect(suplentes.map((j) => j.jugador_id)).toEqual([12, 13]);
    for (const j of pedido.jugadores) {
      expect(j.pos_x).toBeGreaterThanOrEqual(0);
      expect(j.pos_x).toBeLessThanOrEqual(100);
    }
  });

  it("al recargar lo guardado no aparecen cambios sin guardar", () => {
    const e = mover(alineacionCompleta(), 9, 72.5, 41);
    const respuesta: Alineacion = {
      id: 1,
      partido_id: 9,
      formacion: e.formacion,
      jugadores: aPedido(e).jugadores.map((j) => {
        const { nombre, apellido, dorsal, posicion } = jugador(j.jugador_id);
        return { ...j, nombre, apellido, dorsal, posicion };
      }),
    };
    const { estado, descartados } = estadoDesdeAlineacion(respuesta, plantel);
    expect(descartados).toEqual([]);
    expect(huella(estado)).toBe(huella(e));
  });

  it("descarta y avisa de los jugadores que ya no están en el plantel", () => {
    const respuesta: Alineacion = {
      id: 1,
      partido_id: 9,
      formacion: "4-4-2",
      jugadores: [
        {
          jugador_id: 99,
          es_titular: false,
          es_capitan: false,
          pos_x: 50,
          pos_y: 50,
          nombre: "X",
          apellido: "Ajeno",
          dorsal: 99,
          posicion: "MED",
        },
      ],
    };
    const { estado, descartados } = estadoDesdeAlineacion(respuesta, plantel);
    expect(descartados.map((j) => j.apellido)).toEqual(["Ajeno"]);
    expect(estado.suplentes).toEqual([]);
    expect(estado.formacion).toBe("4-4-2");
  });
});

describe("permisos", () => {
  it.each([
    ["ADMIN", true],
    ["DT", true],
    ["ASISTENTE", true],
    ["ANALISTA", false],
    [undefined, false],
  ] as const)("el rol %s puede editar: %s", (rol, puede) => {
    expect(puedeEditarAlineacion(rol)).toBe(puede);
  });

  it.each([
    ["PROGRAMADO", true],
    ["EN_CURSO", true],
    ["FINALIZADO", false],
    ["PROCESANDO", false],
    ["ANALIZADO", false],
    ["CANCELADO", false],
  ] as const)("un partido %s se puede editar: %s", (estado, editable) => {
    expect(partidoEditable({ estado })).toBe(editable);
  });
});

it("el nombre del partido empieza por el rival", () => {
  const p = { rival: "Bolívar", fecha_hora: "2026-11-15T20:00:00Z" } as Partido;
  expect(nombrePartido(p)).toMatch(/^vs Bolívar · /);
});
