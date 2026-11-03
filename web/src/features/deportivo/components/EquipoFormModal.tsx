import { type FormEvent, useEffect, useState } from "react";
import type { Equipo, EquipoCrear } from "../types";

interface EquipoFormModalProps {
  abierto: boolean;
  equipoEditar?: Equipo | null;
  onCerrar: () => void;
  onGuardar: (datos: EquipoCrear & { activo?: boolean }) => Promise<void>;
}

const TEMPORADAS_SUGERIDAS = [
  "2026",
  "2026 - Apertura",
  "2026 - Clausura",
  "2025/2026",
  "2026/2027",
  "Torneo de Verano 2026",
  "Copa Nacional 2026",
];

const ESTRUCTURA_FUTBOL: Record<string, Record<string, string[]>> = {
  "Bolivia (FBF)": {
    "División Profesional y Ascenso": [
      "Primera División (División Profesional)",
      "Copa Simón Bolívar (Ascenso Nacional)",
      "Torneo Nacional de Reservas / Promoción",
    ],
    "Asociaciones Departamentales (AFL / AFC / ACF)": [
      "Primera A (Asociación Departamental)",
      "Primera B (Asociación Departamental)",
      "Primera de Ascenso",
      "Segunda de Ascenso",
    ],
    "Divisiones Formativas y Juveniles": [
      "Sub-20",
      "Sub-19",
      "Sub-17",
      "Sub-15",
      "Sub-13",
      "Escuelas / Infantil",
    ],
    "Fútbol Femenino": [
      "Liga Femenina de Fútbol Boliviano",
      "Femenino Primera División",
      "Femenino Sub-19",
    ],
  },
  "Argentina (AFA)": {
    "Ligas Profesionales": [
      "Liga Profesional de Fútbol (Primera División)",
      "Primera Nacional (2da División)",
      " Torneo Proyección (Reserva)",
    ],
    "Categorías de Ascenso": [
      "Primera B Metropolitana",
      "Torneo Federal A",
      "Primera C",
    ],
    "Divisiones Inferiores AFA": [
      "Cuarta División (Sub-20)",
      "Quinta División (Sub-18)",
      "Sexta División (Sub-17)",
      "Séptima División (Sub-16)",
      "Octava División (Sub-15)",
      "Novena División (Sub-14)",
    ],
    "Fútbol Femenino": [
      " Campeonato Femenino YPF (Primera A)",
      "Primera B Femenina",
    ],
  },
  "España (RFEF / LaLiga)": {
    "Competiciones Nacionales": [
      "Primera División (LaLiga EA Sports)",
      "Segunda División (LaLiga Hypermotion)",
      "Primera Federación (1ª RFEF)",
      "Segunda Federación (2ª RFEF)",
      "Tercera Federación (3ª RFEF)",
    ],
    "Fútbol Base y Juvenil": [
      "Filial / Equipo B",
      "Juvenil División de Honor (U19)",
      "Juvenil Liga Nacional",
      "Cadete División de Honor (U16)",
      "Infantil Autonómico (U14)",
    ],
    "Fútbol Femenino": [
      "Liga F (Primera División Femenina)",
      "Primera Federación FutFem",
    ],
  },
  "Brasil (CBF)": {
    "Campeonatos Nacionales": [
      "Brasileirão Série A",
      "Brasileirão Série B",
      "Brasileirão Série C",
      "Brasileirão Série D",
    ],
    "Torneos Estaduales y Base": [
      "Campeonato Estadual (Paulista / Carioca / Mineiro)",
      "Brasileirão Sub-20",
      "Brasileirão Sub-17",
      "Brasileirão Feminino A1",
    ],
  },
  "Internacional (CONMEBOL / FIFA)": {
    "Torneos Continentales de Clubes": [
      "CONMEBOL Libertadores",
      "CONMEBOL Sudamericana",
      "CONMEBOL Libertadores Sub-20",
      "CONMEBOL Libertadores Femenina",
    ],
    "Selecciones y Torneos Juveniles": [
      "Selección Absoluta",
      "Selección Sub-23 (Preolímpico)",
      "Selección Sub-20",
      "Selección Sub-17",
    ],
  },
  "Personalizado / Otra Liga": {
    "General": ["Otra categoría personalizada..."],
  },
};

