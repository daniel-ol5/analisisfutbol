/**
 * Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
 *
 * Cada feature exporta sus páginas desde su `index.ts`. Este archivo es el
 * único lugar que las conoce: las features no se importan entre sí.
 *
 * /login y /registro van fuera del Layout; el resto, dentro.
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
import { AsistenciaPage } from "@/features/asistencia";
import { DeportivoPage } from "@/features/deportivo";
import { PartidoPage } from "@/features/partido";
import { LoginPage, PerfilPage, RegistroPage, UsuariosPage } from "@/features/seguridad";
import { VisionPage } from "@/features/vision";

export function Router() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registro" element={<RegistroPage />} />
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
          {/* La sección no tiene página propia: lleva al perfil. */}
          <Route
            path="/seguridad"
            element={
              <RequiereRol ruta="/seguridad">
                <Navigate to="/seguridad/perfil" replace />
              </RequiereRol>
            }
          />
          {/* Perfil propio, para todos los autenticados. */}
          <Route
            path="/seguridad/perfil"
            element={
              <RequiereRol ruta="/seguridad/perfil">
                <PerfilPage />
              </RequiereRol>
            }
          />
          {/* Solo ADMIN. */}
          <Route
            path="/seguridad/usuarios"
            element={
              <RequiereRol ruta="/seguridad/usuarios">
                <UsuariosPage />
              </RequiereRol>
            }
          />
          <Route
            path="/deportivo/*"
            element={
              <RequiereRol ruta="/deportivo">
                <DeportivoPage />
              </RequiereRol>
            }
          />
          <Route
            path="/vision/*"
            element={
              <RequiereRol ruta="/vision">
                <VisionPage />
              </RequiereRol>
            }
          />
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
