// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import type { MensajeWorker, PosicionDetectada } from "../types";
import { VisorVideoSincronizado } from "./VisorVideoSincronizado";

vi.mock("@/features/vision/api", () => ({
  listarVideos: vi.fn().mockResolvedValue([]),
  descargarArchivoVideo: vi.fn(),
  obtenerMuestrasVideo: vi.fn(),
}));

afterEach(cleanup);

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
});
