import { useCallback, useEffect, useMemo, useState } from "react";
import {
  crearEquipo,
  desactivarEquipo,
  editarEquipo,
  listarEquipos,
} from "../api";
import type { Equipo, EquipoCrear } from "../types";
import { EquipoCard } from "./EquipoCard";
import { EquipoFormModal } from "./EquipoFormModal";
import { JerseyPreview } from "./JerseyPreview";

interface EquiposViewProps {
  onIrIndumentaria?: (equipoId?: number) => void;
}

export function EquiposView({ onIrIndumentaria }: EquiposViewProps) {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState<string>("TODAS");

  // Estados de modales CRUD
  const [modalFormAbierto, setModalFormAbierto] = useState(false);
  const [equipoAEditar, setEquipoAEditar] = useState<Equipo | null>(null);
  const [equipoAVer, setEquipoAVer] = useState<Equipo | null>(null);
  const [equipoConfirmarEstado, setEquipoConfirmarEstado] = useState<{
    equipo: Equipo;
    accion: "desactivar" | "reactivar";
  } | null>(null);
  const [procesandoEstado, setProcesandoEstado] = useState(false);

  const cargarEquipos = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarEquipos(!mostrarInactivos);
      setEquipos(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo cargar el listado de equipos.";
      setError(msg);
    } finally {
      setCargando(false);
    }
  }, [mostrarInactivos]);

  useEffect(() => {
    void cargarEquipos();
  }, [cargarEquipos]);

  const categoriasUnicas = useMemo(() => {
    const set = new Set<string>();
    equipos.forEach((eq) => {
      if (eq.categoria?.trim()) set.add(eq.categoria.trim());
    });
    return ["TODAS", ...Array.from(set)];
  }, [equipos]);

  const equiposFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return equipos.filter((eq) => {
      const coincideCat =
        categoriaFiltro === "TODAS" || eq.categoria === categoriaFiltro;
      const coincideTexto =
        !q ||
        eq.nombre.toLowerCase().includes(q) ||
        eq.categoria.toLowerCase().includes(q) ||
        eq.temporada.toLowerCase().includes(q);
      return coincideCat && coincideTexto;
    });
  }, [equipos, busqueda, categoriaFiltro]);

  const kpis = useMemo(() => {
    const total = equipos.length;
    const activos = equipos.filter((e) => e.activo).length;
    const totalJugadores = equipos.reduce((acc, e) => acc + e.jugadores, 0);
    return { total, activos, totalJugadores };
  }, [equipos]);

  const handleAbrirCrear = () => {
    setEquipoAEditar(null);
    setModalFormAbierto(true);
  };

  const handleAbrirEditar = (equipo: Equipo) => {
    setEquipoAEditar(equipo);
    setModalFormAbierto(true);
  };

  const handleGuardarFormulario = async (
    datos: EquipoCrear & { activo?: boolean },
  ) => {
    if (equipoAEditar) {
      await editarEquipo(equipoAEditar.id, datos);
    } else {
      await crearEquipo(datos);
    }
    await cargarEquipos();
  };

  const handleConfirmarCambioEstado = async () => {
    if (!equipoConfirmarEstado) return;
    setProcesandoEstado(true);
    try {
      const { equipo, accion } = equipoConfirmarEstado;
      if (accion === "desactivar") {
        await desactivarEquipo(equipo.id);
      } else {
        await editarEquipo(equipo.id, { activo: true });
      }
      setEquipoConfirmarEstado(null);
      if (equipoAVer?.id === equipo.id) {
        setEquipoAVer(null);
      }
      await cargarEquipos();
    } catch (err: unknown) {
      alert(
        err instanceof Error
          ? err.message
          : "Error al cambiar el estado del equipo.",
      );
    } finally {
      setProcesandoEstado(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Barra de KPIs de Equipos */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
          gap: 12,
        }}
      >
        <div
          style={{
            padding: "14px 18px",
            borderRadius: 10,
            background: "var(--surface)",
            border: "1px solid var(--line)",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
            }}
          >
            Equipos Registrados
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: "var(--text)",
              marginTop: 4,
            }}
          >
            {kpis.total}
          </div>
        </div>

        <div
          style={{
            padding: "14px 18px",
            borderRadius: 10,
            background: "var(--surface)",
            border: "1px solid var(--line)",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
            }}
          >
            Equipos Activos
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: "var(--pitch)",
              marginTop: 4,
            }}
          >
            {kpis.activos}
          </div>
        </div>

        <div
          style={{
            padding: "14px 18px",
            borderRadius: 10,
            background: "var(--surface)",
            border: "1px solid var(--line)",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
            }}
          >
            Futbolistas en Planteles
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: "var(--text)",
              marginTop: 4,
            }}
          >
            {kpis.totalJugadores}
          </div>
        </div>
      </div>

      {/* Barra Superior de Búsqueda, Filtros y Alta */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          padding: "14px 18px",
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            flex: 1,
          }}
        >
          <input
            type="search"
            placeholder="Buscar por nombre, división o temporada..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: "var(--ground)",
              color: "var(--text)",
              fontSize: 13,
              minWidth: 260,
            }}
          />

          <select
            value={categoriaFiltro}
            onChange={(e) => setCategoriaFiltro(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: "var(--ground)",
              color: "var(--text)",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {categoriasUnicas.map((cat) => (
              <option key={cat} value={cat}>
                {cat === "TODAS" ? "Todas las categorías" : cat}
              </option>
            ))}
          </select>

          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12.5,
              color: "var(--text-2)",
              cursor: "pointer",
              userSelect: "none",
              fontWeight: 600,
            }}
          >
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
              style={{ cursor: "pointer" }}
            />
            Ver también dados de baja
          </label>
        </div>

        <button
          type="button"
          onClick={handleAbrirCrear}
          style={{
            padding: "9px 18px",
            borderRadius: 6,
            border: "none",
            background: "var(--pitch)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            boxShadow: "0 2px 6px rgba(13, 148, 136, 0.25)",
          }}
        >
          Registrar Equipo
        </button>
      </div>

      {/* Contenido / Grid de Tarjetas */}
      {cargando ? (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--text-3)",
            fontSize: 14,
          }}
        >
          Cargando equipos del club...
        </div>
      ) : error ? (
        <div
          style={{
            padding: 20,
            borderRadius: 8,
            background: "rgba(224, 112, 92, 0.1)",
            border: "1px solid var(--risk)",
            color: "var(--risk)",
            fontSize: 13.5,
          }}
        >
          {error}
        </div>
      ) : equiposFiltrados.length === 0 ? (
        <div
          style={{
            padding: "48px 24px",
            textAlign: "center",
            background: "var(--surface)",
            border: "1px dashed var(--line)",
            borderRadius: 10,
          }}
        >
          <h4 style={{ margin: "0 0 6px", fontSize: 16 }}>
            {equipos.length === 0
              ? "Aún no hay equipos registrados en el club"
              : "No hay equipos que coincidan con el filtro"}
          </h4>
          <p
            style={{
              margin: "0 0 18px",
              fontSize: 13,
              color: "var(--text-2)",
            }}
          >
            {equipos.length === 0
              ? "Crea tu primer equipo (ej. Primera División, Reserva o Sub-17) para gestionar su plantel y partidos."
              : "Prueba ajustando el texto de búsqueda o la categoría seleccionada."}
          </p>
          {equipos.length === 0 && (
            <button
              type="button"
              onClick={handleAbrirCrear}
              style={{
                padding: "9px 18px",
                borderRadius: 6,
                border: "none",
                background: "var(--pitch)",
                color: "#fff",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Crear Primer Equipo
            </button>
          )}
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))",
            gap: 18,
          }}
        >
          {equiposFiltrados.map((eq) => (
            <EquipoCard
              key={eq.id}
              equipo={eq}
              onVer={(equipo) => setEquipoAVer(equipo)}
              onEditar={handleAbrirEditar}
              onDesactivar={(equipo) =>
                setEquipoConfirmarEstado({ equipo, accion: "desactivar" })
              }
              onReactivar={(equipo) =>
                setEquipoConfirmarEstado({ equipo, accion: "reactivar" })
              }
              onIrIndumentaria={(equipo) => onIrIndumentaria?.(equipo.id)}
            />
          ))}
        </div>
      )}

      {/* Modal de Alta / Edición de Equipo (CU-09) */}
      <EquipoFormModal
        abierto={modalFormAbierto}
        equipoEditar={equipoAEditar}
        onCerrar={() => setModalFormAbierto(false)}
        onGuardar={handleGuardarFormulario}
      />

      {/* Modal de Visualización / Ficha Técnica del Equipo */}
      {equipoAVer && (
        <div
          className="modal-backdrop"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(15, 22, 18, 0.6)",
            backdropFilter: "blur(3px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 20,
          }}
          onClick={() => setEquipoAVer(null)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: 12,
              width: "100%",
              maxWidth: 520,
              padding: 24,
              boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
              display: "flex",
              flexDirection: "column",
              gap: 18,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                borderBottom: "1px solid var(--line)",
                paddingBottom: 14,
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11.5,
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: "rgba(13, 148, 136, 0.14)",
                      color: "var(--pitch)",
                    }}
                  >
                    EQ-{String(equipoAVer.id).padStart(2, "0")}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "2px 8px",
                      borderRadius: 99,
                      background: equipoAVer.activo
                        ? "rgba(13, 148, 136, 0.14)"
                        : "rgba(224, 112, 92, 0.15)",
                      color: equipoAVer.activo ? "var(--pitch)" : "var(--risk)",
                    }}
                  >
                    {equipoAVer.activo ? "ACTIVO" : "INACTIVO"}
                  </span>
                </div>
                <h3 style={{ margin: "8px 0 0", fontSize: 21 }}>
                  {equipoAVer.nombre}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEquipoAVer(null)}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  fontSize: 18,
                  color: "var(--text-3)",
                  padding: "4px 8px",
                }}
              >
                ✕
              </button>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
                padding: 16,
                borderRadius: 8,
                background: "var(--ground)",
                border: "1px solid var(--line)",
              }}
            >
              <div style={{ gridColumn: "1 / -1" }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--text-3)",
                    textTransform: "uppercase",
                  }}
                >
                  Categoría / Competición
                </div>
                <div
                  style={{
                    fontSize: 14.5,
                    fontWeight: 700,
                    color: "var(--text)",
                    marginTop: 2,
                  }}
                >
                  {equipoAVer.categoria || "Categoría General"}
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--text-3)",
                    textTransform: "uppercase",
                  }}
                >
                  Temporada
                </div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: "var(--text)",
                    marginTop: 2,
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {equipoAVer.temporada || "2026"}
                </div>
              </div>

              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--text-3)",
                    textTransform: "uppercase",
                  }}
                >
                  Jugadores en Plantel
                </div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 800,
                    color: "var(--pitch)",
                    marginTop: 2,
                  }}
                >
                  {equipoAVer.jugadores} activos
                </div>
              </div>
            </div>

            {/* Resumen compacto de indumentaria con enlace a CU-10 */}
            <div
              style={{
                padding: 14,
                borderRadius: 8,
                background: "var(--ground)",
                border: "1px solid var(--line)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <JerseyPreview
                  color={equipoAVer.color_local}
                  size="sm"
                  etiqueta="Titular"
                />
                <JerseyPreview
                  color={equipoAVer.color_visitante}
                  size="sm"
                  etiqueta="Visita"
                />
                <JerseyPreview
                  color={equipoAVer.color_arquero}
                  size="sm"
                  etiqueta="Arquero"
                />
              </div>

              {onIrIndumentaria && (
                <button
                  type="button"
                  onClick={() => {
                    const id = equipoAVer.id;
                    setEquipoAVer(null);
                    onIrIndumentaria(id);
                  }}
                  style={{
                    padding: "7px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--pitch)",
                    background: "rgba(13, 148, 136, 0.1)",
                    color: "var(--pitch)",
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Configurar indumentaria (CU-10)
                </button>
              )}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderTop: "1px solid var(--line)",
                paddingTop: 14,
                gap: 8,
              }}
            >
              {equipoAVer.activo ? (
                <button
                  type="button"
                  onClick={() =>
                    setEquipoConfirmarEstado({
                      equipo: equipoAVer,
                      accion: "desactivar",
                    })
                  }
                  style={{
                    padding: "8px 14px",
                    borderRadius: 6,
                    border: "1px solid rgba(224, 112, 92, 0.4)",
                    background: "rgba(224, 112, 92, 0.08)",
                    color: "var(--risk)",
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Dar de baja
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    setEquipoConfirmarEstado({
                      equipo: equipoAVer,
                      accion: "reactivar",
                    })
                  }
                  style={{
                    padding: "8px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--pitch)",
                    background: "var(--pitch)",
                    color: "#fff",
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Reactivar equipo
                </button>
              )}

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => {
                    const eq = equipoAVer;
                    setEquipoAVer(null);
                    handleAbrirEditar(eq);
                  }}
                  style={{
                    padding: "8px 16px",
                    borderRadius: 6,
                    border: "none",
                    background: "var(--pitch)",
                    color: "#fff",
                    fontSize: 12.5,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  Editar datos
                </button>
                <button
                  type="button"
                  onClick={() => setEquipoAVer(null)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "transparent",
                    color: "var(--text-2)",
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Cerrar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Confirmación de Baja Lógica / Reactivación */}
      {equipoConfirmarEstado && (
        <div
          className="modal-backdrop"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(15, 22, 18, 0.65)",
            backdropFilter: "blur(3px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1050,
            padding: 20,
          }}
          onClick={() => setEquipoConfirmarEstado(null)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: 10,
              width: "100%",
              maxWidth: 440,
              padding: 24,
              boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: 0, fontSize: 18 }}>
              {equipoConfirmarEstado.accion === "desactivar"
                ? `¿Dar de baja a "${equipoConfirmarEstado.equipo.nombre}"?`
                : `¿Reactivar a "${equipoConfirmarEstado.equipo.nombre}"?`}
            </h3>
            <p
              style={{
                margin: 0,
                fontSize: 13.5,
                color: "var(--text-2)",
                lineHeight: 1.5,
              }}
            >
              {equipoConfirmarEstado.accion === "desactivar"
                ? "El equipo pasará a estado inactivo pero conservará intactos su plantel histórico, partidos y métricas tácticas. Podrás reactivarlo en cualquier momento."
                : "El equipo volverá a estar activo para programar partidos, gestionar alineaciones y registrar indumentaria."}
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 10,
                marginTop: 8,
              }}
            >
              <button
                type="button"
                onClick={() => setEquipoConfirmarEstado(null)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 6,
                  border: "1px solid var(--line)",
                  background: "transparent",
                  color: "var(--text-2)",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={procesandoEstado}
                onClick={handleConfirmarCambioEstado}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  background:
                    equipoConfirmarEstado.accion === "desactivar"
                      ? "var(--risk)"
                      : "var(--pitch)",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: procesandoEstado ? "wait" : "pointer",
                }}
              >
                {procesandoEstado
                  ? "Procesando..."
                  : equipoConfirmarEstado.accion === "desactivar"
                    ? "Confirmar Baja"
                    : "Confirmar Reactivación"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
