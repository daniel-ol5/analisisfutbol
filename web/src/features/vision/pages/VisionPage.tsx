import { Outlet, useSearchParams } from "react-router-dom";

import { Pestanas } from "@/shared/ui/Pestanas";

export function VisionPage() {
  const [parametros] = useSearchParams();
  const partidoId = parametros.get("partidoId");
  const contexto = partidoId ? `?partidoId=${encodeURIComponent(partidoId)}` : "";

  return (
    <main className="area-pagina">
      <header className="area-titulo">
        <h1>Visión y video</h1>
      </header>
      <Pestanas
        titulo="Visión y video"
        enlaces={[
          { ruta: `/vision/videos${contexto}`, titulo: "Videos" },
          { ruta: `/vision/calibracion${contexto}`, titulo: "Calibración" },
          { ruta: `/vision/guia-montaje${contexto}`, titulo: "Montaje" },
          { ruta: "/vision/modelos", titulo: "Modelos" },
        ]}
      />
      <div className="area-contenido vision-contenido">
        <Outlet />
      </div>
    </main>
  );
}
