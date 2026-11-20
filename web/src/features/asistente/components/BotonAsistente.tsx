import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { obtenerSesion, useSesion } from "@/features/seguridad";

import { abrirAsistente, borrarHistoriales, cerrarAsistente, useEstadoAsistente } from "../estado";
import { PanelAsistente } from "./PanelAsistente";
import "../asistente.css";

/** Botón flotante «Asistente» y su panel. Va una sola vez, dentro del Layout. */
export function BotonAsistente() {
  const usuarioId = useSesion()?.usuario.id;
  const { pathname } = useLocation();
  const { abierto, preguntaInicial } = useEstadoAsistente();

  // Al cerrar sesión se borra el historial del chat.
  useEffect(
    () => () => {
      if (obtenerSesion() === null) {
        cerrarAsistente();
        borrarHistoriales();
      }
    },
    [],
  );

  return (
    <>
      {!abierto && (
        <button
          type="button"
          className="asi-flotante"
          onClick={() => abrirAsistente()}
          aria-label="Abrir el asistente de uso"
        >
          <span aria-hidden="true">?</span> Asistente
        </button>
      )}
      {abierto && (
        <PanelAsistente
          key={usuarioId ?? "anon"}
          usuarioId={usuarioId}
          pantallaActual={pathname}
          preguntaInicial={preguntaInicial}
          onCerrar={cerrarAsistente}
        />
      )}
    </>
  );
}
