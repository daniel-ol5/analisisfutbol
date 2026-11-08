/** Pruebas de la carga y el procesamiento de video  —  CU-27, CU-28 (T-062). */
import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import type { Partido } from "@/features/deportivo";

import type { Video } from "./types";
import {
  esElMismoArchivo,
  formatearBytes,
  formatearDuracion,
  formatearRestante,
  hayQueSeguirConsultando,
  partidosParaVideo,
  porcentajeSubida,
  problemaDelArchivo,
  sePuedeProcesar,
  SubidaPausada,
  subirPorTrozos,
  type ApiSubida,
} from "./videos";

function video(cambios: Partial<Video> = {}): Video {
  return {
    id: 1,
    partido_id: 3,
    modelo_id: null,
    archivo_url: "club-1/video-1.mp4",
    nombre: "fecha-12.mp4",
    tipo: "video/mp4",
    tamano_bytes: 100,
    bytes_recibidos: 0,
    duracion_s: null,
    fps: null,
    resolucion: null,
    estado: "CARGANDO",
    progreso_pct: 0,
    iniciado_en: null,
    tiempo_restante_s: null,
    mensaje_error: null,
    creado_en: "2026-11-09T10:00:00Z",
    procesado_en: null,
    ...cambios,
  };
}

function errorHttp(status: number): AxiosError {
  return new AxiosError("error", "ERR", undefined, undefined, {
    status,
    data: {},
  } as AxiosResponse);
}

const errorDeRed = () => new AxiosError("Network Error", "ERR_NETWORK");

/**
 * Servidor de mentira con la misma regla que el backend: cada trozo tiene que
 * empezar donde quedó la cuenta. `fallas` decide qué pasa en cada envío.
 */
function servidor(total: number, fallas: Array<"red" | "respuesta-perdida" | "500" | "422"> = []) {
  let recibidos = 0;
  const recibido = new Uint8Array(total);
  const envios: number[] = [];
  const estado = (): Video =>
    video({
      tamano_bytes: total,
      bytes_recibidos: recibidos,
      estado: recibidos === total ? "SUBIDO" : "CARGANDO",
    });
  const api: ApiSubida = {
    async enviarTrozo(_id, trozo, inicio, _total, onBytes) {
      envios.push(inicio);
      const falla = fallas.shift();
      if (falla === "red") throw errorDeRed();
      if (falla === "500") throw errorHttp(500);
      if (falla === "422") throw errorHttp(422);
      if (inicio !== recibidos) throw errorHttp(409);
      recibido.set(new Uint8Array(await trozo.arrayBuffer()), inicio);
      onBytes?.(trozo.size);
      recibidos = inicio + trozo.size;
      if (falla === "respuesta-perdida") throw errorDeRed(); // llegó, pero la respuesta no
      return estado();
    },
    async verVideo() {
      return estado();
    },
  };
  return { api, envios, recibido, estado };
}

const archivo = (n: number) => new Blob([Uint8Array.from({ length: n }, (_, i) => i % 251)]);
const sinEspera = async () => {};

describe("HU-24 · Criterio 1: el formato se valida antes de subir", () => {
  it.each([
    ["partido.mp4", "video/mp4"],
    ["Partido.MOV", "video/quicktime"],
    ["partido.mkv", ""],
    ["partido.mkv", "application/octet-stream"],
  ])("%s (%s) sirve", (name, type) => {
    expect(problemaDelArchivo({ name, type, size: 10 })).toBeNull();
  });

  it.each(["partido.avi", "partido.wmv", "notas.txt", "partido"])("%s se rechaza", (name) => {
    expect(problemaDelArchivo({ name, type: "", size: 10 })).toMatch(/Se aceptan MP4, MOV, MKV/);
  });

  it("un MIME que no corresponde a la extensión se rechaza", () => {
    expect(problemaDelArchivo({ name: "x.mp4", type: "image/png", size: 10 })).toMatch(
      /image\/png/,
    );
  });

  it("un archivo vacío se rechaza", () => {
    expect(problemaDelArchivo({ name: "x.mp4", type: "video/mp4", size: 0 })).toMatch(/vacío/);
  });

  it("para retomar hay que elegir el mismo archivo", () => {
    const v = video({ nombre: "fecha.mp4", tamano_bytes: 500 });
    expect(esElMismoArchivo({ name: "fecha.mp4", size: 500 }, v)).toBe(true);
    expect(esElMismoArchivo({ name: "fecha.mp4", size: 499 }, v)).toBe(false);
    expect(esElMismoArchivo({ name: "otra.mp4", size: 500 }, v)).toBe(false);
  });
});

