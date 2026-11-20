import { BotonComoSeUsa } from "@/features/asistente"; // Asistente de uso con IA

import { CalibracionDinamicaPage } from "./CalibracionDinamicaPage";

export function CalibracionPage() {
  return (
    <>
      {/* Asistente de uso con IA: ayuda sobre esta pantalla. */}
      <div className="asi-ayuda-pantalla">
        <BotonComoSeUsa pantalla="calibracion" />
      </div>
      <CalibracionDinamicaPage />
    </>
  );
}
