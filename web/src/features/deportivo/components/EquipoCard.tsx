import { JerseyPreview } from "./JerseyPreview";
import type { Equipo } from "../types";

interface EquipoCardProps {
  equipo: Equipo;
  tieneConflictoConOtro?: boolean;
  otroEquipoEnConflicto?: string;
  onEditar: (equipo: Equipo) => void;
  onVerificarRival: (equipo: Equipo) => void;
  onDesactivar: (equipo: Equipo) => void;
}

export function EquipoCard({
  equipo,
  tieneConflictoConOtro,
  otroEquipoEnConflicto,
  onEditar,
  onVerificarRival,
  onDesactivar,
}: EquipoCardProps) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: tieneConflictoConOtro ? "1.5px solid var(--risk)" : "1px solid var(--line)",
        borderRadius: 8,
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: 16,
        boxShadow: "0 2px 5px rgba(0,0,0,0.04)",
        transition: "border-color 0.15s, transform 0.15s, box-shadow 0.15s",
        position: "relative",
        opacity: equipo.activo ? 1 : 0.65,
      }}
    >
      {/* Indicador de estado / advertencia de conflicto de color */}
      {tieneConflictoConOtro && (
        <div
          title={`Color muy similar al de ${otroEquipoEnConflicto}`}
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            background: "rgba(162, 55, 42, 0.12)",
            color: "var(--risk)",
            border: "1px solid var(--risk)",
            padding: "2px 8px",
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span>⚠️</span> Conflicto Óptico
        </div>
      )}

      {/* Encabezado de la tarjeta */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--pitch)",
              background: "rgba(11, 107, 69, 0.08)",
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            EQ-{equipo.id.toString().padStart(2, "0")}
          </span>

          {equipo.categoria && (
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
              {equipo.categoria}
            </span>
          )}

          {equipo.temporada && (
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
              {equipo.temporada}
            </span>
          )}

          {!equipo.activo && (
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
          {equipo.nombre}
        </h3>

        <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-3)" }}>
          {equipo.jugadores === 1
            ? "1 jugador registrado"
            : `${equipo.jugadores} jugadores registrados`}
        </p>
      </div>

      {/* Visualización de la indumentaria (los 3 colores del equipo) */}
      <div
        style={{
          background: "var(--ground)",
          borderRadius: 6,
          padding: "12px 14px",
          border: "1px solid var(--line)",
        }}
      >
        <span
          style={{
            display: "block",
            fontSize: 11,
            fontWeight: 700,
            color: "var(--text-2)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: 8,
          }}
        >
          Juegos de Indumentaria (CU-10)
        </span>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, textAlign: "center" }}>
          {/* Titular */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <JerseyPreview color={equipo.color_local} size="sm" />
            <span style={{ fontSize: 10.5, fontWeight: 700, marginTop: 4, color: "var(--text)" }}>
              Titular
            </span>
            <span style={{ fontSize: 9.5, fontFamily: "monospace", color: "var(--text-3)" }}>
              {equipo.color_local}
            </span>
          </div>

          {/* Alternativa */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <JerseyPreview color={equipo.color_visitante} size="sm" />
            <span style={{ fontSize: 10.5, fontWeight: 700, marginTop: 4, color: "var(--text)" }}>
              Alternativa
            </span>
            <span style={{ fontSize: 9.5, fontFamily: "monospace", color: "var(--text-3)" }}>
              {equipo.color_visitante}
            </span>
          </div>

          {/* Arquero */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <JerseyPreview color={equipo.color_arquero} size="sm" />
            <span style={{ fontSize: 10.5, fontWeight: 700, marginTop: 4, color: "var(--text)" }}>
              Arquero
            </span>
            <span style={{ fontSize: 9.5, fontFamily: "monospace", color: "var(--text-3)" }}>
              {equipo.color_arquero}
            </span>
          </div>
        </div>
      </div>

      {/* Botones de acción */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          paddingTop: 10,
          borderTop: "1px solid var(--line)",
        }}
      >
        <button
          type="button"
          onClick={() => onVerificarRival(equipo)}
          title="Verificar contraste óptico contra uniforme rival"
          style={{
            all: "unset",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 600,
            color: "var(--pitch)",
            background: "rgba(11, 107, 69, 0.08)",
            padding: "5px 10px",
            borderRadius: 4,
            transition: "background 0.1s",
          }}
        >
          Probar Rival
        </button>

        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            onClick={() => onEditar(equipo)}
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

          {equipo.activo && (
            <button
              type="button"
              onClick={() => onDesactivar(equipo)}
              title="Dar de baja lógica al equipo"
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
              Desactivar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
