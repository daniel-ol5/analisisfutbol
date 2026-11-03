import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { editarEquipo, listarEquipos } from "../api";
import { calcularDistanciaHsv, hexAHsv, type Equipo } from "../types";
import { ColorPickerKit } from "./ColorPickerKit";
import { ColorVerificationModal } from "./ColorVerificationModal";
import { JerseyPreview } from "./JerseyPreview";

const COLORES_BASE = {
  color_local: "#1E5AA8",
  color_visitante: "#FFFFFF",
  color_arquero: "#F2C200",
};

interface IndumentariaViewProps {
  equipoInicialId?: number | null;
}

export function IndumentariaView({ equipoInicialId }: IndumentariaViewProps) {
  const [equipos, setEquipos] = useState<Equipo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [filtroContraste, setFiltroContraste] = useState<
    "TODOS" | "OPTIMO" | "RIESGO"
  >("TODOS");

  // Modal de Registro / Edición de Indumentaria (CU-10)
  const [modalConfigAbierto, setModalConfigAbierto] = useState(false);
  const [equipoSeleccionadoId, setEquipoSeleccionadoId] = useState<
    number | null
  >(null);
  const [colorLocal, setColorLocal] = useState(COLORES_BASE.color_local);
  const [colorVisitante, setColorVisitante] = useState(
    COLORES_BASE.color_visitante,
  );
  const [colorArquero, setColorArquero] = useState(COLORES_BASE.color_arquero);
  const [guardandoKit, setGuardandoKit] = useState(false);
  const [errorKit, setErrorKit] = useState<string | null>(null);

  // Modal de Visualización de Ficha Óptica HSV
  const [equipoVerFicha, setEquipoVerFicha] = useState<Equipo | null>(null);

  // Modal de Simulación vs Rival
  const [equipoVerificarRival, setEquipoVerificarRival] =
    useState<Equipo | null>(null);

  // Modal de Confirmación para Restablecer Indumentaria
  const [equipoRestablecer, setEquipoRestablecer] = useState<Equipo | null>(
    null,
  );
  const [restableciendo, setRestableciendo] = useState(false);

  const cargarEquipos = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await listarEquipos(true);
      setEquipos(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo cargar la indumentaria de los equipos.";
      setError(msg);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargarEquipos();
  }, [cargarEquipos]);

  const abrirConfigurarIndumentaria = useCallback(
    (equipo?: Equipo) => {
      const target = equipo ?? equipos[0] ?? null;
      if (!target) return;
      setEquipoSeleccionadoId(target.id);
      setColorLocal(target.color_local || COLORES_BASE.color_local);
      setColorVisitante(target.color_visitante || COLORES_BASE.color_visitante);
      setColorArquero(target.color_arquero || COLORES_BASE.color_arquero);
      setErrorKit(null);
      setModalConfigAbierto(true);
    },
    [equipos],
  );

  // Si venimos redirigidos desde un equipo en CU-09, abrimos su editor de indumentaria
  useEffect(() => {
    if (equipoInicialId && equipos.length > 0) {
      const eq = equipos.find((e) => e.id === equipoInicialId);
      if (eq) {
        abrirConfigurarIndumentaria(eq);
      }
    }
  }, [equipoInicialId, equipos, abrirConfigurarIndumentaria]);

  const handleCambioEquipoEnModal = (nuevoId: number) => {
    setEquipoSeleccionadoId(nuevoId);
    const eq = equipos.find((e) => e.id === nuevoId);
    if (eq) {
      setColorLocal(eq.color_local);
      setColorVisitante(eq.color_visitante);
      setColorArquero(eq.color_arquero);
    }
  };

  const handleGuardarIndumentaria = async (e: FormEvent) => {
    e.preventDefault();
    if (!equipoSeleccionadoId) return;
    setErrorKit(null);

    const hexRegex = /^#[0-9A-Fa-f]{6}$/;
    if (
      !hexRegex.test(colorLocal) ||
      !hexRegex.test(colorVisitante) ||
      !hexRegex.test(colorArquero)
    ) {
      setErrorKit(
        "Todos los colores deben tener formato hexadecimal válido (#RRGGBB).",
      );
      return;
    }

    setGuardandoKit(true);
    try {
      await editarEquipo(equipoSeleccionadoId, {
        color_local: colorLocal.toUpperCase(),
        color_visitante: colorVisitante.toUpperCase(),
        color_arquero: colorArquero.toUpperCase(),
      });
      setModalConfigAbierto(false);
      await cargarEquipos();
    } catch (err: unknown) {
      setErrorKit(
        err instanceof Error
          ? err.message
          : "Error al guardar la indumentaria del equipo.",
      );
    } finally {
      setGuardandoKit(false);
    }
  };

  const handleConfirmarRestablecer = async () => {
    if (!equipoRestablecer) return;
    setRestableciendo(true);
    try {
      await editarEquipo(equipoRestablecer.id, COLORES_BASE);
      setEquipoRestablecer(null);
      if (equipoVerFicha?.id === equipoRestablecer.id) {
        setEquipoVerFicha(null);
      }
      await cargarEquipos();
    } catch (err: unknown) {
      alert(
        err instanceof Error
          ? err.message
          : "No se pudo restablecer la indumentaria.",
      );
    } finally {
      setRestableciendo(false);
    }
  };

  const equiposConMetricas = useMemo(() => {
    return equipos.map((eq) => {
      const distLocalVisita = calcularDistanciaHsv(
        eq.color_local,
        eq.color_visitante,
      );
      const distLocalArquero = calcularDistanciaHsv(
        eq.color_local,
        eq.color_arquero,
      );
      const distVisitaArquero = calcularDistanciaHsv(
        eq.color_visitante,
        eq.color_arquero,
      );
      const hayRiesgo =
        (distLocalVisita !== null && distLocalVisita < 40) ||
        (distLocalArquero !== null && distLocalArquero < 40);
      return {
        equipo: eq,
        distLocalVisita,
        distLocalArquero,
        distVisitaArquero,
        hayRiesgo,
      };
    });
  }, [equipos]);

  const equiposFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return equiposConMetricas.filter(({ equipo, hayRiesgo }) => {
      if (filtroContraste === "OPTIMO" && hayRiesgo) return false;
      if (filtroContraste === "RIESGO" && !hayRiesgo) return false;
      if (!q) return true;
      return (
        equipo.nombre.toLowerCase().includes(q) ||
        equipo.categoria.toLowerCase().includes(q) ||
        equipo.color_local.toLowerCase().includes(q) ||
        equipo.color_visitante.toLowerCase().includes(q) ||
        equipo.color_arquero.toLowerCase().includes(q)
      );
    });
  }, [equiposConMetricas, busqueda, filtroContraste]);

  const kpis = useMemo(() => {
    const total = equiposConMetricas.length;
    const optimos = equiposConMetricas.filter((e) => !e.hayRiesgo).length;
    const conAlerta = equiposConMetricas.filter((e) => e.hayRiesgo).length;
    return { total, optimos, conAlerta };
  }, [equiposConMetricas]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* KPIs de Indumentaria y Contraste Óptico (CU-10) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
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
            Kits de Equipos Configurados
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
            Contraste Óptico Óptimo (HSV ≥ 40)
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: "var(--pitch)",
              marginTop: 4,
            }}
          >
            {kpis.optimos}
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
            Alertas de Similitud Interna
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: kpis.conAlerta > 0 ? "var(--risk)" : "var(--text-3)",
              marginTop: 4,
            }}
          >
            {kpis.conAlerta}
          </div>
        </div>
      </div>

      {/* Barra de Búsqueda, Filtro Óptico y Acción Principal */}
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
            placeholder="Buscar equipo o código hex (#1E5AA8)..."
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
            value={filtroContraste}
            onChange={(e) =>
              setFiltroContraste(
                e.target.value as "TODOS" | "OPTIMO" | "RIESGO",
              )
            }
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
            <option value="TODOS">Todos los estados ópticos</option>
            <option value="OPTIMO">Contraste óptimo (HSV ≥ 40)</option>
            <option value="RIESGO">Con alerta de contraste (HSV &lt; 40)</option>
          </select>
        </div>

        <button
          type="button"
          disabled={equipos.length === 0}
          onClick={() => abrirConfigurarIndumentaria()}
          style={{
            padding: "9px 18px",
            borderRadius: 6,
            border: "none",
            background: "var(--pitch)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 700,
            cursor: equipos.length === 0 ? "not-allowed" : "pointer",
            opacity: equipos.length === 0 ? 0.6 : 1,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            boxShadow: "0 2px 6px rgba(13, 148, 136, 0.25)",
          }}
        >
          Configurar Indumentaria
        </button>
      </div>

      {/* Listado de Tarjetas de Indumentaria (CU-10) */}
      {cargando ? (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--text-3)",
            fontSize: 14,
          }}
        >
          Cargando catálogo de indumentaria oficial...
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
            No se encontraron registros de indumentaria
          </h4>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)" }}>
            Registra primero un equipo en la pestaña "Gestionar Equipos (CU-09)"
            o ajusta los filtros de búsqueda.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
            gap: 18,
          }}
        >
          {equiposFiltrados.map(
            ({
              equipo,
              distLocalVisita,
              distLocalArquero,
              hayRiesgo,
            }) => (
              <article
                key={equipo.id}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 10,
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                {/* Cabecera del Equipo + Estado Óptico */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 10,
                  }}
                >
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          fontWeight: 700,
                          padding: "2px 7px",
                          borderRadius: 4,
                          background: "rgba(13, 148, 136, 0.12)",
                          color: "var(--pitch)",
                        }}
                      >
                        EQ-{String(equipo.id).padStart(2, "0")}
                      </span>
                      <span
                        style={{
                          fontSize: 11.5,
                          color: "var(--text-2)",
                          fontWeight: 600,
                        }}
                      >
                        {equipo.categoria || "Categoría General"}
                      </span>
                    </div>
                    <h3
                      style={{
                        margin: "6px 0 0",
                        fontSize: 18,
                        fontWeight: 800,
                        color: "var(--text)",
                      }}
                    >
                      {equipo.nombre}
                    </h3>
                  </div>

                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "4px 9px",
                      borderRadius: 99,
                      background: hayRiesgo
                        ? "rgba(224, 112, 92, 0.14)"
                        : "rgba(13, 148, 136, 0.14)",
                      color: hayRiesgo ? "var(--risk)" : "var(--pitch)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {hayRiesgo ? "RIESGO HSV" : "CONTRASTE OK"}
                  </span>
                </div>

                {/* Vitrina de las 3 Camisetas Oficiales (CU-10) */}
                <div
                  style={{
                    padding: "16px 12px",
                    borderRadius: 8,
                    background: "var(--ground)",
                    border: "1px solid var(--line)",
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 10,
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <JerseyPreview
                      color={equipo.color_local}
                      size="md"
                      etiqueta="Titular"
                    />
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: "var(--font-mono)",
                        fontWeight: 700,
                        color: "var(--text-2)",
                      }}
                    >
                      {equipo.color_local.toUpperCase()}
                    </span>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <JerseyPreview
                      color={equipo.color_visitante}
                      size="md"
                      etiqueta="Alternativa"
                    />
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: "var(--font-mono)",
                        fontWeight: 700,
                        color: "var(--text-2)",
                      }}
                    >
                      {equipo.color_visitante.toUpperCase()}
                    </span>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <JerseyPreview
                      color={equipo.color_arquero}
                      size="md"
                      etiqueta="Arquero"
                    />
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: "var(--font-mono)",
                        fontWeight: 700,
                        color: "var(--text-2)",
                      }}
                    >
                      {equipo.color_arquero.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Métricas de Distancia en Espacio Cilíndrico HSV */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 8,
                    fontSize: 11.5,
                  }}
                >
                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "var(--ground)",
                      border:
                        distLocalVisita !== null && distLocalVisita < 40
                          ? "1px solid var(--risk)"
                          : "1px solid var(--line)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "var(--text-2)", fontWeight: 600 }}>
                      Titular / Visita:
                    </span>
                    <strong
                      style={{
                        fontFamily: "var(--font-mono)",
                        color:
                          distLocalVisita !== null && distLocalVisita < 40
                            ? "var(--risk)"
                            : "var(--pitch)",
                      }}
                    >
                      {distLocalVisita !== null
                        ? `${distLocalVisita.toFixed(1)}`
                        : "—"}
                    </strong>
                  </div>

                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "var(--ground)",
                      border:
                        distLocalArquero !== null && distLocalArquero < 40
                          ? "1px solid var(--risk)"
                          : "1px solid var(--line)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "var(--text-2)", fontWeight: 600 }}>
                      Titular / Arquero:
                    </span>
                    <strong
                      style={{
                        fontFamily: "var(--font-mono)",
                        color:
                          distLocalArquero !== null && distLocalArquero < 40
                            ? "var(--risk)"
                            : "var(--pitch)",
                      }}
                    >
                      {distLocalArquero !== null
                        ? `${distLocalArquero.toFixed(1)}`
                        : "—"}
                    </strong>
                  </div>
                </div>

                {/* Acciones CRUD de Indumentaria: Visualizar, Editar, Simular vs Rival, Restablecer */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderTop: "1px solid var(--line)",
                    paddingTop: 12,
                    marginTop: "auto",
                    gap: 6,
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => setEquipoVerFicha(equipo)}
                      title="Visualizar análisis óptico HSV detallado"
                      style={{
                        padding: "6px 10px",
                        borderRadius: 6,
                        border: "1px solid var(--line)",
                        background: "var(--ground)",
                        color: "var(--text)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Ficha óptica
                    </button>

                    <button
                      type="button"
                      onClick={() => setEquipoVerificarRival(equipo)}
                      title="Simular contraste contra camiseta de equipo rival"
                      style={{
                        padding: "6px 10px",
                        borderRadius: 6,
                        border: "1px solid var(--line)",
                        background: "var(--ground)",
                        color: "var(--text-2)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Probar vs Rival
                    </button>
                  </div>

                  <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
                    <button
                      type="button"
                      onClick={() => abrirConfigurarIndumentaria(equipo)}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 6,
                        border: "1px solid var(--line)",
                        background: "var(--ground)",
                        color: "var(--text-2)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Editar Kits
                    </button>

                    <button
                      type="button"
                      onClick={() => setEquipoRestablecer(equipo)}
                      title="Restablecer indumentaria a colores institucionales base"
                      style={{
                        padding: "6px 10px",
                        borderRadius: 6,
                        border: "1px solid rgba(224, 112, 92, 0.35)",
                        background: "rgba(224, 112, 92, 0.08)",
                        color: "var(--risk)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Restablecer
                    </button>
                  </div>
                </div>
              </article>
            ),
          )}
        </div>
      )}

      {/* Modal de Registro / Edición de Indumentaria (CU-10) */}
      {modalConfigAbierto && (
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
            zIndex: 1000,
            padding: 20,
          }}
          onClick={() => setModalConfigAbierto(false)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: 12,
              width: "100%",
              maxWidth: 650,
              maxHeight: "92vh",
              overflowY: "auto",
              padding: 24,
              boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--line)",
                paddingBottom: 14,
                marginBottom: 18,
              }}
            >
              <div>
                <span
                  className="kicker"
                  style={{ color: "var(--pitch)", fontWeight: 700 }}
                >
                  CU-10 · REGISTRAR INDUMENTARIA DE EQUIPO
                </span>
                <h3 style={{ margin: "4px 0 0", fontSize: 20 }}>
                  Configuración Oficial de Camisetas y Contraste HSV
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setModalConfigAbierto(false)}
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

            {errorKit && (
              <div
                style={{
                  padding: "10px 14px",
                  marginBottom: 16,
                  borderRadius: 6,
                  background: "rgba(224, 112, 92, 0.12)",
                  border: "1px solid var(--risk)",
                  color: "var(--risk)",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {errorKit}
              </div>
            )}

            <form
              onSubmit={handleGuardarIndumentaria}
              style={{ display: "flex", flexDirection: "column", gap: 18 }}
            >
              {/* Selector de Equipo al que se le registra/edita la indumentaria */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  padding: 14,
                  borderRadius: 8,
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                }}
              >
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--text-2)",
                  }}
                >
                  Seleccionar Equipo del Club
                </label>
                <select
                  value={equipoSeleccionadoId ?? ""}
                  onChange={(e) =>
                    handleCambioEquipoEnModal(Number(e.target.value))
                  }
                  style={{
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    fontSize: 14,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {equipos.map((eq) => (
                    <option key={eq.id} value={eq.id}>
                      EQ-{String(eq.id).padStart(2, "0")} · {eq.nombre} (
                      {eq.categoria || "General"})
                    </option>
                  ))}
                </select>
              </div>

              <ColorPickerKit
                colorLocal={colorLocal}
                colorVisitante={colorVisitante}
                colorArquero={colorArquero}
                onChangeLocal={setColorLocal}
                onChangeVisitante={setColorVisitante}
                onChangeArquero={setColorArquero}
              />

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 10,
                  borderTop: "1px solid var(--line)",
                  paddingTop: 16,
                }}
              >
                <button
                  type="button"
                  onClick={() => setModalConfigAbierto(false)}
                  style={{
                    padding: "9px 16px",
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
                  type="submit"
                  disabled={guardandoKit}
                  style={{
                    padding: "9px 20px",
                    borderRadius: 6,
                    border: "none",
                    background: "var(--pitch)",
                    color: "#fff",
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: guardandoKit ? "wait" : "pointer",
                    opacity: guardandoKit ? 0.7 : 1,
                  }}
                >
                  {guardandoKit
                    ? "Guardando Indumentaria..."
                    : "Guardar Indumentaria"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de Visualización: Ficha Óptica HSV (CU-10) */}
      {equipoVerFicha && (
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
            zIndex: 1000,
            padding: 20,
          }}
          onClick={() => setEquipoVerFicha(null)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: 12,
              width: "100%",
              maxWidth: 560,
              padding: 24,
              boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
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
                <span
                  className="kicker"
                  style={{ color: "var(--pitch)", fontWeight: 700 }}
                >
                  CU-10 · FICHA ÓPTICA DE INDUMENTARIA
                </span>
                <h3 style={{ margin: "4px 0 0", fontSize: 20 }}>
                  {equipoVerFicha.nombre}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEquipoVerFicha(null)}
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

            {/* Detalle de los 3 uniformes con coordenadas HSV */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
              }}
            >
              {[
                {
                  etiqueta: "Titular (Local)",
                  hex: equipoVerFicha.color_local,
                },
                {
                  etiqueta: "Alternativa (Visita)",
                  hex: equipoVerFicha.color_visitante,
                },
                {
                  etiqueta: "Guardameta (Arquero)",
                  hex: equipoVerFicha.color_arquero,
                },
              ].map((item) => {
                const hsv = hexAHsv(item.hex);
                return (
                  <div
                    key={item.etiqueta}
                    style={{
                      padding: 14,
                      borderRadius: 8,
                      background: "var(--ground)",
                      border: "1px solid var(--line)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 8,
                      textAlign: "center",
                    }}
                  >
                    <JerseyPreview color={item.hex} size="lg" />
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 800,
                        color: "var(--text)",
                      }}
                    >
                      {item.etiqueta}
                    </div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 13,
                        fontWeight: 700,
                        color: "var(--pitch)",
                      }}
                    >
                      {item.hex.toUpperCase()}
                    </div>
                    {hsv && (
                      <div
                        style={{
                          fontSize: 11,
                          fontFamily: "var(--font-mono)",
                          color: "var(--text-3)",
                        }}
                      >
                        H:{hsv[0]}° S:{Math.round(hsv[1])}% V:
                        {Math.round(hsv[2])}%
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Matriz de Distancias HSV */}
            <div
              style={{
                padding: 14,
                borderRadius: 8,
                background: "var(--ground)",
                border: "1px solid var(--line)",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div
                style={{
                  fontSize: 11.5,
                  fontWeight: 800,
                  color: "var(--text-2)",
                  textTransform: "uppercase",
                }}
              >
                Matriz de Separación Óptica Cilíndrica (Umbral mínimo = 40.0)
              </div>
              {[
                {
                  par: "Titular vs Alternativa",
                  d: calcularDistanciaHsv(
                    equipoVerFicha.color_local,
                    equipoVerFicha.color_visitante,
                  ),
                },
                {
                  par: "Titular vs Arquero",
                  d: calcularDistanciaHsv(
                    equipoVerFicha.color_local,
                    equipoVerFicha.color_arquero,
                  ),
                },
                {
                  par: "Alternativa vs Arquero",
                  d: calcularDistanciaHsv(
                    equipoVerFicha.color_visitante,
                    equipoVerFicha.color_arquero,
                  ),
                },
              ].map((fila) => {
                const ok = fila.d !== null && fila.d >= 40;
                return (
                  <div
                    key={fila.par}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 13,
                      padding: "6px 0",
                      borderBottom: "1px dashed var(--line)",
                    }}
                  >
                    <span style={{ color: "var(--text)" }}>{fila.par}</span>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontWeight: 800,
                        color: ok ? "var(--pitch)" : "var(--risk)",
                      }}
                    >
                      {fila.d !== null ? fila.d.toFixed(2) : "—"} (
                      {ok ? "Óptimo" : "Riesgo"})
                    </span>
                  </div>
                );
              })}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderTop: "1px solid var(--line)",
                paddingTop: 14,
              }}
            >
              <button
                type="button"
                onClick={() => {
                  const eq = equipoVerFicha;
                  setEquipoVerFicha(null);
                  setEquipoRestablecer(eq);
                }}
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
                Restablecer colores base
              </button>

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => {
                    const eq = equipoVerFicha;
                    setEquipoVerFicha(null);
                    abrirConfigurarIndumentaria(eq);
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
                  Editar Kits
                </button>
                <button
                  type="button"
                  onClick={() => setEquipoVerFicha(null)}
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

      {/* Modal de Verificación contra Rival (CU-10) */}
      <ColorVerificationModal
        abierto={equipoVerificarRival !== null}
        equipo={equipoVerificarRival}
        otrosEquipos={equipos.filter(
          (eq) => eq.id !== equipoVerificarRival?.id,
        )}
        onCerrar={() => setEquipoVerificarRival(null)}
      />

      {/* Modal de Confirmación para Restablecer Indumentaria */}
      {equipoRestablecer && (
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
          onClick={() => setEquipoRestablecer(null)}
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
              ¿Restablecer indumentaria de "{equipoRestablecer.nombre}"?
            </h3>
            <p
              style={{
                margin: 0,
                fontSize: 13.5,
                color: "var(--text-2)",
                lineHeight: 1.5,
              }}
            >
              Los colores volverán a los valores institucionales por defecto:
              Titular <code>#1E5AA8</code>, Alternativa <code>#FFFFFF</code> y
              Arquero <code>#F2C200</code>.
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
                onClick={() => setEquipoRestablecer(null)}
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
                disabled={restableciendo}
                onClick={handleConfirmarRestablecer}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  background: "var(--risk)",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: restableciendo ? "wait" : "pointer",
                }}
              >
                {restableciendo
                  ? "Restableciendo..."
                  : "Confirmar Restablecimiento"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
