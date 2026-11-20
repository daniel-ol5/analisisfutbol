import { Button } from "@/shared/ui";

import { PREGUNTAS_PANTALLA, type PantallaAyuda } from "../constantes";
import { abrirAsistente } from "../estado";
import "../asistente.css";

/** Abre el asistente con una pregunta sobre la pantalla actual. */
export function BotonComoSeUsa({ pantalla }: { pantalla: PantallaAyuda }) {
  return (
    <Button variante="secundario" onClick={() => abrirAsistente(PREGUNTAS_PANTALLA[pantalla])}>
      ¿Cómo se usa esto?
    </Button>
  );
}
