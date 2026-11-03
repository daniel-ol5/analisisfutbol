import type { Equipo } from "../types";

interface EquipoCardProps {
  equipo: Equipo;
  onVer: (equipo: Equipo) => void;
  onEditar: (equipo: Equipo) => void;
  onDesactivar: (equipo: Equipo) => void;
  onReactivar?: (equipo: Equipo) => void;
  onIrIndumentaria?: (equipo: Equipo) => void;
}

export function EquipoCard({
  equipo,
  onVer,
  onEditar,
  onDesactivar,
  onReactivar,
  onIrIndumentaria,
}: EquipoCardProps) {
  return (
    <article
      className="equipo-card"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: 10,
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        position: "relative",
        opacity: equipo.activo ? 1 : 0.72,
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
      }}
    >
      {/* Cabecera del Equipo */}
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
              flexWrap: "wrap",
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
                fontSize: 10.5,
                fontWeight: 800,
                padding: "2px 8px",
                borderRadius: 99,
                background: equipo.activo
                  ? "rgba(13, 148, 136, 0.14)"
                  : "rgba(224, 112, 92, 0.15)",
                color: equipo.activo ? "var(--pitch)" : "var(--risk)",
                letterSpacing: "0.04em",
              }}
            >
              {equipo.activo ? "ACTIVO" : "INACTIVO"}
            </span>
          </div>

          <h3
            onClick={() => onVer(equipo)}
            style={{
              margin: "8px 0 3px",
              fontSize: 18,
              fontWeight: 800,
              color: "var(--text)",
              cursor: "pointer",
            }}
            title="Haz clic para ver la ficha completa del equipo"
          >
            {equipo.nombre}
          </h3>
        </div>

        {/* Mini indicador de colores (acceso rápido a CU-10 sin saturar la tarjeta) */}
        <button
          type="button"
          onClick={() =>
            onIrIndumentaria ? onIrIndumentaria(equipo) : onVer(equipo)
          }
          title="Ver / configurar indumentaria oficial (CU-10)"
          style={{
            all: "unset",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "5px 8px",
            borderRadius: 99,
            background: "var(--ground)",
            border: "1px solid var(--line)",
          }}
        >
          {[equipo.color_local, equipo.color_visitante, equipo.color_arquero].map(
            (hex, idx) => (
              <span
                key={idx}
                style={{
                  width: 11,
                  height: 11,
                  borderRadius: "50%",
                  backgroundColor: hex,
                  border: "1px solid rgba(0,0,0,0.28)",
                }}
              />
            ),
          )}
          <span
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              color: "var(--text-2)",
              marginLeft: 2,
            }}
          >
            Kits
          </span>
        </button>
      </div>

      {/* Datos principales del equipo (CU-09) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 10,
          padding: 12,
          borderRadius: 8,
          background: "var(--ground)",
          border: "1px solid var(--line)",
        }}
      >
        <div style={{ gridColumn: "1 / -1" }}>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            Categoría / División
          </div>
          <div
            style={{
              fontSize: 13.5,
              fontWeight: 700,
              color: "var(--text)",
              marginTop: 2,
            }}
          >
            {equipo.categoria || "Categoría General"}
          </div>
        </div>

        <div>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            Temporada
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text)",
              marginTop: 2,
              fontFamily: "var(--font-mono)",
            }}
          >
            {equipo.temporada || "2026"}
          </div>
        </div>

        <div>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 700,
              color: "var(--text-3)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            Plantel Activo
          </div>
          <div
            style={{
              fontSize: 13,
              fontWeight: 800,
              color: "var(--pitch)",
              marginTop: 2,
            }}
          >
            {equipo.jugadores}{" "}
            {equipo.jugadores === 1 ? "jugador" : "jugadores"}
          </div>
        </div>
      </div>

      {/* Pie de acciones CRUD completas: Visualizar, Editar, Eliminar/Reactivar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid var(--line)",
          paddingTop: 12,
          marginTop: "auto",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={() => onVer(equipo)}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid var(--line)",
            background: "var(--ground)",
            color: "var(--text)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Ver ficha
        </button>

        <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
          <button
            type="button"
            onClick={() => onEditar(equipo)}
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
            Editar
          </button>

          {equipo.activo ? (
            <button
              type="button"
              onClick={() => onDesactivar(equipo)}
              title="Dar de baja lógica al equipo (conserva su historial)"
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
              Dar de baja
            </button>
          ) : (
            onReactivar && (
              <button
                type="button"
                onClick={() => onReactivar(equipo)}
                title="Reactivar equipo en el club"
                style={{
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--pitch)",
                  background: "var(--pitch)",
                  color: "#fff",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Reactivar
              </button>
            )
          )}
        </div>
      </div>
    </article>
  );
}
