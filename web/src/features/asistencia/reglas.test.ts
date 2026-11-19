import { describe, expect, it } from "vitest";

import {
  FORMULARIO_NUEVO,
  aCondicionPlana,
  deCondicionPlana,
  describirCondicion,
  formatoEspera,
  formularioDesdeRegla,
  ordenarReglas,
  puedeGestionarReglas,
  textoResultadoPrueba,
  validarFormulario,
} from "./reglas";
import type { Regla } from "./types";

const regla = (extra: Partial<Regla> = {}): Regla => ({
  id: 1,
  club_id: null,
  nombre: "Bloque defensivo bajo",
  condicion: { y: [{ ">=": ["minuto", 5] }, { "<": ["altura_linea_m", 22] }] },
  plantilla_mensaje: "Adelantar la línea",
  plantilla_justificacion: "Línea a {altura_linea_m:.1f} m",
  prioridad: "MEDIA",
  cooldown_s: 300,
  activa: true,
  ...extra,
});

describe("describirCondicion", () => {
  it("traduce métricas y operadores, con la unidad junto al número", () => {
    expect(describirCondicion(regla().condicion)).toBe(
      "Minuto de partido ≥ 5 y Altura de la línea defensiva < 22 m",
    );
  });

  it("pone paréntesis a los grupos anidados", () => {
    const condicion = {
      o: [
        { ">=": ["rojas_propias", 1] },
        { y: [{ ">": ["posesion_rival_pct", 60] }, { "<": ["minuto", 80] }] },
      ],
    };
    expect(describirCondicion(condicion)).toBe(
      "Rojas propias ≥ 1 o (Posesión rival > 60 % y Minuto de partido < 80)",
    );
  });

  it("no revienta con una condición mal formada", () => {
    expect(describirCondicion({ entre: ["minuto", 5] })).toBe("Condición inválida");
    expect(describirCondicion(null)).toBe("Condición inválida");
  });
});

describe("formatoEspera", () => {
  it.each([
    [30, "30 s"],
    [300, "5 min"],
    [90, "1 min 30 s"],
    [3600, "1 h"],
  ])("%i s → %s", (segundos, texto) => {
    expect(formatoEspera(segundos)).toBe(texto);
  });
});

describe("ordenarReglas", () => {
  it("de mayor a menor prioridad y, a igual prioridad, por nombre", () => {
    const orden = ordenarReglas([
      regla({ id: 1, nombre: "Zeta", prioridad: "BAJA" }),
      regla({ id: 2, nombre: "Beta", prioridad: "MEDIA" }),
      regla({ id: 3, nombre: "Alfa", prioridad: "MEDIA" }),
      regla({ id: 4, nombre: "Expulsión", prioridad: "CRITICA" }),
    ]);
    expect(orden.map((r) => r.id)).toEqual([4, 3, 2, 1]);
  });
});

describe("puedeGestionarReglas", () => {
  it("solo ADMIN y DT", () => {
    expect(puedeGestionarReglas("ADMIN")).toBe(true);
    expect(puedeGestionarReglas("DT")).toBe(true);
    expect(puedeGestionarReglas("ANALISTA")).toBe(false);
    expect(puedeGestionarReglas(null)).toBe(false);
  });
});

describe("condición plana (formulario)", () => {
  it("ida y vuelta de una condición del catálogo", () => {
    const plana = aCondicionPlana(regla().condicion);
    expect(plana).toEqual({
      union: "y",
      comparaciones: [
        { metrica: "minuto", operador: ">=", valor: "5" },
        { metrica: "altura_linea_m", operador: "<", valor: "22" },
      ],
    });
    expect(deCondicionPlana(plana!)).toEqual(regla().condicion);
  });

  it("una comparación suelta también entra", () => {
    expect(aCondicionPlana({ ">=": ["rojas_propias", 1] })?.comparaciones).toHaveLength(1);
  });

  it("lo anidado o con métricas desconocidas se edita como JSON", () => {
    expect(aCondicionPlana({ o: [{ y: [{ "<": ["minuto", 5] }] }] })).toBeNull();
    expect(aCondicionPlana({ "<": ["otra_cosa", 5] })).toBeNull();
    expect(aCondicionPlana({ "<": [5, "minuto"] })).toBeNull();
    expect(formularioDesdeRegla(regla({ condicion: { o: [{ y: [] }] } })).condicion).toBeNull();
  });

  it("acepta coma decimal", () => {
    const condicion = deCondicionPlana({
      union: "o",
      comparaciones: [{ metrica: "altura_linea_m", operador: "<", valor: "22,5" }],
    });
    expect(condicion).toEqual({ o: [{ "<": ["altura_linea_m", 22.5] }] });
  });
});

describe("validarFormulario", () => {
  const completo = {
    ...FORMULARIO_NUEVO,
    nombre: " Línea baja ",
    plantilla_mensaje: "Adelantar la línea",
    espera_min: "2,5",
  };

  it("arma los datos para el backend, con la espera en segundos", () => {
    const resultado = validarFormulario(completo);
    expect(resultado.ok).toBe(true);
    if (!resultado.ok) return;
    expect(resultado.datos.nombre).toBe("Línea baja");
    expect(resultado.datos.cooldown_s).toBe(150);
    expect(resultado.datos.condicion).toEqual({ y: [{ ">=": ["minuto", 5] }] });
  });

  it("marca los campos obligatorios y la espera fuera de rango", () => {
    const resultado = validarFormulario({ ...FORMULARIO_NUEVO, espera_min: "0.2" });
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(Object.keys(resultado.errores).sort()).toEqual([
      "espera_min",
      "nombre",
      "plantilla_mensaje",
    ]);
  });

  it("exige un número en cada comparación", () => {
    const resultado = validarFormulario({
      ...completo,
      condicion: { union: "y", comparaciones: [{ metrica: "minuto", operador: ">=", valor: "" }] },
    });
    expect(resultado.ok || resultado.errores.comparaciones).toBe(
      "Cada comparación necesita un número.",
    );
  });

  it("en modo JSON valida que sea un objeto", () => {
    const enJson = { ...completo, condicion: null };
    expect(validarFormulario({ ...enJson, condicion_json: "[1, 2" }).ok).toBe(false);
    expect(validarFormulario({ ...enJson, condicion_json: "[1, 2]" }).ok).toBe(false);
    const ok = validarFormulario({ ...enJson, condicion_json: '{"<": ["minuto", 5]}' });
    expect(ok.ok && ok.datos.condicion).toEqual({ "<": ["minuto", 5] });
  });
});

describe("textoResultadoPrueba", () => {
  it("distingue 'sin datos' de 'no se disparó'", () => {
    expect(textoResultadoPrueba({ disparos: 0, minutos: [], evaluaciones: 0 })).toMatch(
      /no tiene posiciones guardadas/,
    );
    expect(textoResultadoPrueba({ disparos: 0, minutos: [], evaluaciones: 120 })).toBe(
      "No se habría disparado en ese partido.",
    );
  });

  it("lista los minutos sin repetir", () => {
    expect(textoResultadoPrueba({ disparos: 1, minutos: [6], evaluaciones: 50 })).toBe(
      "Se habría disparado 1 vez, en el minuto 6'.",
    );
    expect(textoResultadoPrueba({ disparos: 3, minutos: [5, 5, 12], evaluaciones: 50 })).toBe(
      "Se habría disparado 3 veces, en los minutos 5', 12'.",
    );
  });
});
