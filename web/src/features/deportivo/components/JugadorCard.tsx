import { ETIQUETAS_POSICION, ETIQUETAS_PIE } from "../types";
import type { Jugador } from "../types";

interface JugadorCardProps {
  jugador: Jugador;
  onEditar: (jugador: Jugador) => void;
  onBaja: (jugador: Jugador) => void;
}

export function JugadorCard({ jugador, onEditar, onBaja }: JugadorCardProps) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: 8,
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: 16,
        boxShadow: "0 2px 5px rgba(0,0,0,0.04)",
        transition: "border-color 0.15s, transform 0.15s, box-shadow 0.15s",
        opacity: jugador.activo ? 1 : 0.65,
      }}
    >
      {/* Encabezado de la tarjeta */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
            marginBottom: 6,
          }}
        >
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 13,
              fontWeight: 800,
              color: "var(--pitch)",
              background: "rgba(11, 107, 69, 0.08)",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            #{jugador.dorsal}
          </span>

          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--text-3)",
              background: "var(--ground)",
              padding: "2px 7px",
              borderRadius: 4,
              border: "1px solid var(--line)",
            }}
          >
            {ETIQUETAS_POSICION[jugador.posicion]}
          </span>

          {!jugador.activo && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--risk)",
                background: "rgba(162, 55, 42, 0.1)",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              Inactivo
            </span>
          )}
        </div>

        <h3
          style={{
            margin: "4px 0 0",
            fontSize: 17,
            fontWeight: 800,
            color: "var(--text)",
            letterSpacing: "-0.01em",
          }}
        >
          {jugador.nombre} {jugador.apellido}
        </h3>

        <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-3)" }}>
          Pie {ETIQUETAS_PIE[jugador.pie_habil]} · {jugador.altura_cm} cm
          {jugador.peso_kg != null ? ` · ${jugador.peso_kg} kg` : ""}
        </p>
      </div>

      {/* Botones de acción */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: 8,
          paddingTop: 10,
          borderTop: "1px solid var(--line)",
        }}
      >
        <button
          type="button"
          onClick={() => onEditar(jugador)}
          style={{
            all: "unset",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 600,
            color: "var(--text-2)",
            background: "var(--ground)",
            border: "1px solid var(--line)",
            padding: "5px 10px",
            borderRadius: 4,
          }}
        >
          Editar
        </button>

        {jugador.activo && (
          <button
            type="button"
            onClick={() => onBaja(jugador)}
            title="Dar de baja lógica al jugador (conserva su historial)"
            style={{
              all: "unset",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
              color: "var(--risk)",
              padding: "5px 8px",
              borderRadius: 4,
            }}
          >
            Dar de baja
          </button>
        )}
      </div>
    </div>
  );
}
