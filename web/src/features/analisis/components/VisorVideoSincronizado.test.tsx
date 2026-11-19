// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { descargarArchivoVideo, listarVideos, obtenerMuestrasVideo, verVideo } from "@/features/vision/api";
import type { Video } from "@/features/vision/types";
import type { MensajeWorker, PosicionDetectada } from "../types";
import { VisorVideoSincronizado } from "./VisorVideoSincronizado";

vi.mock("@/features/vision/api", () => ({
  listarVideos: vi.fn().mockResolvedValue([]),
  descargarArchivoVideo: vi.fn(),
  obtenerMuestrasVideo: vi.fn(),
  verVideo: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("la grabación muestra el balón validado y excluye candidatos de la grada", async () => {
  const arbitro: PosicionDetectada = { tid: 7, equipo: "ARBITRO", x: 30, y: 20, conf: 0.9 };
  const muestra: MensajeWorker = {
    partido: 1, t: 33, jugadores: [arbitro], balon: null,
    detecciones: [
      { tid: 7, clase: "JUGADOR", conf: 0.9, bbox: [25, 30, 27, 45] },
      { tid: 8, clase: "JUGADOR", conf: 0.9, bbox: [5, 5, 8, 12] },
      { tid: 9, clase: "BALON", conf: 0.6, bbox: [90, 10, 91, 11] },
    ],
    calidad: { worker_conectado: true, fps: 5, jugadores_detectados: 0, balon_visible: false,
      retraso_s: 0, degradado: true, calibracion_valida: true },
  };
  const noop = () => {};
  const visor = (balon: PosicionDetectada | null) => (
    <MemoryRouter>
      <VisorVideoSincronizado partidoId={1} jugadores={muestra.jugadores} balon={balon} muestra={muestra}
        workerTransmitiendo={false} modoDisposicion="paralelo" onCambiarModoDisposicion={noop}
        onMuestraSincronizada={noop} onCambiarFuente={noop} />
    </MemoryRouter>
  );
  const vista = render(visor(null));
  await act(async () => {});
  fireEvent.click(screen.getByLabelText("Mostrar detecciones"));
  expect(screen.getByText("Árbitro 7")).toBeTruthy();
  expect(screen.queryByText(/ 8$/)).toBeNull();
  expect(screen.queryByText("Balón")).toBeNull();

  vista.rerender(visor({ tid: 0, equipo: "DESCONOCIDO", x: 40, y: 25, conf: 0.92, bbox: [40, 51, 41, 52] }));
  expect(screen.getByText("Balón").parentElement?.style.left).toBe("40%");

  muestra.calidad.calibracion_valida = false;
  vista.rerender(visor(null));
  expect(screen.queryByText("Árbitro 7")).toBeNull();
  expect(screen.getByText(/Referencia de cancha perdida/)).toBeTruthy();
});

test("actualiza el análisis por lotes sin descargar de nuevo el video", async () => {
  vi.useFakeTimers();
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:clip");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const clip: Video = {
    id: 6, partido_id: 1, modelo_id: null, archivo_url: "", nombre: "Partido.mp4",
    tipo: "video/mp4", tamano_bytes: 10, bytes_recibidos: 10, duracion_s: 60,
    fps: 25, resolucion: "1920x1080", estado: "PROCESANDO", progreso_pct: 0,
    iniciado_en: "2026-11-19T12:00:00Z", tiempo_restante_s: null,
    mensaje_error: null, creado_en: "2026-11-19T11:00:00Z", procesado_en: null,
  };
  const muestra: MensajeWorker = {
    partido: 1, t: 5, jugadores: [], balon: null,
    calidad: { worker_conectado: true, fps: 5, jugadores_detectados: 0, balon_visible: false,
      retraso_s: 0, degradado: true },
  };
  vi.mocked(listarVideos).mockResolvedValueOnce([clip]);
  vi.mocked(verVideo).mockResolvedValueOnce({ ...clip, progreso_pct: 10 })
    .mockResolvedValueOnce({ ...clip, progreso_pct: 20 });
  vi.mocked(descargarArchivoVideo).mockClear().mockResolvedValueOnce(new Blob());
  vi.mocked(obtenerMuestrasVideo).mockClear().mockResolvedValueOnce([muestra])
    .mockResolvedValueOnce([{ ...muestra, t: 10 }]);
  const noop = () => {};
  const vista = render(<MemoryRouter><VisorVideoSincronizado partidoId={1} videoInicialId={6} jugadores={[]}
    workerTransmitiendo={false} modoDisposicion="paralelo" onCambiarModoDisposicion={noop}
    onMuestraSincronizada={noop} onCambiarFuente={noop} /></MemoryRouter>);

  await act(async () => {});
  expect(screen.getByRole("status").textContent).toContain("0:05 · 10 %");
  const reproductor = vista.container.querySelector("video")!;
  Object.defineProperty(reproductor, "readyState", { value: 2 });
  const reproducir = vi.spyOn(reproductor, "play").mockResolvedValue(undefined);
  const pausar = vi.spyOn(reproductor, "pause").mockImplementation(() => {});
  fireEvent.loadedData(reproductor);
  expect(reproducir).toHaveBeenCalledOnce();
  reproductor.currentTime = 6;
  fireEvent.timeUpdate(reproductor);
  expect(pausar).toHaveBeenCalledOnce();
  expect(reproductor.currentTime).toBe(5);

  await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
  expect(screen.getByRole("status").textContent).toContain("0:10 · 20 %");
  expect(reproducir).toHaveBeenCalledTimes(2);
  expect(obtenerMuestrasVideo).toHaveBeenLastCalledWith(6, expect.any(AbortSignal), 5);
  expect(descargarArchivoVideo).toHaveBeenCalledTimes(1);
});
