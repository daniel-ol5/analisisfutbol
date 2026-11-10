import { useEffect, useReducer, useRef } from "react";

import {
  crearEstadoSupervisionCalidad,
  evaluarSupervisionCalidad,
  type EstadoSupervisionCalidad,
  type MuestraSupervisionCalidad,
} from "../lib/calidad";

interface AccionEvaluar {
  tipo: "EVALUAR";
  muestra: MuestraSupervisionCalidad;
  ahoraMs: number;
}

interface AccionReiniciar {
  tipo: "REINICIAR";
}

type AccionSupervision = AccionEvaluar | AccionReiniciar;

function reducirSupervision(
  estado: EstadoSupervisionCalidad,
  accion: AccionSupervision,
): EstadoSupervisionCalidad {
  if (accion.tipo === "REINICIAR") return crearEstadoSupervisionCalidad();
  return evaluarSupervisionCalidad(estado, accion.muestra, accion.ahoraMs);
}

export function useSupervisionCalidad(
  partidoId: number | null,
  muestra: MuestraSupervisionCalidad,
): EstadoSupervisionCalidad {
  const [estado, dispatch] = useReducer(
    reducirSupervision,
    undefined,
    crearEstadoSupervisionCalidad,
  );
  const muestraRef = useRef(muestra);

  useEffect(() => {
    dispatch({ tipo: "REINICIAR" });
  }, [partidoId]);

  useEffect(() => {
    muestraRef.current = muestra;
    dispatch({ tipo: "EVALUAR", muestra, ahoraMs: Date.now() });
  }, [muestra]);

  useEffect(() => {
    const intervalo = window.setInterval(() => {
      dispatch({ tipo: "EVALUAR", muestra: muestraRef.current, ahoraMs: Date.now() });
    }, 1_000);
    return () => window.clearInterval(intervalo);
  }, []);

  return estado;
}
