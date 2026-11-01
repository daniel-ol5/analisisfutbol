import { useState } from "react";
import type { FormEvent } from "react";
import { ETIQUETAS_POSICION, ETIQUETAS_PIE } from "../types";
import type { Jugador, JugadorCrear, JugadorEditar, Posicion, PieHabil } from "../types";

interface JugadorFormModalProps {
  abierto: boolean;
  equipoId: number;
  jugadorAEditar?: Jugador | null;
  cargando?: boolean;
  onCerrar: () => void;
  onGuardar: (datos: JugadorCrear | JugadorEditar) => Promise<void>;
}

export function JugadorFormModal({
  abierto,
  equipoId,
  jugadorAEditar,
  cargando = false,
  onCerrar,
  onGuardar,
}: JugadorFormModalProps) {
  const [nombre, setNombre] = useState(jugadorAEditar?.nombre ?? "");
  const [apellido, setApellido] = useState(jugadorAEditar?.apellido ?? "");
  const [dorsal, setDorsal] = useState(jugadorAEditar?.dorsal?.toString() ?? "");
  const [posicion, setPosicion] = useState<Posicion>(jugadorAEditar?.posicion ?? "MED");
  const [pieHabil, setPieHabil] = useState<PieHabil>(jugadorAEditar?.pie_habil ?? "DER");
  const [alturaCm, setAlturaCm] = useState(jugadorAEditar?.altura_cm?.toString() ?? "");
  const [pesoKg, setPesoKg] = useState(jugadorAEditar?.peso_kg?.toString() ?? "");
  const [fechaNacimiento, setFechaNacimiento] = useState(jugadorAEditar?.fecha_nacimiento ?? "");
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  if (!abierto) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!nombre.trim() || !apellido.trim()) {
      setErrorLocal("El nombre y el apellido son obligatorios.");
      return;
    }

    const dorsalNum = Number(dorsal);
    if (!dorsal || Number.isNaN(dorsalNum) || dorsalNum <= 0) {
      setErrorLocal("El dorsal debe ser un número válido mayor a 0.");
      return;
    }

    const alturaNum = Number(alturaCm);
    if (!alturaCm || Number.isNaN(alturaNum) || alturaNum <= 0) {
      setErrorLocal("La estatura (cm) es obligatoria y debe ser un número válido.");
      return;
    }

    setErrorLocal(null);
    try {
      await onGuardar({
        ...(jugadorAEditar ? {} : { equipo_id: equipoId }),
        nombre: nombre.trim(),
        apellido: apellido.trim(),
        dorsal: dorsalNum,
        posicion,
        pie_habil: pieHabil,
        altura_cm: alturaNum,
        peso_kg: pesoKg ? Number(pesoKg) : null,
        fecha_nacimiento: fechaNacimiento || null,
      });
      onCerrar();
    } catch (err: any) {
      setErrorLocal(err?.response?.data?.detail ?? "Error al guardar el jugador.");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0, 0, 0, 0.65)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !cargando) onCerrar();
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: "100%",
          maxWidth: 680,
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0,0,0,0.25)",
          overflow: "hidden",
        }}
      >
        {/* Cabecera del modal */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--pitch)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              CU-11 · Plantel de Jugadores
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
              {jugadorAEditar
                ? `Editar Jugador: ${jugadorAEditar.nombre} ${jugadorAEditar.apellido}`
                : "Nuevo Jugador"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            disabled={cargando}
            style={{
              all: "unset",
              cursor: "pointer",
              fontSize: 20,
              lineHeight: 1,
              color: "var(--text-3)",
              padding: "4px 8px",
              borderRadius: 4,
            }}
          >
            ✕
          </button>
        </div>

        {/* Cuerpo del formulario con scroll */}
        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            padding: 24,
            gap: 20,
          }}
        >
          {errorLocal && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 6,
                background: "rgba(224, 112, 92, 0.12)",
                border: "1px solid var(--risk)",
                color: "var(--risk)",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {errorLocal}
            </div>
          )}

          {/* Nombre, Apellido, Dorsal */}
          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr", gap: 14 }}>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Nombre *
              </label>
              <input
                type="text"
                required
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="ej. Lionel"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Apellido *
              </label>
              <input
                type="text"
                required
                value={apellido}
                onChange={(e) => setApellido(e.target.value)}
                placeholder="ej. Messi"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Dorsal *
              </label>
              <input
                type="number"
                required
                min={1}
                value={dorsal}
                onChange={(e) => setDorsal(e.target.value)}
                placeholder="ej. 10"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>
          </div>

          {/* Posición, Pie hábil */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Posición
              </label>
              <select
                value={posicion}
                onChange={(e) => setPosicion(e.target.value as Posicion)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              >
                {Object.entries(ETIQUETAS_POSICION).map(([valor, etiqueta]) => (
                  <option key={valor} value={valor}>
                    {etiqueta}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Pie Hábil
              </label>
              <select
                value={pieHabil}
                onChange={(e) => setPieHabil(e.target.value as PieHabil)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              >
                {Object.entries(ETIQUETAS_PIE).map(([valor, etiqueta]) => (
                  <option key={valor} value={valor}>
                    {etiqueta}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Estatura, Peso, Fecha de nacimiento */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.2fr", gap: 14 }}>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Estatura (cm) *
              </label>
              <input
                type="number"
                required
                min={1}
                value={alturaCm}
                onChange={(e) => setAlturaCm(e.target.value)}
                placeholder="ej. 170"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Peso (kg)
              </label>
              <input
                type="number"
                min={1}
                value={pesoKg}
                onChange={(e) => setPesoKg(e.target.value)}
                placeholder="ej. 72"
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--text)",
                  marginBottom: 6,
                }}
              >
                Fecha de Nacimiento
              </label>
              <input
                type="date"
                value={fechaNacimiento ?? ""}
                onChange={(e) => setFechaNacimiento(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  fontSize: 14,
                  color: "var(--text)",
                  background: "var(--ground)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  outline: "none",
                }}
              />
            </div>
          </div>

          {/* Botones de acción */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 12,
              marginTop: 10,
              paddingTop: 16,
              borderTop: "1px solid var(--line)",
            }}
          >
            <button
              type="button"
              disabled={cargando}
              onClick={onCerrar}
              style={{
                all: "unset",
                cursor: "pointer",
                padding: "9px 18px",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text-2)",
                background: "var(--ground)",
                borderRadius: 6,
                border: "1px solid var(--line)",
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={cargando}
              style={{
                all: "unset",
                cursor: cargando ? "wait" : "pointer",
                padding: "9px 22px",
                fontSize: 13,
                fontWeight: 700,
                color: "#ffffff",
                background: "var(--pitch)",
                borderRadius: 6,
                boxShadow: "0 2px 6px rgba(11, 107, 69, 0.25)",
                transition: "opacity 0.15s ease",
                opacity: cargando ? 0.7 : 1,
              }}
            >
              {cargando ? "Guardando…" : jugadorAEditar ? "Guardar Cambios" : "Crear Jugador"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
