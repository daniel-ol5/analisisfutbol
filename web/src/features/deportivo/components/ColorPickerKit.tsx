import { useState } from "react";
import { JerseyPreview } from "./JerseyPreview";
import { calcularDistanciaHsv } from "../types";

interface ColorPickerKitProps {
  colorLocal: string;
  colorVisitante: string;
  colorArquero: string;
  onChangeLocal: (color: string) => void;
  onChangeVisitante: (color: string) => void;
  onChangeArquero: (color: string) => void;
}

const PALETA_FUTBOL = [
  { nombre: "Azul Real", hex: "#1E5AA8" },
  { nombre: "Celeste", hex: "#4FC3F7" },
  { nombre: "Blanco", hex: "#FFFFFF" },
  { nombre: "Negro", hex: "#18181B" },
  { nombre: "Rojo Furia", hex: "#DC2626" },
  { nombre: "Granate", hex: "#7F1D1D" },
  { nombre: "Verde Césped", hex: "#15803D" },
  { nombre: "Verde Flúor", hex: "#10B981" },
  { nombre: "Amarillo Oro", hex: "#F2C200" },
  { nombre: "Naranja", hex: "#EA580C" },
  { nombre: "Púrpura", hex: "#7E22CE" },
  { nombre: "Gris Plata", hex: "#94A3B8" },
];

