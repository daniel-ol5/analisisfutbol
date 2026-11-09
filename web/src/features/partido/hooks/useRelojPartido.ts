/**
 * Hook del cronómetro local sincronizado con `performance.now()` (CU-30, T-068).
 */
import { useEffect, useRef, useState } from "react";

import {
  INTERVALO_TICK_RELOJ_MS,
  calcularSegundosActuales,
  formatearCronometroPartido,
  reconciliarAnclaReloj,
  type AnclaReloj,
} from "../lib/reloj";
import type { EstadoEnVivo } from "../types";

export interface RelojPartidoVista {
  segundosTotales: number;
  textoCronometro: string;
  parte: number;
  enCurso: boolean;
}

interface MedicionReloj {
  partidoId: number;
  parte: number;
  enCurso: boolean;
  segundos: number;
}

export function useRelojPartido(estado: EstadoEnVivo | undefined): RelojPartidoVista {
  const anclaRef = useRef<AnclaReloj | null>(null);
  const [medicion, setMedicion] = useState<MedicionReloj | null>(null);

  useEffect(() => {
    if (!estado) {
      anclaRef.current = null;
      return;
    }

    const sincronizarConEstado = () => {
      const ahora = performance.now();
      const nuevaAncla = reconciliarAnclaReloj(anclaRef.current, estado, ahora);
      anclaRef.current = nuevaAncla;
      setMedicion({
        partidoId: nuevaAncla.partidoId,
        parte: nuevaAncla.parte,
        enCurso: nuevaAncla.enCurso,
        segundos: calcularSegundosActuales(nuevaAncla, ahora),
      });
    };

    const timeoutId = window.setTimeout(sincronizarConEstado, 0);
    if (!estado.en_curso) {
      return () => window.clearTimeout(timeoutId);
    }

    const intervalId = window.setInterval(() => {
      const ancla = anclaRef.current;
      if (!ancla) return;
      const ahora = performance.now();
      setMedicion({
        partidoId: ancla.partidoId,
        parte: ancla.parte,
        enCurso: ancla.enCurso,
        segundos: calcularSegundosActuales(ancla, ahora),
      });
    }, INTERVALO_TICK_RELOJ_MS);

    return () => {
      window.clearTimeout(timeoutId);
      window.clearInterval(intervalId);
    };
  }, [estado]);

  const parte = estado?.parte ?? 0;
  const enCurso = estado?.en_curso ?? false;
  const segundosRemotos = estado ? Math.max(0, estado.minuto * 60 + estado.segundo) : 0;

  const medicionVigente =
    estado !== undefined &&
    medicion !== null &&
    medicion.partidoId === estado.partido_id &&
    medicion.parte === estado.parte &&
    medicion.enCurso === estado.en_curso;

  const segundosTotales = !estado
    ? 0
    : medicionVigente && enCurso
      ? medicion.segundos
      : segundosRemotos;

  return {
    segundosTotales,
    textoCronometro: formatearCronometroPartido(segundosTotales, parte),
    parte,
    enCurso,
  };
}
