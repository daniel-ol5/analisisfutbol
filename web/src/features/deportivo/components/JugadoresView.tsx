import { useState, useMemo, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listarEquipos,
  listarJugadores,
  crearJugador,
  editarJugador,
  bajaJugador,
  importarPlantel,
  exportarJugadoresCsv,
} from "../api";
import { JugadorCard } from "./JugadorCard";
import { JugadorFormModal } from "./JugadorFormModal";
import { ImportarCsvModal } from "./ImportarCsvModal";
import type {
  Jugador,
  JugadorCrear,
  JugadorEditar,
  OrdenJugadores,
  ResultadoImportacion,
} from "../types";

const ETIQUETAS_ORDEN: Record<OrdenJugadores, string> = {
  dorsal: "Dorsal",
  posicion: "Posición",
  apellido: "Apellido",
};

export function JugadoresView() {
  const queryClient = useQueryClient();
  const [equipoId, setEquipoId] = useState<number | null>(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [orden, setOrden] = useState<OrdenJugadores>("dorsal");

  const [modalFormAbierto, setModalFormAbierto] = useState(false);
  const [jugadorAEditar, setJugadorAEditar] = useState<Jugador | null>(null);

  const [modalImportarAbierto, setModalImportarAbierto] = useState(false);
  const [archivoImportar, setArchivoImportar] = useState<File | null>(null);
  const [resultadoImportar, setResultadoImportar] = useState<ResultadoImportacion | null>(null);
  const [importado, setImportado] = useState(false);

  const [exportando, setExportando] = useState(false);

  // Consulta de equipos del club para el selector de plantel
  const { data: equipos = [] } = useQuery({
    queryKey: ["equipos", { activos: true }],
    queryFn: () => listarEquipos(true),
    retry: 1,
  });

  // Selecciona automáticamente el primer equipo disponible
  useEffect(() => {
    if (equipoId === null && equipos.length > 0) {
      setEquipoId(equipos[0].id);
    }
  }, [equipos, equipoId]);

  // Consulta del plantel del equipo seleccionado
  const {
    data: jugadores = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["jugadores", equipoId, { activos: !mostrarInactivos, orden }],
    queryFn: () => listarJugadores(equipoId as number, !mostrarInactivos, orden),
    enabled: equipoId !== null,
    retry: 1,
  });

  const mutationCrear = useMutation({
    mutationFn: (datos: JugadorCrear) => crearJugador(datos),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jugadores", equipoId] });
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
      setModalFormAbierto(false);
    },
  });

  const mutationEditar = useMutation({
    mutationFn: ({ id, datos }: { id: number; datos: JugadorEditar }) => editarJugador(id, datos),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jugadores", equipoId] });
      setModalFormAbierto(false);
      setJugadorAEditar(null);
    },
  });

  const mutationBaja = useMutation({
    mutationFn: (id: number) => bajaJugador(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jugadores", equipoId] });
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
    },
  });

  const mutationPreviewImportar = useMutation({
    mutationFn: (archivo: File) => importarPlantel(equipoId as number, archivo, false),
    onSuccess: (datos) => setResultadoImportar(datos),
  });

  const mutationConfirmarImportar = useMutation({
    mutationFn: (archivo: File) => importarPlantel(equipoId as number, archivo, true),
    onSuccess: (datos) => {
      setResultadoImportar(datos);
      setImportado(true);
      queryClient.invalidateQueries({ queryKey: ["jugadores", equipoId] });
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
    },
  });

  const jugadoresFiltrados = useMemo(() => {
    return jugadores.filter((j) => {
      const texto = `${j.nombre} ${j.apellido}`.toLowerCase();
      return texto.includes(busqueda.toLowerCase());
    });
  }, [jugadores, busqueda]);

  const handleGuardarForm = async (datos: JugadorCrear | JugadorEditar) => {
    if (jugadorAEditar) {
      await mutationEditar.mutateAsync({ id: jugadorAEditar.id, datos });
    } else {
      await mutationCrear.mutateAsync(datos as JugadorCrear);
    }
  };

  const handleBaja = async (jugador: Jugador) => {
    const seguro = window.confirm(
      `¿Estás seguro de dar de baja a "${jugador.nombre} ${jugador.apellido}" (#${jugador.dorsal})?\n` +
        `Se mantendrán todas sus métricas históricas.`,
    );
    if (seguro) {
      await mutationBaja.mutateAsync(jugador.id);
    }
  };

  const handleSeleccionarArchivoImportar = (archivo: File) => {
    setArchivoImportar(archivo);
    setImportado(false);
    setResultadoImportar(null);
    mutationPreviewImportar.mutate(archivo);
  };

  const handleConfirmarImportar = () => {
    if (archivoImportar) mutationConfirmarImportar.mutate(archivoImportar);
  };

  const handleExportarCsv = async () => {
    if (equipoId === null) return;
    setExportando(true);
    try {
      const blob = await exportarJugadoresCsv(equipoId, !mostrarInactivos, orden);
      const url = URL.createObjectURL(blob);
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download = `plantel_equipo_${equipoId}.csv`;
      enlace.click();
      URL.revokeObjectURL(url);
    } finally {
      setExportando(false);
    }
  };

  const handleCerrarImportar = () => {
    setModalImportarAbierto(false);
    setArchivoImportar(null);
    setResultadoImportar(null);
    setImportado(false);
    mutationPreviewImportar.reset();
    mutationConfirmarImportar.reset();
  };

  if (equipos.length === 0) {
    return (
      <div
        style={{
          textAlign: "center",
          padding: 48,
          background: "var(--surface)",
          border: "1px dashed var(--line)",
          borderRadius: 8,
        }}
      >
        <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>👟</span>
        <h4 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
          Aún no hay equipos registrados en el club.
        </h4>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--text-2)" }}>
          Registra primero un equipo en la pestaña "Equipos e Indumentaria" para poder gestionar su
          plantel.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Alerta si falla la carga */}
      {isError && (
        <div
          style={{
            padding: "16px 20px",
            background: "rgba(162, 55, 42, 0.08)",
            border: "1.5px solid var(--risk)",
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <strong style={{ fontSize: 14, color: "var(--risk)" }}>
              Error al consultar el plantel del equipo
            </strong>
            <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--text-2)" }}>
              {(error as any)?.response?.data?.detail ??
                "No se pudo conectar con el servicio de Gestión Deportiva."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "7px 14px",
              fontSize: 12.5,
              fontWeight: 700,
              color: "#ffffff",
              background: "var(--risk)",
              borderRadius: 6,
            }}
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Barra de herramientas: Selector de equipo, Búsqueda, Filtros y Botón Nuevo Jugador */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          padding: 16,
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", flex: 1 }}>
          <select
            value={equipoId ?? ""}
            onChange={(e) => setEquipoId(Number(e.target.value))}
            style={{
              padding: "8px 12px",
              fontSize: 13,
              fontWeight: 600,
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: "var(--ground)",
              color: "var(--text)",
              outline: "none",
            }}
          >
            {equipos.map((eq) => (
              <option key={eq.id} value={eq.id}>
                {eq.nombre} {eq.categoria ? `· ${eq.categoria}` : ""}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Buscar por nombre o apellido…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            style={{
              minWidth: 220,
              flex: 1,
              padding: "8px 12px",
              fontSize: 13,
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: "var(--ground)",
              color: "var(--text)",
              outline: "none",
            }}
          />

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12.5,
              color: "var(--text-2)",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Ver inactivos
          </label>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12.5,
              color: "var(--text-2)",
            }}
          >
            Ordenar por
            <select
              value={orden}
              onChange={(e) => setOrden(e.target.value as OrdenJugadores)}
              style={{
                padding: "6px 10px",
                fontSize: 12.5,
                fontWeight: 600,
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--ground)",
                color: "var(--text)",
                outline: "none",
              }}
            >
              {Object.entries(ETIQUETAS_ORDEN).map(([valor, etiqueta]) => (
                <option key={valor} value={valor}>
                  {etiqueta}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button
            type="button"
            disabled={equipoId === null || exportando || jugadoresFiltrados.length === 0}
            onClick={handleExportarCsv}
            style={{
              all: "unset",
              cursor: exportando ? "wait" : "pointer",
              padding: "9px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text)",
              background: "var(--ground)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              whiteSpace: "nowrap",
              opacity: equipoId === null || jugadoresFiltrados.length === 0 ? 0.5 : 1,
            }}
          >
            {exportando ? "Exportando…" : "Exportar CSV"}
          </button>

          <button
            type="button"
            disabled={equipoId === null}
            onClick={() => setModalImportarAbierto(true)}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "9px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text)",
              background: "var(--ground)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              whiteSpace: "nowrap",
            }}
          >
            Importar CSV
          </button>

          <button
            type="button"
            disabled={equipoId === null}
            onClick={() => {
              setJugadorAEditar(null);
              setModalFormAbierto(true);
            }}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "9px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: "#ffffff",
              background: "var(--pitch)",
              borderRadius: 6,
              boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
              whiteSpace: "nowrap",
            }}
          >
            + Registrar Nuevo Jugador
          </button>
        </div>
      </div>

      {/* Grid de Jugadores */}
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-3)", fontSize: 14 }}>
          Cargando plantel…
        </div>
      ) : jugadoresFiltrados.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 48,
            background: "var(--surface)",
            border: "1px dashed var(--line)",
            borderRadius: 8,
          }}
        >
          <span style={{ fontSize: 36, display: "block", marginBottom: 8 }}>👟</span>
          <h4 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
            {busqueda
              ? "No se encontraron jugadores que coincidan con la búsqueda."
              : "Aún no hay jugadores registrados en este equipo."}
          </h4>
          <p style={{ margin: "6px 0 16px", fontSize: 13, color: "var(--text-2)" }}>
            Comienza registrando el primer jugador del plantel con su dorsal y ficha física.
          </p>
          <button
            type="button"
            onClick={() => {
              setJugadorAEditar(null);
              setModalFormAbierto(true);
            }}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: 700,
              color: "#ffffff",
              background: "var(--pitch)",
              borderRadius: 6,
            }}
          >
            + Registrar Primer Jugador
          </button>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))",
            gap: 16,
          }}
        >
          {jugadoresFiltrados.map((jugador) => (
            <JugadorCard
              key={jugador.id}
              jugador={jugador}
              onEditar={(j) => {
                setJugadorAEditar(j);
                setModalFormAbierto(true);
              }}
              onBaja={handleBaja}
            />
          ))}
        </div>
      )}

      {/* Modal de Alta / Edición de jugador */}
      {equipoId !== null && (
        <JugadorFormModal
          abierto={modalFormAbierto}
          equipoId={equipoId}
          jugadorAEditar={jugadorAEditar}
          cargando={mutationCrear.isPending || mutationEditar.isPending}
          onCerrar={() => {
            setModalFormAbierto(false);
            setJugadorAEditar(null);
          }}
          onGuardar={handleGuardarForm}
        />
      )}

      {/* Modal de importación CSV */}
      <ImportarCsvModal
        abierto={modalImportarAbierto}
        equipoId={equipoId}
        resultado={resultadoImportar}
        importado={importado}
        cargandoPreview={mutationPreviewImportar.isPending}
        cargandoConfirmar={mutationConfirmarImportar.isPending}
        error={
          ((mutationPreviewImportar.error ?? mutationConfirmarImportar.error) as any)?.response
            ?.data?.detail ?? null
        }
        onSeleccionarArchivo={handleSeleccionarArchivoImportar}
        onConfirmar={handleConfirmarImportar}
        onCerrar={handleCerrarImportar}
      />
    </div>
  );
}
