/**
 * Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
 *
 * Cada feature exporta sus páginas desde su `index.ts`. Este archivo es el
 * único lugar que las conoce: las features no se importan entre sí.
 */
import { Route, Routes } from "react-router-dom";

import { Inicio } from "./Inicio";
import { AnalisisPage } from "@/features/analisis";
import { AsistenciaPage } from "@/features/asistencia";
import { DeportivoPage } from "@/features/deportivo";
import { PartidoPage } from "@/features/partido";
import { LoginPage, RegistroPage, SeguridadPage } from "@/features/seguridad";
import { GuiaMontajePage, VisionPage } from "@/features/vision";

export function Router() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registro" element={<RegistroPage />} />
      <Route path="/seguridad/*" element={<SeguridadPage />} />
      <Route path="/deportivo/*" element={<DeportivoPage />} />
      <Route path="/vision/guia-montaje" element={<GuiaMontajePage />} />
      <Route path="/vision/*" element={<VisionPage />} />
      <Route path="/partido/*" element={<PartidoPage />} />
      <Route path="/analisis/*" element={<AnalisisPage />} />
      <Route path="/asistencia/*" element={<AsistenciaPage />} />
    </Routes>
  );
}
