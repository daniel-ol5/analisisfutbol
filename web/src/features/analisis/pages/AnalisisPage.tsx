/**
 * Análisis Táctico  —  P5 · CU-40 … CU-48
 *
 * Módulo de seguimiento en vivo y métricas pospartido.
 * Implementa CU-40 (Panel del partido en vivo) y CU-41 (Plano 2D interactivo)
 * para el Sprint 3 (T-077, T-078).
 */

import { useState } from "react";

import { Pendiente } from "@/shared/ui/Pendiente";

import { MapaCalorCancha } from "../components/MapaCalorCancha";
import { PanelPartidoVivo } from "../components/PanelPartidoVivo";
import "../analisis.css";

type SeccionAnalisis = "vivo" | "calor" | "metricas" | "pases";

export function AnalisisPage() {
  const [seccionActiva, setSeccionActiva] = useState<SeccionAnalisis>("vivo");

  return (
    <div className="analisis-pagina">
      {/* Cabecera del Módulo de Análisis Táctico */}
      <header className="page-head" style={{ marginBottom: 0 }}>
        <h2 style={{ margin: "4px 0 6px" }}>Análisis del partido</h2>
        <p
          style={{
            margin: 0,
            color: "var(--text-2)",
            fontSize: 13.5,
            maxWidth: 780,
          }}
        >
          Revisa el video, las posiciones y las métricas observadas del partido.
        </p>
      </header>

      {/* Navegación por pestañas del módulo */}
      <div className="analisis-tabs">
        {[
          {
            id: "vivo" as const,
            label: "Partido",
            cu: "CU-40, CU-41 · Activo",
          },
          {
            id: "calor" as const,
            label: "Mapas de Calor",
            cu: "CU-44 · Sprint 3",
          },
          {
            id: "metricas" as const,
            label: "Métricas",
            cu: "CU-42, CU-43 · Sprint 4",
          },
          {
            id: "pases" as const,
            label: "Pases y evolución",
            cu: "CU-45 … CU-48 · Sprint 4",
          },
        ].map((tab) => {
          const activa = seccionActiva === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`analisis-tab-btn ${activa ? "analisis-tab-btn--activa" : ""}`}
              onClick={() => setSeccionActiva(tab.id)}
            >
              <span className="analisis-tab-label">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Contenido de la sección activa */}
      {seccionActiva === "vivo" && <PanelPartidoVivo />}

      {seccionActiva === "calor" && <MapaCalorCancha />}

      {seccionActiva === "metricas" && (
        <Pendiente
          paquete="P5"
          titulo="Métricas Tácticas y Físicas"
          casos={[
            "CU-42 Posesión y circulación",
            "CU-43 Métricas físicas por jugador",
            "CU-45 Métricas tácticas colectivas",
          ]}
        />
      )}

      {seccionActiva === "pases" && (
        <Pendiente
          paquete="P5"
          titulo="Línea de Tiempo y Red de Pases"
          casos={[
            "CU-46 Evolución por intervalos",
            "CU-47 Línea de tiempo",
            "CU-48 Red de pases",
          ]}
        />
      )}
    </div>
  );
}