describe("subida por trozos", () => {
  it("sube todo en trozos ordenados y el contenido llega intacto", async () => {
    const s = servidor(100);
    const progreso: number[] = [];
    const final = await subirPorTrozos(archivo(100), video(), s.api, {
      tamanoTrozo: 30,
      onProgreso: (b) => progreso.push(b),
    });
    expect(final.estado).toBe("SUBIDO");
    expect(s.envios).toEqual([0, 30, 60, 90]);
    expect(Array.from(s.recibido)).toEqual(Array.from({ length: 100 }, (_, i) => i % 251));
    expect(progreso).toEqual([...progreso].sort((a, b) => a - b)); // nunca retrocede
    expect(progreso.at(-1)).toBe(100);
  });

  it("retoma desde bytes_recibidos (una carga cortada)", async () => {
    // Otro día, con la página recargada: el servidor ya tenía 60 bytes.
    const s = servidor(100);
    await s.api.enviarTrozo(1, archivo(100).slice(0, 60), 0, 100);
    s.envios.length = 0;
    const final = await subirPorTrozos(archivo(100), s.estado(), s.api, { tamanoTrozo: 30 });
    expect(s.envios).toEqual([60, 90]);
    expect(final.estado).toBe("SUBIDO");
  });

  it("ante cortes de red reintenta el mismo trozo", async () => {
    const s = servidor(60, ["red", "500"]);
    const final = await subirPorTrozos(archivo(60), video({ tamano_bytes: 60 }), s.api, {
      tamanoTrozo: 30,
      esperar: sinEspera,
    });
    expect(final.estado).toBe("SUBIDO");
    expect(s.envios).toEqual([0, 0, 0, 30]);
  });

  it("si el trozo llegó pero la respuesta se perdió, no lo reenvía", async () => {
    const s = servidor(60, ["respuesta-perdida"]);
    const final = await subirPorTrozos(archivo(60), video({ tamano_bytes: 60 }), s.api, {
      tamanoTrozo: 30,
      esperar: sinEspera,
    });
    expect(final.estado).toBe("SUBIDO");
    expect(s.envios).toEqual([0, 30]);
  });

  it("si el servidor tiene otra cuenta (409), se alinea con él", async () => {
    const s = servidor(90);
    await s.api.enviarTrozo(1, archivo(90).slice(0, 30), 0, 90);
    s.envios.length = 0;
    // El cliente cree que va en 0, el servidor ya tiene 30.
    const final = await subirPorTrozos(archivo(90), video({ tamano_bytes: 90 }), s.api, {
      tamanoTrozo: 30,
    });
    expect(final.estado).toBe("SUBIDO");
    expect(s.envios).toEqual([0, 30, 60]);
  });

  it("después de varios fallos seguidos se rinde", async () => {
    const s = servidor(60, ["red", "red", "red"]);
    await expect(
      subirPorTrozos(archivo(60), video({ tamano_bytes: 60 }), s.api, {
        tamanoTrozo: 30,
        reintentos: 2,
        esperar: sinEspera,
      }),
    ).rejects.toThrow("Network Error");
  });

  it("un error del cliente (4xx) no se reintenta", async () => {
    const s = servidor(60, ["422"]);
    await expect(
      subirPorTrozos(archivo(60), video({ tamano_bytes: 60 }), s.api, { esperar: sinEspera }),
    ).rejects.toBeInstanceOf(AxiosError);
    expect(s.envios).toEqual([0]);
  });

  it("pausar corta la subida con SubidaPausada", async () => {
    const control = new AbortController();
    const s = servidor(100);
    const api: ApiSubida = {
      ...s.api,
      async enviarTrozo(...args) {
        const v = await s.api.enviarTrozo(...args);
        control.abort(); // el usuario pausa durante el primer trozo
        return v;
      },
    };
    await expect(
      subirPorTrozos(archivo(100), video(), api, { tamanoTrozo: 30, signal: control.signal }),
    ).rejects.toBeInstanceOf(SubidaPausada);
    expect(s.envios).toEqual([0]);
  });

  it("un archivo ilegible termina en ERROR sin lanzar", async () => {
    const api: ApiSubida = {
      enviarTrozo: async () =>
        video({ bytes_recibidos: 100, estado: "ERROR", mensaje_error: "no se pudo leer" }),
      verVideo: async () => video(),
    };
    const final = await subirPorTrozos(archivo(100), video(), api);
    expect(final.estado).toBe("ERROR");
  });
});

