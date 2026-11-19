/**
 * Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
 *
 * Cada feature exporta sus páginas desde su `index.ts`. Este archivo es el
 * único lugar que las conoce: las features no se importan entre sí.
 *
 * /login, /registro, /recuperar y /restablecer van fuera del Layout; el resto, dentro.
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { Componentes } from "./Componentes";
import { Inicio } from "./Inicio";
import { Layout } from "./Layout";
import { NoEncontrada } from "./NoEncontrada";
import { RequiereAutenticacion } from "./RequiereAutenticacion";
import { RequiereRol } from "./RequiereRol";
import { RetornoTrasLogin } from "./RetornoTrasLogin";
import { AnalisisPage } from "@/features/analisis";
import { AsistenciaPage, ReglasPage } from "@/features/asistencia";
import { DeportivoPage } from "@/features/deportivo";
import { PartidoPage } from "@/features/partido";
import {
  LoginPage,
  PerfilPage,
  RecuperarPage,
  RegistroPage,
  RestablecerPage,
  SeguridadPage,
  UsuariosPage,
} from "@/features/seguridad";
import {
  CalibracionPage,
  GuiaMontajePage,
  ModelosPage,
  VideosPage,
  VisionPage,
} from "@/features/vision";

export function Router() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registro" element={<RegistroPage />} />
      <Route path="/recuperar" element={<RecuperarPage />} />
      <Route path="/restablecer" element={<RestablecerPage />} />
      <Route element={<RequiereAutenticacion />}>
        <Route element={<Layout />}>
          <Route
            path="/"
            element={
              <RetornoTrasLogin>
                <Inicio />
              </RetornoTrasLogin>
            }
          />
          <Route
            path="/seguridad"
            element={
              <RequiereRol ruta="/seguridad">
                <SeguridadPage />
              </RequiereRol>
            }
          >
            <Route index element={<Navigate to="perfil" replace />} />
            <Route path="perfil" element={<PerfilPage />} />
            <Route
              path="usuarios"
              element={
                <RequiereRol ruta="/seguridad/usuarios">
                  <UsuariosPage />
                </RequiereRol>
              }
            />
          </Route>
          <Route
            path="/deportivo/*"
            element={
              <RequiereRol ruta="/deportivo">
                <DeportivoPage />
              </RequiereRol>
            }
          />
          <Route
            path="/vision"
            element={
              <RequiereRol ruta="/vision">
                <VisionPage />
              </RequiereRol>
            }
          >
            <Route index element={<Navigate to="videos" replace />} />
            <Route path="videos" element={<VideosPage />} />
            <Route path="calibracion" element={<CalibracionPage />} />
            <Route path="guia-montaje" element={<GuiaMontajePage />} />
            <Route path="modelos" element={<ModelosPage />} />
          </Route>
          <Route
            path="/partido/*"
            element={
              <RequiereRol ruta="/partido">
                <PartidoPage />
              </RequiereRol>
            }
          />
          <Route
            path="/analisis/*"
            element={
              <RequiereRol ruta="/analisis">
                <AnalisisPage />
              </RequiereRol>
            }
          />
          <Route
            path="/asistencia/reglas"
            element={
              <RequiereRol ruta="/asistencia">
                <ReglasPage />
              </RequiereRol>
            }
          />
          <Route
            path="/asistencia/*"
            element={
              <RequiereRol ruta="/asistencia">
                <AsistenciaPage />
              </RequiereRol>
            }
          />
          {import.meta.env.DEV && (
            <Route
              path="/componentes"
              element={
                <RequiereRol ruta="/componentes">
                  <Componentes />
                </RequiereRol>
              }
            />
          )}
          <Route path="*" element={<NoEncontrada />} />
        </Route>
      </Route>
    </Routes>
  );
}
