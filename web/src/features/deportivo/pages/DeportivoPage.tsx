import { useState } from "react";
import { AlineacionView } from "../components/AlineacionView";
import { EquiposView } from "../components/EquiposView";
import { IndumentariaView } from "../components/IndumentariaView";
import { JugadoresView } from "../components/JugadoresView";
import { PartidosView } from "../components/PartidosView";

type SeccionDeportivo = "equipos" | "indumentaria" | "jugadores" | "partidos" | "alineacion";

export function DeportivoPage() {
  const [seccionActiva, setSeccionActiva] = useState<SeccionDeportivo>("equipos");
  const [equipoIndumentariaId, setEquipoIndumentariaId] = useState<number | null>(null);

  const handleIrIndumentaria = (equipoId?: number) => {
    setEquipoIndumentariaId(equipoId ?? null);
    setSeccionActiva("indumentaria");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* Cabecera del Módulo Deportivo */}
      <header className="page-head" style={{ marginBottom: 0 }}>
        <span className="kicker">P2 · GESTIÓN DEPORTIVA (CU-09 … CU-17)</span>
        <h2 style={{ margin: "4px 0 6px" }}>Equipos, Indumentaria, Plantel y Calendario</h2>
        <p
          style={{
            margin: 0,
            color: "var(--text-2)",
            fontSize: 13.5,
            maxWidth: 740,
          }}
        >
          Administra de forma organizada las divisiones y planteles del club (<strong>CU-09</strong>
          ), registra y valida ópticamente la indumentaria oficial en espacio HSV (
          <strong>CU-10</strong>) y gestiona las fichas antropométricas de los futbolistas (
          <strong>CU-11, CU-12</strong>).
        </p>
      </header>

      {/* Navegación de Secciones del Módulo Deportivo */}
      <div
        style={{
          display: "flex",
          gap: 6,
          borderBottom: "1px solid var(--line)",
          paddingBottom: 0,
          overflowX: "auto",
        }}
      >
        {(
          [
            {
              id: "equipos",
              label: "Gestionar Equipos",
              cu: "CU-09",
            },
            {
              id: "indumentaria",
              label: "Indumentaria de Equipo",
              cu: "CU-10",
            },
            {
              id: "jugadores",
              label: "Plantel de Jugadores",
              cu: "CU-11, CU-12",
            },
            {
              id: "partidos",
              label: "Competiciones y Calendario",
              cu: "CU-13 … CU-16",
            },
            {
              id: "alineacion",
              label: "Alineaciones y Pizarra",
              cu: "CU-17",
            },
          ] as const
        ).map((tab) => {
          const activa = seccionActiva === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                if (tab.id !== "indumentaria") {
                  setEquipoIndumentariaId(null);
                }
                setSeccionActiva(tab.id);
              }}
              style={{
                all: "unset",
                cursor: "pointer",
                padding: "10px 16px",
                borderBottom: activa ? "2.5px solid var(--pitch)" : "2.5px solid transparent",
                color: activa ? "var(--text)" : "var(--text-3)",
                fontWeight: activa ? 700 : 500,
                fontSize: 13.5,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                whiteSpace: "nowrap",
                transition: "color 0.15s ease, border-color 0.15s ease",
              }}
            >
              <span>{tab.label}</span>
              <span
                style={{
                  fontSize: 10.5,
                  fontFamily: "var(--font-mono)",
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: activa ? "rgba(13, 148, 136, 0.14)" : "var(--ground)",
                  color: activa ? "var(--pitch)" : "var(--text-3)",
                }}
              >
                {tab.cu}
              </span>
            </button>
          );
        })}
      </div>

      {/* Renderizado de la Sección Activa */}
      {seccionActiva === "equipos" && <EquiposView onIrIndumentaria={handleIrIndumentaria} />}
      {seccionActiva === "indumentaria" && (
        <IndumentariaView equipoInicialId={equipoIndumentariaId} />
      )}
      {seccionActiva === "jugadores" && <JugadoresView />}

      {seccionActiva === "partidos" && <PartidosView />}

      {seccionActiva === "alineacion" && <AlineacionView />}
    </div>
  );
}
