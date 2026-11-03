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

interface GrupoColores {
  categoria: string;
  colores: Array<{ nombre: string; hex: string }>;
}

const PALETA_CLASICA_GRUPOS: GrupoColores[] = [
  {
    categoria: "Celestes y Azules",
    colores: [
      { nombre: "Celeste Bolívar", hex: "#1E5AA8" },
      { nombre: "Celeste Cielo", hex: "#4FC3F7" },
      { nombre: "Azul Marino", hex: "#0F172A" },
      { nombre: "Azul Real", hex: "#1E40AF" },
      { nombre: "Azul Francia", hex: "#2563EB" },
    ],
  },
  {
    categoria: "Rojos y Granates",
    colores: [
      { nombre: "Rojo Escarlata", hex: "#DC2626" },
      { nombre: "Granate / Bordó", hex: "#7F1D1D" },
      { nombre: "Carmín Intenso", hex: "#B91C1C" },
      { nombre: "Coral Furia", hex: "#F87171" },
    ],
  },
  {
    categoria: "Verdes",
    colores: [
      { nombre: "Verde Césped", hex: "#15803D" },
      { nombre: "Verde Oscuro", hex: "#14532D" },
      { nombre: "Verde Flúor / Lima", hex: "#10B981" },
      { nombre: "Verde Menta", hex: "#6EE7B7" },
    ],
  },
  {
    categoria: "Amarillos y Naranjas",
    colores: [
      { nombre: "Amarillo Oro", hex: "#F2C200" },
      { nombre: "Amarillo Canario", hex: "#FACC15" },
      { nombre: "Naranja Fuego", hex: "#EA580C" },
      { nombre: "Naranja Neón", hex: "#FB923C" },
    ],
  },
  {
    categoria: "Blancos, Grises y Negros",
    colores: [
      { nombre: "Blanco Puro", hex: "#FFFFFF" },
      { nombre: "Blanco Hueso", hex: "#F8FAFC" },
      { nombre: "Gris Plata", hex: "#94A3B8" },
      { nombre: "Gris Carbón", hex: "#334155" },
      { nombre: "Negro Azabache", hex: "#18181B" },
    ],
  },
  {
    categoria: "Especiales y Púrpuras",
    colores: [
      { nombre: "Púrpura / Morado", hex: "#7E22CE" },
      { nombre: "Violeta Profundo", hex: "#581C87" },
      { nombre: "Rosa Fucsia", hex: "#E11D48" },
    ],
  },
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

  const kitActual = {
    local: {
      tipo: "local" as const,
      titulo: "Indumentaria Titular (Local)",
      subtitulo: "Color institucional principal del equipo para partidos oficiales de local",
      color: colorLocal,
      onChange: onChangeLocal,
    },
    visitante: {
      tipo: "visitante" as const,
      titulo: "Indumentaria Alternativa (Visitante)",
      subtitulo: "Debe contrastar nítidamente con la indumentaria titular ante rivales similares",
      color: colorVisitante,
      onChange: onChangeVisitante,
    },
    arquero: {
      tipo: "arquero" as const,
      titulo: "Indumentaria de Guardameta (Arquero)",
      subtitulo: "Debe ser estrictamente contrastante con jugadores de campo y árbitros",
      color: colorArquero,
      onChange: onChangeArquero,
    },
  }[pestañaActiva];

  // Sanitizador de entrada hexadecimal
  const handleHexInputChange = (valor: string) => {
    let clean = valor.trim().toUpperCase();
    if (!clean.startsWith("#")) {
      clean = "#" + clean;
    }
    // Permitir escribir hasta 7 caracteres (#RRGGBB)
    if (clean.length <= 7) {
      kitActual.onChange(clean);
    }
  };

  return (
    <div className="kit-color-picker" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Selector de kits / camisetas 2D */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
          padding: 14,
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
            padding: "10px 8px",
            borderRadius: 6,
            background: pestañaActiva === "local" ? "rgba(11, 107, 69, 0.12)" : "transparent",
            border: pestañaActiva === "local" ? "2px solid var(--pitch)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <JerseyPreview color={colorLocal} size="md" />
          <span style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--text)" }}>
            Titular
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
            padding: "10px 8px",
            borderRadius: 6,
            background: pestañaActiva === "visitante" ? "rgba(11, 107, 69, 0.12)" : "transparent",
            border: pestañaActiva === "visitante" ? "2px solid var(--pitch)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <JerseyPreview color={colorVisitante} size="md" />
          <span style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--text)" }}>
            Alternativa
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
            padding: "10px 8px",
            borderRadius: 6,
            background: pestañaActiva === "arquero" ? "rgba(11, 107, 69, 0.12)" : "transparent",
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

      {/* Panel de Edición del Kit Seleccionado */}
      <div
        style={{
          border: "1px solid var(--line)",
          borderRadius: 8,
          padding: 16,
          background: "var(--surface)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: "var(--text)" }}>
              {kitActual.titulo}
            </h4>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--text-2)" }}>
              {kitActual.subtitulo}
            </p>
          </div>
          <JerseyPreview color={kitActual.color} size="sm" />
        </div>

        {/* Inputs de Color: Selector Nativo + Campo Hexadecimal */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: 12,
            background: "var(--ground)",
            border: "1px solid var(--line)",
            borderRadius: 6,
            flexWrap: "wrap",
          }}
        >
          {/* Círculo/Botón con selector nativo HTML5 */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                position: "relative",
                width: 42,
                height: 42,
                borderRadius: 8,
                overflow: "hidden",
                border: "2px solid var(--line)",
                cursor: "pointer",
                boxShadow: "0 2px 5px rgba(0,0,0,0.15)",
                backgroundColor: kitActual.color,
              }}
              title="Haz clic para abrir el selector de color libre"
            >
              <input
                type="color"
                value={/^#[0-9A-Fa-f]{6}$/.test(kitActual.color) ? kitActual.color : "#1E5AA8"}
                onChange={(e) => kitActual.onChange(e.target.value.toUpperCase())}
                style={{
                  position: "absolute",
                  top: -10,
                  left: -10,
                  width: 64,
                  height: 64,
                  border: "none",
                  cursor: "pointer",
                  opacity: 0,
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.3 }}>
              <span style={{ fontWeight: 600, color: "var(--text)" }}>Selector Libre</span>
              <br />
              Clic para rueda RGB
            </div>
          </div>

          {/* Campo de Código Hexadecimal */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 150 }}>
            <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)" }}>
              Código Hexadecimal (#RRGGBB)
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="text"
                value={kitActual.color}
                maxLength={7}
                placeholder="#1E5AA8"
                onChange={(e) => handleHexInputChange(e.target.value)}
                style={{
                  width: "100%",
                  maxWidth: 150,
                  padding: "7px 10px",
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 13,
                  fontWeight: 700,
                  color: "var(--text)",
                  background: "var(--surface)",
                  border: /^#[0-9A-Fa-f]{6}$/.test(kitActual.color)
                    ? "1px solid var(--line)"
                    : "1.5px solid var(--risk)",
                  borderRadius: 4,
                  outline: "none",
                }}
              />
              {pestañaActiva !== "local" && (
                <button
                  type="button"
                  onClick={() => kitActual.onChange(colorLocal)}
                  title="Copiar el color de la indumentaria titular"
                  style={{
                    all: "unset",
                    cursor: "pointer",
                    padding: "6px 10px",
                    fontSize: 11.5,
                    fontWeight: 600,
                    borderRadius: 4,
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    color: "var(--text-2)",
                    whiteSpace: "nowrap",
                  }}
                >
                  Usar base titular
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Paleta Clásica de Fútbol Organizada por Familias de Colores */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-2)", textTransform: "uppercase" }}>
            Paleta Clásica de Indumentaria
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {PALETA_CLASICA_GRUPOS.map((grupo) => (
              <div key={grupo.categoria} style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-3)",
                    minWidth: 120,
                  }}
                >
                  {grupo.categoria}:
                </span>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {grupo.colores.map((c) => {
                    const seleccionado = kitActual.color.toUpperCase() === c.hex.toUpperCase();
                    return (
                      <button
                        key={c.hex}
                        type="button"
                        title={`${c.nombre} (${c.hex})`}
                        onClick={() => kitActual.onChange(c.hex)}
                        style={{
                          all: "unset",
                          cursor: "pointer",
                          width: 24,
                          height: 24,
                          borderRadius: 4,
                          backgroundColor: c.hex,
                          border: seleccionado
                            ? "2px solid var(--pitch)"
                            : "1px solid rgba(0,0,0,0.25)",
                          boxShadow: seleccionado ? "0 0 0 2px var(--surface)" : "none",
                          transform: seleccionado ? "scale(1.2)" : "scale(1)",
                          transition: "all 0.1s ease",
                        }}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Alerta de contraste interno (Titular vs Alternativa o Titular vs Arquero) */}
      {(distLocalVisitante !== null && distLocalVisitante < 40) && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 6,
            background: "rgba(224, 112, 92, 0.1)",
            border: "1.5px solid var(--risk)",
            fontSize: 12,
            color: "var(--risk)",
            lineHeight: 1.4,
          }}
        >
          <strong>Advertencia de contraste interno (Titular - Alternativa):</strong> La indumentaria alternativa
          ({colorVisitante}) es muy próxima a la titular ({colorLocal}) en espacio HSV (distancia {distLocalVisitante.toFixed(1)} &lt; 40).
          Si un equipo rival viste similar a la titular, tu indumentaria alternativa tampoco resolverá la confusión óptica.
        </div>
      )}

      {(distLocalArquero !== null && distLocalArquero < 40) && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 6,
            background: "rgba(242, 194, 0, 0.12)",
            border: "1.5px solid #F2C200",
            fontSize: 12,
            color: "var(--text)",
            lineHeight: 1.4,
          }}
        >
          <strong>Contraste de Arquero:</strong> La indumentaria del guardameta ({colorArquero}) está cercana
          al uniforme titular ({colorLocal}). El reglamento exige que el arquero se distinga claramente del resto del equipo.
        </div>
      )}
    </div>
  );
}
