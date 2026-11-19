import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { Pestanas } from "@/shared/ui/Pestanas";

import { MapaCalorCancha } from "../components/MapaCalorCancha";
import { MetricasTacticasPanel } from "../components/MetricasTacticasPanel";
import { PanelPartidoVivo } from "../components/PanelPartidoVivo";
import { RedPasesCancha } from "../components/RedPasesCancha";
import { usePartidoUrl } from "../hooks/usePartidosAnalisis";
import "../analisis.css";

const PESTANAS = [
  { ruta: "/analisis", titulo: "Panel del partido", exacta: true },
  { ruta: "/analisis/mapa-de-calor", titulo: "Mapa de calor" },
  { ruta: "/analisis/metricas", titulo: "Métricas" },
  { ruta: "/analisis/red-de-pases", titulo: "Red de pases" },
];

export function AnalisisPage() {
  const { search } = useLocation();
  const { partidoId } = usePartidoUrl();

  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Análisis táctico</h1>
      </header>
      <Pestanas
        titulo="Análisis táctico"
        enlaces={PESTANAS.map((enlace) => ({
          ...enlace,
          ruta: enlace.ruta + search,
        }))}
      />
      <div className="area-contenido">
        <Routes>
          <Route index element={<PanelPartidoVivo key={partidoId} />} />
          <Route path="mapa-de-calor" element={<MapaCalorCancha key={partidoId} />} />
          <Route path="metricas" element={<MetricasTacticasPanel />} />
          <Route path="red-de-pases" element={<RedPasesCancha />} />
          <Route path="*" element={<Navigate to={`/analisis${search}`} replace />} />
        </Routes>
      </div>
    </main>
  );
}