describe("procesamiento", () => {
  it("se consulta el estado solo mientras algo se procesa", () => {
    expect(hayQueSeguirConsultando([video({ estado: "SUBIDO" })])).toBe(false);
    expect(hayQueSeguirConsultando([video({ estado: "PROCESANDO" })])).toBe(true);
  });

  it.each([
    [video({ estado: "SUBIDO" }), true],
    [video({ estado: "PROCESADO" }), true],
    [video({ estado: "ERROR", duracion_s: 90 }), true], // falló el pipeline: se reintenta
    [video({ estado: "ERROR", duracion_s: null }), false], // archivo ilegible
    [video({ estado: "CARGANDO" }), false],
    [video({ estado: "PROCESANDO" }), false],
  ])("se puede procesar %#", (v, puede) => {
    expect(sePuedeProcesar(v)).toBe(puede);
  });

  it.each([
    [null, null],
    [0, "terminando"],
    [45, "menos de 1 min"],
    [12 * 60, "~12 min"],
    [80 * 60, "~1 h 20 min"],
    [120 * 60, "~2 h"],
  ])("tiempo restante %s → %s", (segundos, texto) => {
    expect(formatearRestante(segundos)).toBe(texto);
  });
});

describe("formatos", () => {
  it.each([
    [500, "500 B"],
    [2048, "2 KB"],
    [5.5 * 1024 ** 2, "5,5 MB"],
    [4.2 * 1024 ** 3, "4,2 GB"],
  ])("%s bytes → %s", (b, texto) => {
    expect(formatearBytes(b)).toBe(texto);
  });

  it.each([
    [65, "1:05"],
    [5400, "1:30:00"],
    [3725, "1:02:05"],
  ])("%s s → %s", (s, texto) => {
    expect(formatearDuracion(s)).toBe(texto);
  });

  it("el porcentaje de subida no llega a 100 antes de terminar", () => {
    expect(porcentajeSubida(0, 1000)).toBe(0);
    expect(porcentajeSubida(999, 1000)).toBe(99);
    expect(porcentajeSubida(1000, 1000)).toBe(100);
  });

  it("partidos con video: sin cancelados, el más reciente primero", () => {
    const p = (id: number, fecha: string, estado: Partido["estado"]) =>
      ({ id, fecha_hora: fecha, estado }) as Partido;
    const lista = partidosParaVideo([
      p(1, "2026-10-01T20:00:00Z", "ANALIZADO"),
      p(2, "2026-10-20T20:00:00Z", "CANCELADO"),
      p(3, "2026-11-01T20:00:00Z", "FINALIZADO"),
    ]);
    expect(lista.map((x) => x.id)).toEqual([3, 1]);
  });
});
