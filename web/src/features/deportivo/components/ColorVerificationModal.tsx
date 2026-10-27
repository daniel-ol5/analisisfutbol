import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { JerseyPreview } from "./JerseyPreview";
import { verificarColoresEquipo } from "../api";
import type { Equipo } from "../types";

interface ColorVerificationModalProps {
  abierto: boolean;
  equipo: Equipo | null;
  otrosEquipos: Equipo[];
  onCerrar: () => void;
}

const RIVALES_COMUNES = [
  { nombre: "The Strongest (Amarillo/Oro)", hex: "#F2C200" },
  { nombre: "Wilstermann (Rojo/Escarlata)", hex: "#D32F2F" },
  { nombre: "Oriente Petrolero (Verde)", hex: "#15803D" },
  { nombre: "Always Ready (Rojo/Blanco)", hex: "#B91C1C" },
  { nombre: "Blooming (Celeste)", hex: "#4FC3F7" },
  { nombre: "Real Tomayapo (Verde Limón)", hex: "#84CC16" },
  { nombre: "San Antonio (Naranja)", hex: "#EA580C" },
  { nombre: "Rival con Blanco Puro", hex: "#FFFFFF" },
  { nombre: "Rival con Azul Marino", hex: "#1E3A8A" },
];

export function ColorVerificationModal({
  abierto,
  equipo,
  otrosEquipos,
  onCerrar,
}: ColorVerificationModalProps) {
  const [colorRival, setColorRival] = useState<string>("#F2C200");

  const esHexValido = /^#[0-9A-Fa-f]{6}$/.test(colorRival);

  // Consulta de verificación en backend mediante React Query
  const {
    data: resultado,
    isLoading: cargando,
    isError,
    error,
  } = useQuery({
    queryKey: ["verificar-color", equipo?.id, colorRival],
    queryFn: () => verificarColoresEquipo(equipo!.id, colorRival),
    enabled: abierto && Boolean(equipo) && esHexValido,
    retry: false,
  });

  if (!abierto || !equipo) return null;

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
        if (e.target === e.currentTarget) onCerrar();
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          width: "100%",
          maxWidth: 620,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0,0,0,0.25)",
          overflow: "hidden",
        }}
      >
        {/* Cabecera */}
        <div
          style={{
            padding: "16px 20px",
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
              CU-10 · Verificador de Contraste Óptico (HSV)
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 17, fontWeight: 800, color: "var(--text)" }}>
              Contraste de Indumentaria vs. Rival
            </h3>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            style={{
              all: "unset",
              cursor: "pointer",
              fontSize: 18,
              lineHeight: 1,
              color: "var(--text-3)",
              padding: "4px 8px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Contenido */}
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18, overflowY: "auto" }}>
          {/* Comparación visual de camisetas cara a cara */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto 1fr",
              alignItems: "center",
              gap: 16,
              padding: 18,
              borderRadius: 8,
              background: "var(--ground)",
              border: "1px solid var(--line)",
            }}
          >
            {/* Tu equipo */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <JerseyPreview color={equipo.color_local} size="lg" />
              <div style={{ textAlign: "center" }}>
                <strong style={{ fontSize: 13, color: "var(--text)" }}>{equipo.nombre}</strong>
                <p style={{ margin: 0, fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
                  Local ({equipo.color_local})
                </p>
              </div>
            </div>

            {/* Marcador VS */}
            <div
              style={{
                fontSize: 14,
                fontWeight: 900,
                color: "var(--text-3)",
                padding: "6px 12px",
                borderRadius: 20,
                background: "var(--surface)",
                border: "1px solid var(--line)",
              }}
            >
              VS
            </div>

            {/* Equipo Rival */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <JerseyPreview color={esHexValido ? colorRival : "#999999"} size="lg" />
              <div style={{ textAlign: "center" }}>
                <strong style={{ fontSize: 13, color: "var(--text)" }}>Equipo Rival</strong>
                <p style={{ margin: 0, fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
                  Indumentaria ({colorRival})
                </p>
              </div>
            </div>
          </div>

          {/* Resultado de la verificación */}
          {cargando && (
            <div style={{ textAlign: "center", padding: 12, fontSize: 13, color: "var(--text-3)" }}>
              Calculando contraste cilíndrico en espacio HSV…
            </div>
          )}

          {isError && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 6,
                background: "rgba(224, 112, 92, 0.12)",
                border: "1px solid var(--risk)",
                color: "var(--risk)",
                fontSize: 12,
              }}
            >
              {(error as any)?.response?.data?.detail ?? "Error al verificar colores con el servidor"}
            </div>
          )}

          {resultado && !cargando && (
            <div
              style={{
                padding: "14px 16px",
                borderRadius: 8,
                background: resultado.hay_riesgo ? "rgba(162, 55, 42, 0.1)" : "rgba(11, 107, 69, 0.1)",
                border: resultado.hay_riesgo ? "1.5px solid var(--risk)" : "1.5px solid var(--pitch)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>{resultado.hay_riesgo ? "⚠️" : "✅"}</span>
                  <strong
                    style={{
                      fontSize: 14,
                      color: resultado.hay_riesgo ? "var(--risk)" : "var(--pitch)",
                    }}
                  >
                    {resultado.hay_riesgo ? "Riesgo de Confusión Óptica" : "Contraste Aprobado"}
                  </strong>
                </div>

                <span
                  style={{
                    fontSize: 11.5,
                    fontFamily: "monospace",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontWeight: 700,
                    backgroundColor: resultado.hay_riesgo ? "var(--risk)" : "var(--pitch)",
                    color: "#fff",
                  }}
                >
                  Distancia HSV: {resultado.distancia_hsv.toFixed(1)} {resultado.hay_riesgo ? "< 40" : "≥ 40"}
                </span>
              </div>

              <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: "var(--text)" }}>
                {resultado.mensaje}
              </p>
            </div>
          )}

          {/* Selector interactivo de color rival */}
          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                fontWeight: 700,
                color: "var(--text)",
                marginBottom: 8,
              }}
            >
              Elegir o personalizar color del rival:
            </label>

            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <input
                type="color"
                value={esHexValido ? colorRival : "#F2C200"}
                onChange={(e) => setColorRival(e.target.value.toUpperCase())}
                style={{
                  width: 42,
                  height: 38,
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  cursor: "pointer",
                  background: "var(--ground)",
                }}
              />
              <input
                type="text"
                value={colorRival}
                maxLength={7}
                onChange={(e) => setColorRival(e.target.value.toUpperCase())}
                style={{
                  width: 120,
                  padding: "8px 10px",
                  fontSize: 13,
                  fontFamily: "monospace",
                  fontWeight: 600,
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  background: "var(--ground)",
                  color: "var(--text)",
                }}
              />
            </div>

            {/* Rivales típicos preestablecidos */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)" }}>
                Rivales y patrones de contraste frecuentes:
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {RIVALES_COMUNES.map((r) => (
                  <button
                    key={r.hex + r.nombre}
                    type="button"
                    onClick={() => setColorRival(r.hex)}
                    style={{
                      all: "unset",
                      cursor: "pointer",
                      padding: "4px 8px",
                      borderRadius: 4,
                      fontSize: 11.5,
                      background: colorRival.toUpperCase() === r.hex.toUpperCase() ? "var(--pitch)" : "var(--ground)",
                      color: colorRival.toUpperCase() === r.hex.toUpperCase() ? "#fff" : "var(--text-2)",
                      border: "1px solid var(--line)",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        backgroundColor: r.hex,
                        border: "1px solid rgba(0,0,0,0.2)",
                      }}
                    />
                    {r.nombre}
                  </button>
                ))}
              </div>
            </div>

            {/* Otros equipos del mismo club para comparar amistosos o prácticas internas */}
            {otrosEquipos.filter((e) => e.id !== equipo.id).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", display: "block", marginBottom: 6 }}>
                  Comparar con otro equipo del club (entrenamientos o amistosos internos):
                </span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {otrosEquipos
                    .filter((e) => e.id !== equipo.id)
                    .map((otro) => (
                      <button
                        key={otro.id}
                        type="button"
                        onClick={() => setColorRival(otro.color_local)}
                        style={{
                          all: "unset",
                          cursor: "pointer",
                          padding: "4px 8px",
                          borderRadius: 4,
                          fontSize: 11.5,
                          background: "var(--ground)",
                          color: "var(--text-2)",
                          border: "1px solid var(--line)",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                        }}
                      >
                        <span
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            backgroundColor: otro.color_local,
                            border: "1px solid rgba(0,0,0,0.2)",
                          }}
                        />
                        {otro.nombre} ({otro.color_local})
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid var(--line)",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="button"
            onClick={onCerrar}
            style={{
              all: "unset",
              cursor: "pointer",
              padding: "7px 16px",
              fontSize: 12.5,
              fontWeight: 600,
              color: "var(--text)",
              background: "var(--ground)",
              borderRadius: 6,
              border: "1px solid var(--line)",
            }}
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
