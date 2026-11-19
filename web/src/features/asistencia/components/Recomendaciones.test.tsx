// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { rec } from "../ejemplos";
import { RecomendacionesEnVivo } from "./RecomendacionesEnVivo";
import { TarjetaRecomendacion } from "./TarjetaRecomendacion";

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  listarRecomendaciones: vi.fn(),
  marcarVista: vi.fn(),
  valorarRecomendacion: vi.fn(),
}));

vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  obtenerTokenAcceso: () => "token-de-prueba",
  obtenerRolActual: () => "DT",
}));

const mockApi = vi.mocked(api);

beforeEach(() => {
  mockApi.marcarVista.mockResolvedValue(rec(1, "ALTA", { estado: "VISTA" }));
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const conCifras = rec(7, "CRITICA", {
  minuto: 63,
  mensaje: "Adelanta la línea defensiva",
  justificacion: "El rival tuvo el 68 % de la posesión observada.",
  datos_soporte: [
    { metrica: "posesion_rival_pct", valor: 68.4, umbral: 65 },
    { metrica: "altura_linea_m", valor: 19.25, umbral: 22 },
  ],
});

describe("TarjetaRecomendacion (T-090)", () => {
  it("muestra prioridad, minuto, justificación y las cifras reales contra el umbral", () => {
    render(<TarjetaRecomendacion recomendacion={conCifras} />);
    const tarjeta = screen.getByTestId("tarjeta-recomendacion");
    expect(within(tarjeta).getByText("Prioridad Crítica")).toBeTruthy();
    expect(tarjeta.className).toContain("rec-tarjeta--critica");
    expect(within(tarjeta).getByText("Min 63'")).toBeTruthy();
    expect(within(tarjeta).getByText("Adelanta la línea defensiva")).toBeTruthy();
    expect(within(tarjeta).getByText("Posesión rival")).toBeTruthy();
    expect(within(tarjeta).getByText("68,4 %")).toBeTruthy();
    expect(within(tarjeta).getByText(/umbral 65 %/)).toBeTruthy();
    expect(within(tarjeta).getByText("19,3 m")).toBeTruthy();
    expect(within(tarjeta).getByText(/umbral 22 m/)).toBeTruthy();
  });

  it("al mostrarse por primera vez la marca como vista, una sola vez", () => {
    const { rerender } = render(<TarjetaRecomendacion recomendacion={conCifras} />);
    rerender(<TarjetaRecomendacion recomendacion={conCifras} />);
    expect(mockApi.marcarVista).toHaveBeenCalledTimes(1);
    expect(mockApi.marcarVista).toHaveBeenCalledWith(7);
  });

  it("solo lectura: sin botones y sin marcar vista", () => {
    render(<TarjetaRecomendacion recomendacion={conCifras} soloLectura />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(mockApi.marcarVista).not.toHaveBeenCalled();
  });
});

describe("Valoración en la tarjeta (T-091)", () => {
  it("envía la opción y el comentario, y bloquea los botones mostrando lo elegido", async () => {
    const alValorar = vi.fn();
    const devuelta = rec(7, "CRITICA", { estado: "DESCARTADA", util: false });
    mockApi.valorarRecomendacion.mockResolvedValue(devuelta);
    render(<TarjetaRecomendacion recomendacion={conCifras} alValorar={alValorar} />);

    fireEvent.change(screen.getByLabelText("Comentario (opcional)"), {
      target: { value: "El rival ya estaba cansado" },
    });
    fireEvent.click(screen.getByRole("button", { name: "No útil" }));

    expect(await screen.findByText("Valorada: No útil")).toBeTruthy();
    expect(mockApi.valorarRecomendacion).toHaveBeenCalledWith(7, "NO_UTIL", "El rival ya estaba cansado");
    for (const nombre of ["Útil", "No útil", "Aplicada"]) {
      expect((screen.getByRole("button", { name: nombre }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(screen.getByRole("button", { name: "No útil" }).getAttribute("aria-pressed")).toBe("true");
    expect(alValorar).toHaveBeenCalledWith(devuelta);
  });

  it("un error se muestra con el mensaje de errors.ts y deja volver a intentar", async () => {
    mockApi.valorarRecomendacion.mockRejectedValue(new Error("sin red"));
    render(<TarjetaRecomendacion recomendacion={conCifras} />);
    fireEvent.click(screen.getByRole("button", { name: "Útil" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Útil" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("una recomendación ya valorada llega con los botones bloqueados", () => {
    render(
      <TarjetaRecomendacion recomendacion={rec(3, "ALTA", { estado: "VISTA", util: true })} />,
    );
    expect(screen.getByText("Valorada: Útil")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Aplicada" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

// ---------------- WebSocket /vivo ----------------

class SocketFalso {
  static ultimo: SocketFalso | null = null;
  enviados: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    SocketFalso.ultimo = this;
  }
  send(datos: string) {
    this.enviados.push(datos);
  }
  close() {}
  recibir(mensaje: unknown) {
    act(() => this.onmessage?.({ data: JSON.stringify(mensaje) }));
  }
}

function montar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={cliente}>
      <RecomendacionesEnVivo
        partidoId={42}
        crearSocket={(url) => new SocketFalso(url) as unknown as WebSocket}
      />
    </QueryClientProvider>,
  );
}

describe("Recomendaciones en vivo (T-090)", () => {
  it("una recomendación que llega por WebSocket aparece en la lista, priorizada", async () => {
    mockApi.listarRecomendaciones.mockResolvedValue([rec(1, "BAJA", { mensaje: "Mantén la calma" })]);
    montar();
    expect(await screen.findByText("Mantén la calma")).toBeTruthy();

    const ws = SocketFalso.ultimo as SocketFalso;
    expect(ws.url).toMatch(/\/partido\/42\/vivo$/);
    act(() => ws.onopen?.());
    expect(JSON.parse(ws.enviados[0])).toEqual({ tipo: "auth", token: "token-de-prueba" });
    ws.recibir({ tipo: "listo", partido: 42 });
    expect(await screen.findByText("En vivo")).toBeTruthy();

    ws.recibir({
      tipo: "recomendacion",
      datos: rec(2, "CRITICA", { mensaje: "Reorganiza el bloque tras la expulsión" }),
    });
    await waitFor(() => expect(screen.getAllByTestId("tarjeta-recomendacion")).toHaveLength(2));
    const mensajes = screen.getAllByTestId("tarjeta-recomendacion").map((t) => t.textContent);
    expect(mensajes[0]).toContain("Reorganiza el bloque tras la expulsión");
    expect(mensajes[1]).toContain("Mantén la calma");
  });

  it("nunca muestra más de 3 y descarta mensajes de otro partido", async () => {
    mockApi.listarRecomendaciones.mockResolvedValue([rec(1, "ALTA"), rec(2, "MEDIA"), rec(3, "BAJA")]);
    montar();
    await waitFor(() => expect(screen.getAllByTestId("tarjeta-recomendacion")).toHaveLength(3));
    const ws = SocketFalso.ultimo as SocketFalso;
    ws.recibir({ tipo: "recomendacion", datos: rec(4, "CRITICA", { mensaje: "Nueva crítica" }) });
    ws.recibir({ tipo: "recomendacion", datos: rec(5, "CRITICA", { partido_id: 99 }) });

    expect(await screen.findByText("Nueva crítica")).toBeTruthy();
    expect(screen.getAllByTestId("tarjeta-recomendacion")).toHaveLength(3);
    expect(screen.queryByText("Recomendación 3")).toBeNull();   // la BAJA quedó afuera
    expect(screen.queryByText("Recomendación 5")).toBeNull();
  });

  it("si el canal se cae, avisa que no está en vivo", async () => {
    mockApi.listarRecomendaciones.mockResolvedValue([]);
    montar();
    const ws = SocketFalso.ultimo as SocketFalso;
    ws.recibir({ tipo: "listo", partido: 42 });
    expect(await screen.findByText("En vivo")).toBeTruthy();
    act(() => ws.onclose?.({ code: 1006 }));
    expect(await screen.findByText("Sin conexión en vivo")).toBeTruthy();
  });
});
