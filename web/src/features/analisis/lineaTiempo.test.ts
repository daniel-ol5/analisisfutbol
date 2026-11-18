import { describe, expect, it } from "vitest";
import {
  asignarFilas,
  contarPorTipo,
  duracionEje,
  ETIQUETA_TIPO,
  filtrarItems,
  formatoTiempo,
  ICONO_TIPO,
  indiceActivo,
  marcasEje,
  porcentajeEnEje,
  TIPOS_INICIALES,
} from "./lineaTiempo";
import type { ItemLineaTiempo } from "./types";

const item = (
  t: number,
  tipo: ItemLineaTiempo["tipo"],
  equipo: ItemLineaTiempo["equipo"] = "LOCAL",
): ItemLineaTiempo => ({
  t,
  minuto: Math.floor(t / 60),
  tipo,
  equipo,
  jugador_id: null,
  descripcion: tipo,
  origen: "CAMARA",
});

const items = [
  item(10, "PASE"),
  item(60, "GOL"),
  item(75, "PERDIDA", "VISITANTE"),
  item(200, "ROJA"),
];

describe("línea de tiempo", () => {
  it("formatea segundos de partido como MM:SS", () => {
    expect(formatoTiempo(0)).toBe("00:00");
    expect(formatoTiempo(75.9)).toBe("01:15");
    expect(formatoTiempo(6125)).toBe("102:05");
    expect(formatoTiempo(-3)).toBe("00:00");
  });

  it("los pases arrancan ocultos y los hitos visibles", () => {
    const visibles = filtrarItems(items, new Set(TIPOS_INICIALES), null);
    expect(visibles.map((i) => i.tipo)).toEqual(["GOL", "PERDIDA", "ROJA"]);
  });

  it("filtra por equipo", () => {
    const todos = new Set(items.map((i) => i.tipo));
    expect(filtrarItems(items, todos, "VISITANTE").map((i) => i.tipo)).toEqual(["PERDIDA"]);
  });

  it("cuenta por tipo", () => {
    expect(contarPorTipo([...items, item(300, "GOL")]).get("GOL")).toBe(2);
  });

  it("marca el último evento ocurrido en el instante dado", () => {
    expect(indiceActivo(items, 5)).toBe(-1);
    expect(indiceActivo(items, 60)).toBe(1);
    expect(indiceActivo(items, 199)).toBe(2);
    expect(indiceActivo(items, 9999)).toBe(3);
    expect(indiceActivo(items, null)).toBe(-1);
  });
});

describe("cronología horizontal (CU-47)", () => {
  it("todo tipo de evento tiene ícono y etiqueta", () => {
    for (const tipo of Object.keys(ETIQUETA_TIPO) as (keyof typeof ETIQUETA_TIPO)[]) {
      expect(ICONO_TIPO[tipo]).toBeTruthy();
    }
  });

  it("el eje cubre del minuto 0 al 90 como mínimo", () => {
    expect(duracionEje([])).toBe(90);
    expect(duracionEje(items)).toBe(90);
  });

  it("el eje se extiende más allá del 90 si hay eventos en el descuento", () => {
    expect(duracionEje([item(5400 + 30, "GOL")])).toBe(91); // 90:30
    expect(duracionEje([item(95 * 60 + 10, "GOL")])).toBe(96); // 95:10
    expect(duracionEje([item(89 * 60, "GOL")])).toBe(90);
  });

  it("ubica cada instante como porcentaje del eje y lo mantiene dentro", () => {
    expect(porcentajeEnEje(0, 90)).toBe(0);
    expect(porcentajeEnEje(2700, 90)).toBe(50); // minuto 45 de 90
    expect(porcentajeEnEje(5400, 90)).toBe(100);
    expect(porcentajeEnEje(9999, 90)).toBe(100);
    expect(porcentajeEnEje(-5, 90)).toBe(0);
    expect(porcentajeEnEje(60, 0)).toBe(0);
  });

  it("marca el eje cada 15 minutos y rotula «90+» cuando se extiende", () => {
    expect(marcasEje(90).map((m) => m.etiqueta)).toEqual([
      "0'",
      "15'",
      "30'",
      "45'",
      "60'",
      "75'",
      "90'",
    ]);
    const extendido = marcasEje(96);
    expect(extendido.at(-1)).toEqual({ minuto: 90, etiqueta: "90+" });
  });

  it("reparte las marcas cercanas en filas distintas para que no se tapen", () => {
    expect(asignarFilas([0, 0.1, 0.2, 5], 1, 3)).toEqual([0, 1, 2, 0]);
    expect(asignarFilas([10, 20, 30], 1, 3)).toEqual([0, 0, 0]);
  });

  it("al agotar las filas apila en la última en vez de inventar otra", () => {
    expect(asignarFilas([1, 1, 1, 1, 1], 2, 2)).toEqual([0, 1, 1, 1, 1]);
    expect(asignarFilas([], 1, 3)).toEqual([]);
  });
});
