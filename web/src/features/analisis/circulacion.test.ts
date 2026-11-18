import { describe, expect, it } from "vitest";
import {
  dentroDeCancha,
  flechasDeRed,
  geometriaFlecha,
  grosorEnlace,
  radioNodo,
} from "./circulacion";
import type { NodoPase } from "./types";

const nodo = (
  id: number,
  x: number,
  y: number,
  recibidos = 0,
  extra: Partial<NodoPase> = {},
): NodoPase => ({
  jugador_id: id,
  nombre: `J${id}`,
  dorsal: id,
  equipo: "LOCAL",
  x_medio: x,
  y_medio: y,
  pases: 0,
  pases_recibidos: recibidos,
  mayor_recepcion: false,
  aislado: false,
  ...extra,
});

describe("red de pases", () => {
  it("el grosor y el radio crecen con el peso y tienen tope", () => {
    expect(grosorEnlace(1, 10)).toBeLessThan(grosorEnlace(10, 10));
    expect(grosorEnlace(50, 10)).toBe(grosorEnlace(10, 10));
    expect(radioNodo(0, 0)).toBe(1.6);
    expect(radioNodo(8, 8)).toBeCloseTo(3.4);
  });

  it("recorta posiciones fuera de la cancha", () => {
    expect(dentroDeCancha({ x_medio: 120, y_medio: -2 })).toEqual({ x: 105, y: 0 });
  });
});

describe("flechas dirigidas", () => {
  it("la flecha sale del borde del origen y su punta cae en el borde del destino", () => {
    const g = geometriaFlecha({ x: 10, y: 20 }, { x: 40, y: 20 }, 2, 3, 1)!;
    expect(g.x1).toBeCloseTo(12); // 10 + radio del origen
    const punta = Number(g.cabeza.split(" ")[0].split(",")[0]);
    expect(punta).toBeCloseTo(37); // 40 - radio del destino
    expect(g.x2).toBeLessThan(punta); // la línea termina en la base de la cabeza
  });

  it("apunta hacia el destino: la cabeza queda del lado del destino", () => {
    const ida = geometriaFlecha({ x: 10, y: 20 }, { x: 40, y: 20 }, 2, 2, 1)!;
    const vuelta = geometriaFlecha({ x: 40, y: 20 }, { x: 10, y: 20 }, 2, 2, 1)!;
    expect(Number(ida.cabeza.split(" ")[0].split(",")[0])).toBeGreaterThan(30);
    expect(Number(vuelta.cabeza.split(" ")[0].split(",")[0])).toBeLessThan(20);
  });

  it("la ida y la vuelta de un par van separadas para no taparse", () => {
    const ida = geometriaFlecha({ x: 10, y: 20 }, { x: 40, y: 20 }, 2, 2, 1)!;
    const vuelta = geometriaFlecha({ x: 40, y: 20 }, { x: 10, y: 20 }, 2, 2, 1)!;
    expect(Math.abs(ida.y1 - vuelta.y1)).toBeGreaterThan(1); // más que el grosor: no se pisan
  });

  it("la separación crece con el grosor: dos flechas gruesas de un par tampoco se solapan", () => {
    const grosor = 2.2;
    const ida = geometriaFlecha({ x: 10, y: 20 }, { x: 40, y: 20 }, 2, 2, grosor)!;
    const vuelta = geometriaFlecha({ x: 40, y: 20 }, { x: 10, y: 20 }, 2, 2, grosor)!;
    expect(Math.abs(ida.y1 - vuelta.y1)).toBeGreaterThan(grosor);
  });

  it("no dibuja flecha si los nodos están casi encimados", () => {
    expect(geometriaFlecha({ x: 10, y: 10 }, { x: 12, y: 10 }, 2, 2, 1)).toBeNull();
  });

  it("una flecha por sentido, con grosor proporcional a los pases y las más fuertes encima", () => {
    const nodos = [nodo(1, 20, 30, 4), nodo(2, 60, 30, 9), nodo(3, 40, 10, 1)];
    const flechas = flechasDeRed(
      [
        { origen_id: 1, destino_id: 2, pases: 9 },
        { origen_id: 2, destino_id: 1, pases: 3 },
        { origen_id: 1, destino_id: 3, pases: 1 },
      ],
      nodos,
    );
    expect(flechas.map((f) => f.pases)).toEqual([1, 3, 9]); // de menos a más: la gruesa queda arriba
    expect(flechas.map((f) => f.grosor)).toEqual(
      [...flechas.map((f) => f.grosor)].sort((a, b) => a - b),
    );
    expect(flechas[2].grosor).toBeGreaterThan(flechas[1].grosor);
    expect(flechas[2]).toMatchObject({ origen_id: 1, destino_id: 2 });
  });

  it("descarta las conexiones con menos pases que el mínimo y las de nodos desconocidos", () => {
    const nodos = [nodo(1, 20, 30), nodo(2, 60, 30)];
    const flechas = flechasDeRed(
      [
        { origen_id: 1, destino_id: 2, pases: 5 },
        { origen_id: 2, destino_id: 1, pases: 1 },
        { origen_id: 1, destino_id: 99, pases: 8 },
      ],
      nodos,
      2,
    );
    expect(flechas.map((f) => f.pases)).toEqual([5]);
  });

  it("sin conexiones no hay flechas", () => {
    expect(flechasDeRed([], [nodo(1, 20, 30)])).toEqual([]);
  });
});
