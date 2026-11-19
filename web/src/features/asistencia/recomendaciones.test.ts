import { describe, expect, it } from "vitest";

import { cuerpoValoracion } from "./api";
import { cifraLegible, esRecomendacion, incorporar, ordenarActivas } from "./recomendaciones";
import { rec } from "./ejemplos";

describe("lista de recomendaciones activas (T-090)", () => {
  it("como máximo 3, por prioridad y la más reciente primero", () => {
    const lista = ordenarActivas([
      rec(1, "BAJA"),
      rec(2, "MEDIA"),
      rec(3, "ALTA"),
      rec(4, "MEDIA", { t: 500 }),
      rec(5, "CRITICA"),
    ]);
    expect(lista.map((r) => r.id)).toEqual([5, 3, 4]);
  });

  it("las aplicadas y descartadas no son activas", () => {
    const lista = ordenarActivas([
      rec(1, "CRITICA", { estado: "APLICADA" }),
      rec(2, "ALTA", { estado: "DESCARTADA" }),
      rec(3, "BAJA", { estado: "VISTA" }),
    ]);
    expect(lista.map((r) => r.id)).toEqual([3]);
  });

  it("una nueva de la misma regla reemplaza a la anterior", () => {
    const lista = incorporar([rec(1, "MEDIA")], rec(9, "ALTA", { regla_id: 1 }));
    expect(lista.map((r) => r.id)).toEqual([9]);
  });

  it("una nueva de mayor prioridad desplaza a la de menor", () => {
    const lista = incorporar([rec(1, "ALTA"), rec(2, "MEDIA"), rec(3, "BAJA")], rec(4, "CRITICA"));
    expect(lista.map((r) => r.id)).toEqual([4, 1, 2]);
  });

  it("valida la forma de lo que llega por el WebSocket", () => {
    expect(esRecomendacion(rec(1, "ALTA"))).toBe(true);
    expect(esRecomendacion({ ...rec(1, "ALTA"), prioridad: "URGENTE" })).toBe(false);
    expect(esRecomendacion(null)).toBe(false);
  });
});

describe("cifras legibles", () => {
  it("muestra la métrica en español con su unidad y el umbral", () => {
    expect(cifraLegible({ metrica: "posesion_rival_pct", valor: 68.44, umbral: 65 })).toEqual({
      etiqueta: "Posesión rival",
      valor: "68,4 %",
      umbral: "65 %",
    });
    expect(cifraLegible({ metrica: "otra_cosa", valor: 2, umbral: null }).etiqueta).toBe("otra_cosa");
  });
});

describe("cuerpo de la valoración (T-091)", () => {
  it.each([
    ["UTIL", { util: true, aplicada: false }],
    ["NO_UTIL", { util: false, aplicada: false }],
    ["APLICADA", { util: null, aplicada: true }],
  ] as const)("%s", (opcion, esperado) => {
    expect(cuerpoValoracion(opcion, "  nota  ")).toEqual({ ...esperado, comentario: "nota" });
  });
});
