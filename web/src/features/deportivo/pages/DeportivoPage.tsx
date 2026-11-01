/**
 * Gestión Deportiva  —  P2 · CU-09 … CU-17
 *
 * T-041 (Sprint 2 · Daniel): Pantalla de alta y edición de equipos con selector visual de tres colores.
 * Criterio de aceptación: Advierte cuando dos equipos usan colores demasiado similares.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { EquiposView } from "../components/EquiposView";
import { JugadoresView } from "../components/JugadoresView";

const TABS = [
  {
    id: "equipos",
    titulo: "Equipos e Indumentaria",
    cus: "CU-09, CU-10",
    responsable: "Daniel",
    estado: "completado",
  },
  {
    id: "jugadores",
    titulo: "Plantel de Jugadores",
    cus: "CU-11, CU-12",
    responsable: "Alex",
    estado: "pendiente",
  },
  {
    id: "partidos",
    titulo: "Competiciones y Calendario",
    cus: "CU-13 … CU-16",
    responsable: "Susana",
    estado: "pendiente",
  },
  {
    id: "alineacion",
    titulo: "Alineaciones y Pizarra",
    cus: "CU-17",
    responsable: "Araceli",
    estado: "pendiente",
  },
];

export function DeportivoPage() {
  const [tabActiva, setTabActiva] = useState<string>("equipos");

  return (
    <main
      style={{
        maxWidth: 1100,
        margin: "0 auto",
        padding: "48px 24px 80px",
      }}
    >
      {/* Navegación de retorno */}
      <div style={{ marginBottom: 16 }}>
        <Link
          to="/"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--text-3)",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          ← Volver al Inicio
        </Link>
      </div>

      {/* Encabezado principal */}
      <header style={{ marginBottom: 28 }}>
        <p className="kicker">Paquete P2 · Sprint 2</p>
        <h1
          style={{
            fontSize: "clamp(28px, 4vw, 38px)",
            fontWeight: 800,
            letterSpacing: "-0.02em",
            margin: "8px 0 6px",
          }}
        >
          Gestión <em>Deportiva</em>
        </h1>
        <p className="dek" style={{ margin: 0 }}>
          Administración de planteles, indumentaria para visión artificial y calendario deportivo.
        </p>
      </header>

      {/* Selector de sub-módulos (Pestañas) */}
      <nav
        style={{
          display: "flex",
          gap: 8,
          borderBottom: "1px solid var(--line)",
          marginBottom: 28,
          overflowX: "auto",
        }}
      >
        {TABS.map((tab) => {
          const esActiva = tabActiva === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setTabActiva(tab.id)}
              style={{
                all: "unset",
                cursor: "pointer",
                padding: "10px 16px",
                fontSize: 13,
                fontWeight: esActiva ? 700 : 500,
                color: esActiva ? "var(--pitch)" : "var(--text-2)",
                borderBottom: esActiva ? "2px solid var(--pitch)" : "2px solid transparent",
                marginBottom: -1,
                display: "flex",
                alignItems: "center",
                gap: 8,
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              <span>{tab.titulo}</span>
              <span
                style={{
                  fontSize: 10,
                  fontFamily: "monospace",
                  padding: "1px 5px",
                  borderRadius: 3,
                  backgroundColor: esActiva ? "rgba(11, 107, 69, 0.12)" : "var(--ground)",
                  color: esActiva ? "var(--pitch)" : "var(--text-3)",
                  border: "1px solid var(--line)",
                }}
              >
                {tab.cus}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Contenido según pestaña activa */}
      {tabActiva === "equipos" && <EquiposView />}

      {tabActiva === "jugadores" && <JugadoresView />}

      {tabActiva === "partidos" && (
        <div
          style={{
            padding: 32,
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 8,
          }}
        >
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--pitch)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Sprint 2 · Susana · CU-13 … CU-16
          </span>
          <h3 style={{ margin: "6px 0 8px", fontSize: 18, color: "var(--text)" }}>
            Competiciones y Agenda de Partidos
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
            Programación de encuentros oficiales y amistosos, definición de torneos,
            reprogramaciones y cancelaciones de partidos.
          </p>
        </div>
      )}

      {tabActiva === "alineacion" && (
        <div
          style={{
            padding: 32,
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 8,
          }}
        >
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--pitch)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Sprint 2 · Araceli · CU-17
          </span>
          <h3 style={{ margin: "6px 0 8px", fontSize: 18, color: "var(--text)" }}>
            Alineación y Formación Táctica
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)", lineHeight: 1.6 }}>
            Pizarra táctica interactiva para definir el esquema inicial (4-3-3, 4-4-2, 4-2-3-1,
            3-5-2), titulares, suplentes y dirección de ataque en cada tiempo.
          </p>
        </div>
      )}
    </main>
  );
}
