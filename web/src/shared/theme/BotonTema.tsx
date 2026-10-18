import { Button } from "@/shared/ui";

import { alternarTema, useTema } from "./tema";

/** Alterna entre tema oscuro y claro. */
export function BotonTema() {
  const tema = useTema();
  const destino = tema === "dark" ? "claro" : "oscuro";
  return (
    <Button variante="secundario" onClick={alternarTema} aria-label={`Cambiar a tema ${destino}`}>
      Tema {destino}
    </Button>
  );
}
