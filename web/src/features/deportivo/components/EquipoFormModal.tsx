import { useState, useMemo } from "react";
import type { FormEvent } from "react";
import { ColorPickerKit } from "./ColorPickerKit";
import { calcularDistanciaHsv } from "../types";
import type { Equipo, EquipoCrear, EquipoEditar } from "../types";

interface EquipoFormModalProps {
  abierto: boolean;
  equipoAEditar?: Equipo | null;
  otrosEquipos: Equipo[];
  cargando?: boolean;
  onCerrar: () => void;
  onGuardar: (datos: EquipoCrear | EquipoEditar) => Promise<void>;
}

export function EquipoFormModal({
  abierto,
  equipoAEditar,
  otrosEquipos,
  cargando = false,
  onCerrar,
  onGuardar,
}: EquipoFormModalProps) {
  const [nombre, setNombre] = useState(equipoAEditar?.nombre ?? "");
  const [categoria, setCategoria] = useState(equipoAEditar?.categoria ?? "Primera");
  const [temporada, setTemporada] = useState(equipoAEditar?.temporada ?? "2026");
  const [colorLocal, setColorLocal] = useState(equipoAEditar?.color_local ?? "#1E5AA8");
  const [colorVisitante, setColorVisitante] = useState(equipoAEditar?.color_visitante ?? "#FFFFFF");
  const [colorArquero, setColorArquero] = useState(equipoAEditar?.color_arquero ?? "#F2C200");
  const [errorLocal, setErrorLocal] = useState<string | null>(null);

  // Verificación de colisión de color contra todos los demás equipos activos (Criterio T-041)
  const conflictosConOtrosEquipos = useMemo(() => {
    return otrosEquipos
      .filter((eq) => eq.id !== equipoAEditar?.id && eq.activo)
      .map((eq) => {
        const distancia = calcularDistanciaHsv(colorLocal, eq.color_local);
        return {
          equipo: eq,
          distancia: distancia ?? 999,
          hayConflicto: distancia !== null && distancia < 40,
          esModerado: distancia !== null && distancia >= 40 && distancia < 55,
        };
      })
      .filter((item) => item.hayConflicto || item.esModerado)
      .sort((a, b) => a.distancia - b.distancia);
  }, [otrosEquipos, equipoAEditar?.id, colorLocal]);

  if (!abierto) return null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!nombre.trim()) {
      setErrorLocal("El nombre del equipo es obligatorio.");
      return;
    }

    const regexHex = /^#[0-9A-Fa-f]{6}$/;
    if (!regexHex.test(colorLocal) || !regexHex.test(colorVisitante) || !regexHex.test(colorArquero)) {
      setErrorLocal("Los colores deben tener formato hexadecimal válido (#RRGGBB).");
      return;
    }

    setErrorLocal(null);
    try {
      await onGuardar({
        nombre: nombre.trim(),
        categoria: categoria.trim(),
        temporada: temporada.trim(),
        color_local: colorLocal,
        color_visitante: colorVisitante,
        color_arquero: colorArquero,
      });
      onCerrar();
    } catch (err: any) {
      setErrorLocal(err?.response?.data?.detail ?? "Error al guardar el equipo.");
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
              CU-09 &amp; CU-10 · Gestión de Equipos
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
              {equipoAEditar ? `Editar Equipo: ${equipoAEditar.nombre}` : "Nuevo Equipo"}
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

          {/* Datos básicos: Nombre, Categoría, Temporada */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 14 }}>
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
                Nombre del Equipo *
              </label>
              <input
                type="text"
                required
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="ej. Primera División, Sub-19"
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
                Categoría
              </label>
              <input
                type="text"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                placeholder="ej. Sub-17, Mayor"
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
                Temporada
              </label>
              <input
                type="text"
                value={temporada}
                onChange={(e) => setTemporada(e.target.value)}
                placeholder="ej. 2026"
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

          {/* Selector visual de indumentaria (los 3 colores) */}
          <div>
            <label
              style={{
                display: "block",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--text)",
                marginBottom: 8,
              }}
            >
              Colores de Indumentaria (CU-10)
            </label>
            <ColorPickerKit
              colorLocal={colorLocal}
              colorVisitante={colorVisitante}
              colorArquero={colorArquero}
              onChangeLocal={setColorLocal}
              onChangeVisitante={setColorVisitante}
              onChangeArquero={setColorArquero}
            />
          </div>

          {/* ALERTA EN VIVO: ¿Dos equipos usan colores demasiado similares? (Criterio de Aceptación T-041) */}
          {conflictosConOtrosEquipos.length > 0 && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                padding: "14px 16px",
                borderRadius: 8,
                background: conflictosConOtrosEquipos.some((c) => c.hayConflicto)
                  ? "rgba(162, 55, 42, 0.1)"
                  : "rgba(242, 194, 0, 0.12)",
                border: conflictosConOtrosEquipos.some((c) => c.hayConflicto)
                  ? "1.5px solid var(--risk)"
                  : "1.5px solid #F2C200",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18 }}>
                  {conflictosConOtrosEquipos.some((c) => c.hayConflicto) ? "⚠️" : "⚡"}
                </span>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 700,
                    color: conflictosConOtrosEquipos.some((c) => c.hayConflicto)
                      ? "var(--risk)"
                      : "var(--text)",
                  }}
                >
                  {conflictosConOtrosEquipos.some((c) => c.hayConflicto)
                    ? "Alerta de Conflicto Óptico: Colores Demasiado Similares (T-041)"
                    : "Aviso de Proximidad Cromática"}
                </span>
              </div>

              {conflictosConOtrosEquipos.map(({ equipo: eq, distancia, hayConflicto }) => (
                <div
                  key={eq.id}
                  style={{
                    fontSize: 12.5,
                    lineHeight: 1.45,
                    color: "var(--text)",
                    padding: "8px 10px",
                    background: "var(--surface)",
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 14,
                        height: 14,
                        borderRadius: "50%",
                        backgroundColor: eq.color_local,
                        border: "1px solid rgba(0,0,0,0.2)",
                        display: "inline-block",
                      }}
                    />
                    <span>
                      Coincide con <strong>{eq.nombre}</strong> ({eq.color_local})
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: "monospace",
                        padding: "2px 6px",
                        borderRadius: 4,
                        fontWeight: 700,
                        backgroundColor: hayConflicto ? "var(--risk)" : "#eab308",
                        color: "#fff",
                      }}
                    >
                      Distancia HSV: {distancia.toFixed(1)} {hayConflicto ? "< 40" : ""}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-3)" }}>
                      {hayConflicto ? "Conflicto en visión" : "Precaución"}
                    </span>
                  </div>
                </div>
              ))}

              <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "var(--text-2)" }}>
                Si estos dos equipos juegan un partido o comparten sesiones de entrenamiento, el
                algoritmo de seguimiento y segmentación por color (YOLO + HSV) puede confundir las
                camisetas. Se aconseja diferenciar el tono o acordar el uso de indumentaria alternativa.
              </p>
            </div>
          )}

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
              {cargando ? "Guardando…" : equipoAEditar ? "Guardar Cambios" : "Crear Equipo"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
