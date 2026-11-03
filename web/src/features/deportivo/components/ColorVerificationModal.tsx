import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { JerseyPreview } from "./JerseyPreview";
import { verificarColoresEquipo } from "../api";
import { calcularDistanciaHsv } from "../types";
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
  { nombre: "Rival Blanco Puro", hex: "#FFFFFF" },
  { nombre: "Rival Azul Marino", hex: "#1E3A8A" },
  { nombre: "Rival Negro Azabache", hex: "#18181B" },
];

export function ColorVerificationModal({
  abierto,
  equipo,
  otrosEquipos: _otrosEquipos,
  onCerrar,
}: ColorVerificationModalProps) {
  const [kitNuestro, setKitNuestro] = useState<"local" | "visitante">("local");
  const [colorRival, setColorRival] = useState<string>("#F2C200");

  const esHexValido = /^#[0-9A-Fa-f]{6}$/.test(colorRival);

  // Consulta de verificación en backend para el uniforme titular
  const { isError, error } = useQuery({
    queryKey: ["verificar-color", equipo?.id, colorRival],
    queryFn: () => verificarColoresEquipo(equipo!.id, colorRival),
    enabled: abierto && Boolean(equipo) && esHexValido,
    retry: false,
  });

  // Cálculo en frontend para contraste inmediato de ambos kits (Titular y Alternativo)
  const analisisKits = useMemo(() => {
    if (!equipo || !esHexValido) return null;

    const distTitular = calcularDistanciaHsv(equipo.color_local, colorRival) ?? 999;
    const distAlternativa = calcularDistanciaHsv(equipo.color_visitante, colorRival) ?? 999;

    const titularEnRiesgo = distTitular < 40;
    const alternativaEnRiesgo = distAlternativa < 40;

    return {
      distTitular,
      distAlternativa,
      titularEnRiesgo,
      alternativaEnRiesgo,
      colorActivo: kitNuestro === "local" ? equipo.color_local : equipo.color_visitante,
      distActiva: kitNuestro === "local" ? distTitular : distAlternativa,
      hayRiesgoActivo: kitNuestro === "local" ? titularEnRiesgo : alternativaEnRiesgo,
    };
  }, [equipo, colorRival, esHexValido, kitNuestro]);

  if (!abierto || !equipo) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
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
          maxWidth: 640,
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0,0,0,0.3)",
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
              CU-10 · Verificador Óptico de Partido vs Rival
            </span>
            <h3 style={{ margin: "2px 0 0", fontSize: 17, fontWeight: 800, color: "var(--text)" }}>
              Contraste de Indumentaria: {equipo.nombre} vs. Rival
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

        {/* Contenido del modal */}
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16, overflowY: "auto" }}>
          {/* Selector de kit de nuestro equipo (Titular o Alternativo) */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>
              Indumentaria a utilizar en el partido:
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => setKitNuestro("local")}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  padding: "5px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 700,
                  background: kitNuestro === "local" ? "var(--pitch)" : "var(--ground)",
                  color: kitNuestro === "local" ? "#fff" : "var(--text-2)",
                  border: "1px solid var(--line)",
                }}
              >
                Titular ({equipo.color_local})
              </button>
              <button
                type="button"
                onClick={() => setKitNuestro("visitante")}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  padding: "5px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 700,
                  background: kitNuestro === "visitante" ? "var(--pitch)" : "var(--ground)",
                  color: kitNuestro === "visitante" ? "#fff" : "var(--text-2)",
                  border: "1px solid var(--line)",
                }}
              >
                Alternativa ({equipo.color_visitante})
              </button>
            </div>
          </div>

          {/* Comparación visual cara a cara */}
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
            {/* Nuestro equipo */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <JerseyPreview color={analisisKits?.colorActivo ?? equipo.color_local} size="lg" />
              <div style={{ textAlign: "center" }}>
                <strong style={{ fontSize: 13, color: "var(--text)" }}>{equipo.nombre}</strong>
                <p style={{ margin: 0, fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
                  {kitNuestro === "local" ? "Titular" : "Alternativa"} ({analisisKits?.colorActivo})
                </p>
              </div>
            </div>

            {/* Marcador VS */}
            <div
              style={{
                fontSize: 13,
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
          {analisisKits && (
            <div
              style={{
                padding: "14px 16px",
                borderRadius: 8,
                background: analisisKits.hayRiesgoActivo
                  ? "rgba(162, 55, 42, 0.1)"
                  : "rgba(11, 107, 69, 0.1)",
                border: analisisKits.hayRiesgoActivo
                  ? "1.5px solid var(--risk)"
                  : "1.5px solid var(--pitch)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <strong
                    style={{
                      fontSize: 14,
                      color: analisisKits.hayRiesgoActivo ? "var(--risk)" : "var(--pitch)",
                    }}
                  >
                    {analisisKits.hayRiesgoActivo ? "Riesgo de Confusión Óptica" : "Contraste Óptico Aprobado"}
                  </strong>
                </div>

                <span
                  style={{
                    fontSize: 11.5,
                    fontFamily: "monospace",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontWeight: 700,
                    backgroundColor: analisisKits.hayRiesgoActivo ? "var(--risk)" : "var(--pitch)",
                    color: "#fff",
                  }}
                >
                  Distancia HSV: {analisisKits.distActiva.toFixed(1)} {analisisKits.hayRiesgoActivo ? "< 40" : "≥ 40"}
                </span>
              </div>

              <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: "var(--text)" }}>
                {analisisKits.hayRiesgoActivo
                  ? `La indumentaria ${kitNuestro === "local" ? "titular" : "alternativa"} está muy próxima a la del rival en espacio HSV (distancia ${analisisKits.distActiva.toFixed(1)} < 40). El pipeline de visión computacional podría confundir a los jugadores.`
                  : `Contraste adecuado: la distancia en espacio HSV (${analisisKits.distActiva.toFixed(1)} ≥ 40) garantiza una segmentación nítida de ambos planteles.`}
              </p>

              {/* Recomendación inteligente de cambio a indumentaria alternativa */}
              {analisisKits.titularEnRiesgo && kitNuestro === "local" && (
                <div
                  style={{
                    marginTop: 10,
                    padding: "10px 12px",
                    borderRadius: 6,
                    background: "var(--surface)",
                    border: "1px dashed var(--line)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <span style={{ fontSize: 12, color: "var(--text)" }}>
                    <strong>Sugerencia:</strong> {!analisisKits.alternativaEnRiesgo
                      ? `La indumentaria alternativa (${equipo.color_visitante}) sí contrasta adecuadamente (distancia ${analisisKits.distAlternativa.toFixed(1)} ≥ 40).`
                      : "La indumentaria alternativa también presenta similitud. Conviene registrar o cambiar el color del rival."}
                  </span>
                  {!analisisKits.alternativaEnRiesgo && (
                    <button
                      type="button"
                      onClick={() => setKitNuestro("visitante")}
                      style={{
                        all: "unset",
                        cursor: "pointer",
                        padding: "4px 10px",
                        fontSize: 11.5,
                        fontWeight: 700,
                        color: "#fff",
                        background: "var(--pitch)",
                        borderRadius: 4,
                      }}
                    >
                      Probar con Alternativa
                    </button>
                  )}
                </div>
              )}
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
              {(error as any)?.response?.data?.detail ?? "Error al sincronizar con el backend"}
            </div>
          )}

          {/* Configuración del color del Rival */}
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
              Configurar color del uniforme rival:
            </label>

            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <input
                type="color"
                value={esHexValido ? colorRival : "#F2C200"}
                onChange={(e) => setColorRival(e.target.value.toUpperCase())}
                style={{
                  width: 44,
                  height: 40,
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
                placeholder="#RRGGBB"
                onChange={(e) => setColorRival(e.target.value.toUpperCase())}
                style={{
                  width: 140,
                  padding: "8px 12px",
                  fontSize: 13,
                  fontFamily: "monospace",
                  fontWeight: 700,
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  background: "var(--ground)",
                  color: "var(--text)",
                }}
              />
              <span style={{ fontSize: 11.5, color: "var(--text-3)" }}>
                Ingresa el código hexadecimal del visitante o selecciona un rival de la lista:
              </span>
            </div>

            {/* Rivales típicos preestablecidos */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)" }}>
                Rivales frecuentes para calibración de partido:
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
                      padding: "5px 10px",
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
              padding: "7px 18px",
              fontSize: 12.5,
              fontWeight: 700,
              color: "#fff",
              background: "var(--pitch)",
              borderRadius: 6,
            }}
          >
            Aceptar y Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