export function ColorPickerKit({
  colorLocal,
  colorVisitante,
  colorArquero,
  onChangeLocal,
  onChangeVisitante,
  onChangeArquero,
}: ColorPickerKitProps) {
  const [pestañaActiva, setPestañaActiva] = useState<"local" | "visitante" | "arquero">("local");

  // Validación de contraste interno
  const distLocalVisitante = calcularDistanciaHsv(colorLocal, colorVisitante);
  const distLocalArquero = calcularDistanciaHsv(colorLocal, colorArquero);
  const distVisitanteArquero = calcularDistanciaHsv(colorVisitante, colorArquero);

  const conflictoInterno =
    (distLocalVisitante !== null && distLocalVisitante < 40) ||
    (distLocalArquero !== null && distLocalArquero < 40) ||
    (distVisitanteArquero !== null && distVisitanteArquero < 40);

  const kitActual = {
    local: {
      titulo: "Indumentaria Titular (Local)",
      subtitulo: "Color principal del uniforme de campo para partidos de local",
      color: colorLocal,
      onChange: onChangeLocal,
    },
    visitante: {
      titulo: "Indumentaria Alternativa (Visitante)",
      subtitulo: "Utilizada en caso de conflicto de indumentaria con el adversario",
      color: colorVisitante,
      onChange: onChangeVisitante,
    },
    arquero: {
      titulo: "Indumentaria de Guardameta (Arquero)",
      subtitulo: "Debe ser estrictamente contrastante con ambos equipos y árbitros",
      color: colorArquero,
      onChange: onChangeArquero,
    },
  }[pestañaActiva];

  return (
    <div className="kit-color-picker" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Vista previa de las 3 camisetas del equipo */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
          padding: 16,
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 8,
        }}
      >
        <button
          type="button"
          onClick={() => setPestañaActiva("local")}
          style={{
            all: "unset",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 6px",
            borderRadius: 6,
            background: pestañaActiva === "local" ? "rgba(11, 107, 69, 0.08)" : "transparent",
            border: pestañaActiva === "local" ? "2px solid var(--pitch)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <JerseyPreview color={colorLocal} size="md" />
          <span style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--text)" }}>
            Local
          </span>
          <span style={{ fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
            {colorLocal}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setPestañaActiva("visitante")}
          style={{
            all: "unset",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 6px",
            borderRadius: 6,
            background: pestañaActiva === "visitante" ? "rgba(11, 107, 69, 0.08)" : "transparent",
            border: pestañaActiva === "visitante" ? "2px solid var(--pitch)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <JerseyPreview color={colorVisitante} size="md" />
          <span style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--text)" }}>
            Visitante
          </span>
          <span style={{ fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
            {colorVisitante}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setPestañaActiva("arquero")}
          style={{
            all: "unset",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 6px",
            borderRadius: 6,
            background: pestañaActiva === "arquero" ? "rgba(11, 107, 69, 0.08)" : "transparent",
            border: pestañaActiva === "arquero" ? "2px solid var(--pitch)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <JerseyPreview color={colorArquero} size="md" />
          <span style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--text)" }}>
            Arquero
          </span>
          <span style={{ fontSize: 11, fontFamily: "monospace", color: "var(--text-3)" }}>
            {colorArquero}
          </span>
        </button>
      </div>

      {/* Editor visual del kit seleccionado */}
      <div
        style={{
          border: "1px solid var(--line)",
          borderRadius: 8,
          padding: 16,
          background: "var(--surface)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--text)" }}>
              {kitActual.titulo}
            </h4>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--text-2)" }}>
              {kitActual.subtitulo}
            </p>
          </div>
          <JerseyPreview color={kitActual.color} size="sm" />
        </div>

        {/* Input de color HTML5 + Campo HEX */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
          <div
            style={{
              position: "relative",
              width: 44,
              height: 44,
              borderRadius: 6,
              overflow: "hidden",
              border: "1px solid var(--line)",
              cursor: "pointer",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            }}
          >
            <input
              type="color"
              value={kitActual.color}
              onChange={(e) => kitActual.onChange(e.target.value)}
              style={{
                position: "absolute",
                top: -8,
                left: -8,
                width: 64,
                height: 64,
                border: "none",
                cursor: "pointer",
                background: "transparent",
              }}
              title="Abrir selector de color"
            />
          </div>

          <div style={{ flex: 1 }}>
            <label
              style={{
                display: "block",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-3)",
                marginBottom: 4,
              }}
            >
              Código Hexadecimal (#RRGGBB)
            </label>
            <input
              type="text"
              value={kitActual.color}
              maxLength={7}
              placeholder="#1E5AA8"
              onChange={(e) => {
                const val = e.target.value.toUpperCase();
                kitActual.onChange(val);
              }}
              style={{
                width: "100%",
                maxWidth: 160,
                padding: "8px 12px",
                fontFamily: "monospace",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text)",
                background: "var(--ground)",
                border: "1px solid var(--line)",
                borderRadius: 4,
                outline: "none",
              }}
            />
          </div>
        </div>

        {/* Muestrario de colores habituales */}
        <div style={{ marginTop: 14 }}>
          <label
            style={{
              display: "block",
              fontSize: 11,
              fontWeight: 600,
              color: "var(--text-3)",
              marginBottom: 8,
            }}
          >
            Colores recomendados para fútbol:
          </label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {PALETA_FUTBOL.map((p) => {
              const esSeleccionado = kitActual.color.toUpperCase() === p.hex.toUpperCase();
              return (
                <button
                  key={p.hex}
                  type="button"
                  title={`${p.nombre} (${p.hex})`}
                  onClick={() => kitActual.onChange(p.hex)}
                  style={{
                    all: "unset",
                    cursor: "pointer",
                    width: 26,
                    height: 26,
                    borderRadius: 4,
                    backgroundColor: p.hex,
                    border: esSeleccionado ? "2px solid var(--pitch)" : "1px solid rgba(0,0,0,0.2)",
                    boxShadow: esSeleccionado ? "0 0 0 2px var(--surface)" : "none",
                    transform: esSeleccionado ? "scale(1.15)" : "scale(1)",
                    transition: "transform 0.1s ease",
                  }}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* Alerta si el equipo tiene colores de kit demasiado similares entre sí */}
      {conflictoInterno && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 6,
            background: "rgba(224, 112, 92, 0.1)",
            border: "1px solid var(--risk)",
            fontSize: 12,
            color: "var(--risk)",
            lineHeight: 1.4,
          }}
        >
          <strong>⚠️ Advertencia de contraste interno:</strong> Dos de las indumentarias de este equipo tienen
          tonalidades muy próximas en espacio HSV (distancia &lt; 40). Asegúrate de que la indumentaria visitante
          o de arquero contrasten claramente con la titular.
        </div>
      )}
    </div>
  );
}
