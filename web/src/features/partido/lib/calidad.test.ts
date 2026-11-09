import { describe, expect, it } from "vitest";

import {
  CADUCIDAD_TELEMETRIA_MS,
  DURACION_BALON_AUSENTE_MS,
  DURACION_JUGADORES_BAJO_MS,
  calcularLatenciaWsMs,
  contarTracksActivos,
  crearEstadoSupervisionCalidad,
  evaluarSupervisionCalidad,
  type MuestraSupervisionCalidad,
} from "./calidad";

const base: MuestraSupervisionCalidad = {
  canal: "CONECTADO",
  recibidaEnMs: 1_000,
  tracksActivos: 23,
  latenciaWsMs: 24,
  calidad: {
    worker_conectado: true,
    fps: 5,
    jugadores_detectados: 22,
    balon_visible: true,
    retraso_s: 0.2,
    degradado: false,
    motivo: null,
  },
};

function codigos(muestra: MuestraSupervisionCalidad, ahoraMs: number) {
  return evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), muestra, ahoraMs).alertas.map(
    (alerta) => alerta.codigo,
  );
}

describe("T-073 · supervisión de calidad", () => {
  it("calcula latencia ping/pong y tracks únicos de la muestra real", () => {
    expect(calcularLatenciaWsMs(100, 124.5)).toBe(24.5);
    expect(calcularLatenciaWsMs(200, 199)).toBe(0);
    expect(
      contarTracksActivos({
        jugadores: [{ tid: 1 }, { tid: 2 }, { tid: 2 }],
        balon: { tid: 0 },
      }),
    ).toBe(3);
    expect(contarTracksActivos({ jugadores: [{ tid: 1 }], balon: null })).toBe(1);
  });

  it("muestra el worker conectado sin alertas con telemetría normal", () => {
    const estado = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), base, 1_100);
    expect(estado.workerConectado).toBe(true);
    expect(estado.alertas).toEqual([]);
  });

  it("detecta canal caído, worker reportado desconectado y telemetría vencida", () => {
    expect(codigos({ ...base, canal: "SIN_CONEXION" }, 1_100)).toContain("WORKER_DESCONECTADO");
    expect(
      codigos({ ...base, calidad: { ...base.calidad!, worker_conectado: false } }, 1_100),
    ).toContain("WORKER_DESCONECTADO");
    expect(codigos(base, 1_000 + CADUCIDAD_TELEMETRIA_MS + 1)).toContain("WORKER_DESCONECTADO");
  });

  it("alerta inmediatamente si el FPS es inferior a 3 y se recupera", () => {
    const degradada = {
      ...base,
      calidad: { ...base.calidad!, fps: 2.9 },
    };
    const baja = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), degradada, 1_100);
    expect(baja.alertas.map((alerta) => alerta.codigo)).toContain("FPS_BAJO");

    const recuperada = evaluarSupervisionCalidad(baja, base, 1_200);
    expect(recuperada.alertas.map((alerta) => alerta.codigo)).not.toContain("FPS_BAJO");
  });

  it("exige 10 segundos continuos con menos de 16 jugadores", () => {
    const pocos = {
      ...base,
      calidad: { ...base.calidad!, jugadores_detectados: 15 },
    };
    const inicio = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), pocos, 1_000);
    const antes = evaluarSupervisionCalidad(
      inicio,
      { ...pocos, recibidaEnMs: 1_000 + DURACION_JUGADORES_BAJO_MS - 1 },
      1_000 + DURACION_JUGADORES_BAJO_MS - 1,
    );
    expect(antes.alertas.map((alerta) => alerta.codigo)).not.toContain("JUGADORES_BAJOS");

    const limite = evaluarSupervisionCalidad(
      antes,
      { ...pocos, recibidaEnMs: 1_000 + DURACION_JUGADORES_BAJO_MS },
      1_000 + DURACION_JUGADORES_BAJO_MS,
    );
    expect(limite.alertas.map((alerta) => alerta.codigo)).toContain("JUGADORES_BAJOS");

    const recuperada = evaluarSupervisionCalidad(
      limite,
      { ...base, recibidaEnMs: 1_001 + DURACION_JUGADORES_BAJO_MS },
      1_001 + DURACION_JUGADORES_BAJO_MS,
    );
    expect(recuperada.jugadoresBajosDesdeMs).toBeNull();
    expect(recuperada.alertas).toEqual([]);
  });

  it("exige 30 segundos continuos sin balón y limpia la alerta al recuperarlo", () => {
    const sinBalon = {
      ...base,
      calidad: { ...base.calidad!, balon_visible: false },
    };
    const inicio = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), sinBalon, 1_000);
    const antes = evaluarSupervisionCalidad(
      inicio,
      { ...sinBalon, recibidaEnMs: 1_000 + DURACION_BALON_AUSENTE_MS - 1 },
      1_000 + DURACION_BALON_AUSENTE_MS - 1,
    );
    expect(antes.alertas.map((alerta) => alerta.codigo)).not.toContain("BALON_AUSENTE");

    const limite = evaluarSupervisionCalidad(
      antes,
      { ...sinBalon, recibidaEnMs: 1_000 + DURACION_BALON_AUSENTE_MS },
      1_000 + DURACION_BALON_AUSENTE_MS,
    );
    expect(limite.alertas.map((alerta) => alerta.codigo)).toContain("BALON_AUSENTE");

    const recuperada = evaluarSupervisionCalidad(
      limite,
      { ...base, recibidaEnMs: 1_001 + DURACION_BALON_AUSENTE_MS },
      1_001 + DURACION_BALON_AUSENTE_MS,
    );
    expect(recuperada.balonAusenteDesdeMs).toBeNull();
    expect(recuperada.alertas).toEqual([]);
  });

  it("mantiene temporizadores independientes entre partidos", () => {
    const pocos = {
      ...base,
      calidad: { ...base.calidad!, jugadores_detectados: 10 },
    };
    const partidoA = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), pocos, 1_000);
    const partidoB = evaluarSupervisionCalidad(crearEstadoSupervisionCalidad(), base, 9_000);

    expect(partidoA.jugadoresBajosDesdeMs).toBe(1_000);
    expect(partidoB.jugadoresBajosDesdeMs).toBeNull();
  });
});
