// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AxiosError, AxiosHeaders } from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { cerrarAsistente } from "../estado";
import type { Progreso, Respuesta } from "../types";
import { BotonAsistente } from "./BotonAsistente";
import { AVISO_ALCANCE, PREGUNTAS_PANTALLA } from "../constantes";
import { BotonComoSeUsa } from "./BotonComoSeUsa";
import { PanelAsistente } from "./PanelAsistente";

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  obtenerProgreso: vi.fn(),
  preguntar: vi.fn(),
}));

const mockApi = vi.mocked(api);

const progreso: Progreso = {
  plataforma: "web",
  partido_id: 10,
  asistente_activo: true,
  pasos: [
    { clave: "club", titulo: "Registrar el club", estado: "hecho", ruta: null, solo_web: false,
      disponible: true, tu_rol_puede: true, nota: null },
    { clave: "equipo", titulo: "Crear el equipo y sus colores", estado: "hecho",
      ruta: "/deportivo/equipos", solo_web: false, disponible: true, tu_rol_puede: true, nota: null },
    { clave: "calibracion", titulo: "Calibrar la cámara", estado: "pendiente",
      ruta: "/vision/calibracion?partidoId=10", solo_web: true, disponible: true,
      tu_rol_puede: true, nota: null },
    { clave: "informe", titulo: "Informe del partido", estado: "pendiente", ruta: null,
      solo_web: false, disponible: false, tu_rol_puede: false,
      nota: "Esta función todavía no está disponible en Área Técnica." },
  ],
  siguiente: null,
};
progreso.siguiente = progreso.pasos[2];

function montar(preguntaInicial: string | null = null) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <PanelAsistente
          usuarioId={1}
          pantallaActual="/vision/calibracion"
          preguntaInicial={preguntaInicial}
          onCerrar={() => undefined}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function errorHttp(status: number, detail: string) {
  const headers = new AxiosHeaders();
  return new AxiosError("fallo", "ERR", { headers }, null, {
    status, statusText: "", headers: {}, config: { headers }, data: { detail },
  });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  sessionStorage.clear();
  cerrarAsistente();
});

describe("PanelAsistente", () => {
  it("muestra el progreso con los pasos y el botón para ir al siguiente", async () => {
    mockApi.obtenerProgreso.mockResolvedValue(progreso);
    montar();
    const seccion = await screen.findByRole("region", { name: /Tu progreso/ });
    expect(within(seccion).getByText("2 de 3")).toBeTruthy();
    expect(within(seccion).getAllByRole("listitem")).toHaveLength(4);
    expect(within(seccion).getByText("Siguiente paso:").parentElement?.textContent).toContain(
      "Calibrar la cámara",
    );
    expect(within(seccion).getByText("Informe del partido")).toBeTruthy();
    const ir = within(seccion).getByRole("link", { name: "Ir al siguiente paso" });
    expect(ir.getAttribute("href")).toBe("/vision/calibracion?partidoId=10");
    expect(screen.getByText(AVISO_ALCANCE)).toBeTruthy();
  });

  it("si el siguiente paso no tiene pantalla, muestra la nota en vez del botón", async () => {
    const soloWeb = { ...progreso.pasos[2], ruta: null, nota: "Lo hace un Administrador o Analista." };
    mockApi.obtenerProgreso.mockResolvedValue({ ...progreso, siguiente: soloWeb });
    montar();
    expect(await screen.findByText("Lo hace un Administrador o Analista.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Ir al siguiente paso" })).toBeNull();
  });

  it("envía la pregunta y muestra la respuesta con sus acciones", async () => {
    mockApi.obtenerProgreso.mockResolvedValue(progreso);
    let responder: (r: Respuesta) => void = () => undefined;
    mockApi.preguntar.mockImplementation(() => new Promise((ok) => (responder = ok)));
    montar();

    fireEvent.change(screen.getByLabelText("Tu pregunta"), {
      target: { value: "¿Cómo calibro la cámara?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("El asistente está escribiendo…")).toBeTruthy();
    expect(mockApi.preguntar.mock.calls[0][0]).toEqual({
      pregunta: "¿Cómo calibro la cámara?",
      pantalla_actual: "/vision/calibracion",
      plataforma: "web",
      historial: [],
    });
    responder({
      respuesta: "1. Abre Visión y video.\n2. Entra a Calibración.",
      acciones: [{ texto: "Ir a calibrar", ruta: "/vision/calibracion?partidoId=10" }],
    });

    expect(await screen.findByText(/Abre Visión y video/)).toBeTruthy();
    const accion = screen.getByRole("link", { name: "Ir a calibrar" });
    expect(accion.getAttribute("href")).toBe("/vision/calibracion?partidoId=10");
    expect(screen.getByText("¿Cómo calibro la cámara?")).toBeTruthy();
    expect(screen.queryByText("El asistente está escribiendo…")).toBeNull();
    // El historial queda en la sesión de la pestaña.
    expect(sessionStorage.getItem("areatecnica.asistente.1")).toContain("Abre Visión y video");
  });

  it("muestra el error de la API de forma amable", async () => {
    mockApi.obtenerProgreso.mockResolvedValue(progreso);
    mockApi.preguntar.mockRejectedValue(
      errorHttp(429, "Llegaste al límite de 30 preguntas por hoy. Vuelve a intentarlo mañana."),
    );
    montar();
    fireEvent.change(screen.getByLabelText("Tu pregunta"), { target: { value: "¿Siguiente?" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    const alerta = await screen.findByText(/Llegaste al límite de 30 preguntas/);
    expect(alerta.closest(".ui-alerta")?.textContent).toContain("No pudimos responder");
  });

  it("si la IA está apagada avisa y deja el progreso", async () => {
    mockApi.obtenerProgreso.mockResolvedValue({ ...progreso, asistente_activo: false });
    montar();
    expect(await screen.findByText(/El chat no está disponible/)).toBeTruthy();
    expect(screen.queryByLabelText("Tu pregunta")).toBeNull();
    expect(screen.getByRole("region", { name: /Tu progreso/ })).toBeTruthy();
  });

  it("«¿Cómo se usa esto?» abre el asistente y envía sola la pregunta de la pantalla", async () => {
    mockApi.obtenerProgreso.mockResolvedValue(progreso);
    mockApi.preguntar.mockResolvedValue({ respuesta: "1. Marca los puntos.", acciones: [] });
    const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={cliente}>
        <MemoryRouter initialEntries={["/vision/calibracion"]}>
          <BotonComoSeUsa pantalla="calibracion" />
          <BotonAsistente />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "¿Cómo se usa esto?" }));

    expect(await screen.findByRole("dialog", { name: "Asistente" })).toBeTruthy();
    await waitFor(() => expect(mockApi.preguntar).toHaveBeenCalledTimes(1));
    expect(mockApi.preguntar.mock.calls[0][0]).toMatchObject({
      pregunta: PREGUNTAS_PANTALLA.calibracion,
      pantalla_actual: "/vision/calibracion",
    });
    expect(await screen.findByText("1. Marca los puntos.")).toBeTruthy();
  });

  it("el botón flotante abre y cierra el panel", async () => {
    mockApi.obtenerProgreso.mockResolvedValue(progreso);
    const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={cliente}>
        <MemoryRouter>
          <BotonAsistente />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Abrir el asistente de uso" }));
    expect(await screen.findByRole("dialog", { name: "Asistente" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cerrar asistente" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mockApi.preguntar).not.toHaveBeenCalled();
  });
});
