/**
 * Tarjeta de una recomendación táctica  —  T-090 (CU-50) y T-091 (CU-51).
 *
 * Mensaje, prioridad, minuto y la justificación con las cifras REALES que la
 * dispararon (`datos_soporte`: valor medido contra umbral). Al mostrarse por
 * primera vez la marca como vista. Debajo, la valoración: Útil, No útil o
 * Aplicada, con comentario opcional; tras valorar, los botones se bloquean y
 * muestran lo elegido.
 */
import { useEffect, useRef, useState } from "react";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Input } from "@/shared/ui";
import type { TonoBadge } from "@/shared/ui/Badge";

import { marcarVista as marcarVistaApi, valorarRecomendacion } from "../api";
import { ETIQUETA_PRIORIDAD, cifraLegible } from "../recomendaciones";
import type { OpcionValoracion, Prioridad, Recomendacion } from "../types";
import "./recomendaciones.css";

const TONO: Record<Prioridad, TonoBadge> = {
  CRITICA: "error",
  ALTA: "aviso",
  MEDIA: "info",
  BAJA: "neutro",
};

const OPCIONES: { opcion: OpcionValoracion; texto: string }[] = [
  { opcion: "UTIL", texto: "Útil" },
  { opcion: "NO_UTIL", texto: "No útil" },
  { opcion: "APLICADA", texto: "Aplicada" },
];

/** Lo que ya está guardado en la recomendación (por ejemplo, valorada en otro dispositivo). */
function valoracionGuardada(r: Recomendacion): OpcionValoracion | null {
  if (r.estado === "APLICADA") return "APLICADA";
  if (r.util === false || r.estado === "DESCARTADA") return "NO_UTIL";
  if (r.util === true) return "UTIL";
  return null;
}

export interface PropsTarjeta {
  recomendacion: Recomendacion;
  /** Se llama con la recomendación que devolvió el servidor al valorarla. */
  alValorar?: (r: Recomendacion) => void;
  /** Sin permiso para valorar (ASISTENTE): solo se muestra. */
  soloLectura?: boolean;
}

export function TarjetaRecomendacion({ recomendacion: r, alValorar, soloLectura = false }: PropsTarjeta) {
  const [comentario, setComentario] = useState("");
  const [elegida, setElegida] = useState<OpcionValoracion | null>(valoracionGuardada(r));
  const [enviando, setEnviando] = useState<OpcionValoracion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const marcada = useRef(false);

  // T-090: la primera vez que se muestra, queda VISTA en el servidor.
  useEffect(() => {
    if (soloLectura || marcada.current || r.estado !== "PENDIENTE") return;
    marcada.current = true;
    marcarVistaApi(r.id).catch(() => {
      // No es crítico: se reintenta la próxima vez que se monte la tarjeta.
      marcada.current = false;
    });
  }, [r.id, r.estado, soloLectura]);

  const valorar = async (opcion: OpcionValoracion) => {
    setEnviando(opcion);
    setError(null);
    try {
      const actualizada = await valorarRecomendacion(r.id, opcion, comentario);
      setElegida(opcion);
      alValorar?.(actualizada);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setEnviando(null);
    }
  };

  const bloqueada = elegida !== null || enviando !== null;
  const textoElegida = OPCIONES.find((o) => o.opcion === elegida)?.texto;

  return (
    <article
      className={`rec-tarjeta rec-tarjeta--${r.prioridad.toLowerCase()}`}
      aria-label={`Recomendación de prioridad ${ETIQUETA_PRIORIDAD[r.prioridad]}`}
      data-testid="tarjeta-recomendacion"
    >
      <header className="rec-cabecera">
        <Badge tono={TONO[r.prioridad]}>Prioridad {ETIQUETA_PRIORIDAD[r.prioridad]}</Badge>
        <span className="rec-minuto">Min {r.minuto}&apos;</span>
      </header>

      <p className="rec-mensaje">{r.mensaje}</p>
      {r.justificacion && <p className="rec-justificacion">{r.justificacion}</p>}

      {r.datos_soporte.length > 0 && (
        <dl className="rec-cifras" aria-label="Cifras que la dispararon">
          {r.datos_soporte.map((dato) => {
            const c = cifraLegible(dato);
            return (
              <div className="rec-cifra" key={`${dato.metrica}-${dato.umbral}`}>
                <dt>{c.etiqueta}</dt>
                <dd>
                  <strong>{c.valor}</strong>
                  {c.umbral !== null && <span className="rec-umbral"> · umbral {c.umbral}</span>}
                </dd>
              </div>
            );
          })}
        </dl>
      )}

      {!soloLectura && (
      <div className="rec-valoracion">
        {elegida === null && (
          <Input
            etiqueta="Comentario (opcional)"
            value={comentario}
            maxLength={400}
            disabled={bloqueada}
            onChange={(e) => setComentario(e.target.value)}
          />
        )}
        <div className="rec-botones" role="group" aria-label="Valorar la recomendación">
          {OPCIONES.map(({ opcion, texto }) => (
            <Button
              key={opcion}
              variante={elegida === opcion ? "primario" : "secundario"}
              disabled={bloqueada}
              aria-pressed={elegida === opcion}
              onClick={() => void valorar(opcion)}
            >
              {enviando === opcion ? "Enviando…" : texto}
            </Button>
          ))}
        </div>
        {textoElegida && (
          <p className="rec-elegida" role="status">
            Valorada: {textoElegida}
          </p>
        )}
        {error && <Alert tono="error">{error}</Alert>}
      </div>
      )}
    </article>
  );
}