export function EquipoFormModal({
  abierto,
  equipoEditar,
  onCerrar,
  onGuardar,
}: EquipoFormModalProps) {
  const [nombre, setNombre] = useState("");

  // Selectores jerárquicos de País -> Liga -> Categoría
  const [paisLiga, setPaisLiga] = useState<string>("Bolivia (FBF)");
  const [tipoCompeticion, setTipoCompeticion] = useState<string>("División Profesional y Ascenso");
  const [categoria, setCategoria] = useState("");
  const [modoCategoriaManual, setModoCategoriaManual] = useState(false);

  const [temporada, setTemporada] = useState("2026");
  const [modoTemporadaManual, setModoTemporadaManual] = useState(false);
  const [activo, setActivo] = useState(true);

  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (equipoEditar) {
      setNombre(equipoEditar.nombre);
      setCategoria(equipoEditar.categoria || "");
      setTemporada(equipoEditar.temporada || "2026");
      setActivo(equipoEditar.activo);

      let encontrado = false;
      for (const [pais, bloques] of Object.entries(ESTRUCTURA_FUTBOL)) {
        for (const [bloque, cats] of Object.entries(bloques)) {
          if (cats.includes(equipoEditar.categoria)) {
            setPaisLiga(pais);
            setTipoCompeticion(bloque);
            encontrado = true;
            break;
          }
        }
        if (encontrado) break;
      }

      if (!encontrado && equipoEditar.categoria) {
        setModoCategoriaManual(true);
      } else {
        setModoCategoriaManual(false);
      }

      if (
        equipoEditar.temporada &&
        !TEMPORADAS_SUGERIDAS.includes(equipoEditar.temporada)
      ) {
        setModoTemporadaManual(true);
      } else {
        setModoTemporadaManual(false);
      }
    } else {
      setNombre("");
      setPaisLiga("Bolivia (FBF)");
      setTipoCompeticion("División Profesional y Ascenso");
      setCategoria("Primera División (División Profesional)");
      setModoCategoriaManual(false);
      setTemporada("2026");
      setModoTemporadaManual(false);
      setActivo(true);
    }
    setError(null);
  }, [equipoEditar, abierto]);

  const handlePaisChange = (nuevoPais: string) => {
    setPaisLiga(nuevoPais);
    if (nuevoPais === "Personalizado / Otra Liga") {
      setModoCategoriaManual(true);
      setCategoria("");
      return;
    }
    setModoCategoriaManual(false);
    const bloques = Object.keys(ESTRUCTURA_FUTBOL[nuevoPais] || {});
    const primerBloque = bloques[0] || "";
    setTipoCompeticion(primerBloque);
    const categorias = ESTRUCTURA_FUTBOL[nuevoPais]?.[primerBloque] || [];
    setCategoria(categorias[0] || "");
  };

  const handleBloqueChange = (nuevoBloque: string) => {
    setTipoCompeticion(nuevoBloque);
    const categorias = ESTRUCTURA_FUTBOL[paisLiga]?.[nuevoBloque] || [];
    setCategoria(categorias[0] || "");
  };

  if (!abierto) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!nombre.trim()) {
      setError("El nombre del equipo es obligatorio.");
      return;
    }

    setEnviando(true);
    try {
      await onGuardar({
        nombre: nombre.trim(),
        categoria: categoria.trim(),
        temporada: temporada.trim(),
        color_local: equipoEditar?.color_local ?? "#1E5AA8",
        color_visitante: equipoEditar?.color_visitante ?? "#FFFFFF",
        color_arquero: equipoEditar?.color_arquero ?? "#F2C200",
        ...(equipoEditar ? { activo } : {}),
      });
      onCerrar();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al guardar el equipo.";
      setError(msg);
    } finally {
      setEnviando(false);
    }
  };

  const bloquesDisponibles = Object.keys(ESTRUCTURA_FUTBOL[paisLiga] || {});
  const categoriasDisponibles =
    ESTRUCTURA_FUTBOL[paisLiga]?.[tipoCompeticion] || [];

  return (
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
      onClick={onCerrar}
    >
      <div
        className="modal-card"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: "100%",
          maxWidth: 600,
          maxHeight: "92vh",
          overflowY: "auto",
          boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
          padding: 24,
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
            marginBottom: 20,
          }}
        >
          <div>
            <span
              className="kicker"
              style={{ color: "var(--pitch)", fontWeight: 700 }}
            >
              CU-09 · GESTIONAR EQUIPOS
            </span>
            <h3 style={{ margin: "4px 0 0", fontSize: 20 }}>
              {equipoEditar
                ? `Editar Equipo: ${equipoEditar.nombre}`
                : "Registrar Nuevo Equipo"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCerrar}
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

        {error && (
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
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 18 }}
        >
          {/* Nombre y Temporada */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.4fr 1fr",
              gap: 14,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <label
                style={{ fontSize: 12, fontWeight: 700, color: "var(--text-2)" }}
              >
                Nombre del Equipo / Plantel *
              </label>
              <input
                type="text"
                required
                placeholder="Ej. Primera División, Reserva, Sub-19..."
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                style={{
                  padding: "9px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--line)",
                  background: "var(--ground)",
                  color: "var(--text)",
                  fontSize: 13.5,
                }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--text-2)",
                  }}
                >
                  Temporada / Ciclo
                </label>
                <button
                  type="button"
                  onClick={() => setModoTemporadaManual(!modoTemporadaManual)}
                  style={{
                    all: "unset",
                    cursor: "pointer",
                    fontSize: 11,
                    color: "var(--pitch)",
                    fontWeight: 600,
                  }}
                >
                  {modoTemporadaManual ? "Usar lista" : "Escribir otra"}
                </button>
              </div>

              {modoTemporadaManual ? (
                <input
                  type="text"
                  placeholder="Ej. 2026 - Torneo Invierno"
                  value={temporada}
                  onChange={(e) => setTemporada(e.target.value)}
                  style={{
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--ground)",
                    color: "var(--text)",
                    fontSize: 13.5,
                  }}
                />
              ) : (
                <select
                  value={temporada}
                  onChange={(e) => setTemporada(e.target.value)}
                  style={{
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--ground)",
                    color: "var(--text)",
                    fontSize: 13.5,
                    cursor: "pointer",
                  }}
                >
                  {TEMPORADAS_SUGERIDAS.map((temp) => (
                    <option key={temp} value={temp}>
                      {temp}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Selector Estructurado de Liga y Categoría */}
          <div
            style={{
              padding: 14,
              borderRadius: 8,
              background: "var(--ground)",
              border: "1px solid var(--line)",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 800,
                  color: "var(--text)",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                Estructura Competitiva (País / Liga / División)
              </span>
              <button
                type="button"
                onClick={() => setModoCategoriaManual(!modoCategoriaManual)}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  fontSize: 11.5,
                  color: "var(--pitch)",
                  fontWeight: 700,
                }}
              >
                {modoCategoriaManual
                  ? "Volver al selector de ligas"
                  : "Escribir categoría manual"}
              </button>
            </div>

            {modoCategoriaManual ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <label
                  style={{
                    fontSize: 11.5,
                    fontWeight: 600,
                    color: "var(--text-2)",
                  }}
                >
                  Nombre de Categoría o Competición Personalizada
                </label>
                <input
                  type="text"
                  placeholder="Ej. Torneo Intercolegial Sub-18, Liga Universitaria..."
                  value={categoria}
                  onChange={(e) => setCategoria(e.target.value)}
                  style={{
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    fontSize: 13.5,
                  }}
                />
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1.2fr",
                  gap: 10,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--text-3)",
                    }}
                  >
                    1. País / Federación
                  </label>
                  <select
                    value={paisLiga}
                    onChange={(e) => handlePaisChange(e.target.value)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      fontSize: 12.5,
                      cursor: "pointer",
                    }}
                  >
                    {Object.keys(ESTRUCTURA_FUTBOL).map((pais) => (
                      <option key={pais} value={pais}>
                        {pais}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--text-3)",
                    }}
                  >
                    2. Rama / Nivel
                  </label>
                  <select
                    value={tipoCompeticion}
                    onChange={(e) => handleBloqueChange(e.target.value)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      fontSize: 12.5,
                      cursor: "pointer",
                    }}
                  >
                    {bloquesDisponibles.map((bloque) => (
                      <option key={bloque} value={bloque}>
                        {bloque}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <label
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--text-3)",
                    }}
                  >
                    3. División / Categoría Oficial
                  </label>
                  <select
                    value={categoria}
                    onChange={(e) => setCategoria(e.target.value)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      border: "1px solid var(--line)",
                      background: "var(--surface)",
                      color: "var(--text)",
                      fontSize: 12.5,
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {categoriasDisponibles.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Estado operativo cuando se edita */}
          {equipoEditar && (
            <div
              style={{
                padding: "12px 14px",
                borderRadius: 8,
                background: "var(--ground)",
                border: "1px solid var(--line)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div
                  style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}
                >
                  Estado operativo del equipo
                </div>
                <div style={{ fontSize: 12, color: "var(--text-2)" }}>
                  Los equipos inactivos conservan todo su historial táctico y de partidos.
                </div>
              </div>
              <label
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: 700,
                  color: activo ? "var(--pitch)" : "var(--text-3)",
                }}
              >
                <input
                  type="checkbox"
                  checked={activo}
                  onChange={(e) => setActivo(e.target.checked)}
                />
                {activo ? "Activo" : "Inactivo"}
              </label>
            </div>
          )}

          {/* Nota informativa sobre Indumentaria separada en CU-10 */}
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 6,
              background: "rgba(13, 148, 136, 0.08)",
              border: "1px solid rgba(13, 148, 136, 0.25)",
              fontSize: 12,
              color: "var(--text-2)",
              lineHeight: 1.45,
            }}
          >
            <strong>Nota:</strong> El registro de camisetas (Titular, Alternativa y Arquero) y la validación óptica HSV se gestionan en la pestaña dedicada{" "}
            <strong style={{ color: "var(--pitch)" }}>
              Indumentaria de Equipo (CU-10)
            </strong>
            .
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              borderTop: "1px solid var(--line)",
              paddingTop: 16,
              marginTop: 4,
            }}
          >
            <button
              type="button"
              onClick={onCerrar}
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
              disabled={enviando}
              style={{
                padding: "9px 20px",
                borderRadius: 6,
                border: "none",
                background: "var(--pitch)",
                color: "#fff",
                fontSize: 13,
                fontWeight: 700,
                cursor: enviando ? "wait" : "pointer",
                opacity: enviando ? 0.7 : 1,
              }}
            >
              {enviando
                ? "Guardando..."
                : equipoEditar
                  ? "Guardar Cambios"
                  : "Crear Equipo"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
