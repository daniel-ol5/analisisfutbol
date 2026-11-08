/**
 * Validación del error de calibración con `/validar` (CU-21, T-031).
 *
 * - Automática, con retardo (`RETARDO_VALIDACION_MS`) tras el último cambio.
 * - Manual con `validarAhora` (también sirve de «Reintentar»).
 * - Cada resultado queda atado a SU cuerpo mediante la clave de la consulta, así
 *   una respuesta antigua nunca pisa a una más nueva; además se cancela la
 *   petición vieja con `signal`.
 * - Si el cuerpo actual no es el que se validó, el estado es «pendiente» y NO se
 *   expone ningún resultado (las cifras desactualizadas no se muestran).
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { validarCalibracion } from "./api";
import { RETARDO_VALIDACION_MS } from "./calibracion";
import type { CalibracionGuardar, ErrorCalibracion } from "./types";

interface Solicitud {
  clave: string;
  partidoId: number;
  cuerpo: CalibracionGuardar;
}

export type EstadoValidacion = "sin-datos" | "pendiente" | "calculando" | "listo" | "error";

export interface ValidacionCalibracion {
  estado: EstadoValidacion;
  /** Solo con `estado === "listo"`: es el resultado de EXACTAMENTE los puntos actuales. */
  resultado: ErrorCalibracion | null;
  /** Solo con `estado === "error"`. */
  error: unknown;
  /** Valida ya los puntos actuales (sin esperar el retardo) o repite el cálculo. */
  validarAhora: () => void;
}

/**
 * @param partidoId  ID del partido, o `null` si no es válido.
 * @param cuerpo     Cuerpo a validar, o `null` si todavía no cumple los requisitos de cliente.
 */
export function useValidacionCalibracion(
  partidoId: number | null,
  cuerpo: CalibracionGuardar | null,
): ValidacionCalibracion {
  const actual = useMemo<Solicitud | null>(
    () =>
      partidoId !== null && cuerpo !== null
        ? { clave: JSON.stringify({ partidoId, cuerpo }), partidoId, cuerpo }
        : null,
    [partidoId, cuerpo],
  );

  // Última solicitud «asentada»: la que ya pasó el retardo (o se pidió a mano).
  const [asentada, setAsentada] = useState<Solicitud | null>(null);

  useEffect(() => {
    if (actual === null) return;
    const temporizador = setTimeout(() => setAsentada(actual), RETARDO_VALIDACION_MS);
    return () => clearTimeout(temporizador);
  }, [actual]);

  const vigente = actual !== null && asentada !== null && asentada.clave === actual.clave;

  const consulta = useQuery({
    queryKey: ["calibracion-validar", asentada?.clave ?? null],
    queryFn: ({ signal }) => {
      if (asentada === null) throw new Error("No hay solicitud de validación.");
      return validarCalibracion(asentada.partidoId, asentada.cuerpo, signal);
    },
    enabled: asentada !== null,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  function validarAhora() {
    if (actual === null) return;
    if (vigente) {
      void consulta.refetch();
    } else {
      setAsentada(actual);
    }
  }

  let estado: EstadoValidacion;
  if (actual === null) estado = "sin-datos";
  else if (!vigente) estado = "pendiente";
  else if (consulta.isFetching) estado = "calculando";
  else if (consulta.isError) estado = "error";
  else if (consulta.isSuccess) estado = "listo";
  else estado = "calculando";

  return {
    estado,
    resultado: estado === "listo" ? (consulta.data ?? null) : null,
    error: estado === "error" ? consulta.error : null,
    validarAhora,
  };
}
