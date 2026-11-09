/**
 * Lógica pura de asignación de identificadores (tracks) a jugadores del plantel
 * (CU-34, CU-35, T-072). Sin dependencias de React.
 */
import type {
  EquipoDetectado,
  TrackDetectado,
  TrackEnVivoLigero,
  TrackUnificadoVista,
} from "../types";

/** Intervalo de refresco periódico de `GET /partido/{id}/tracks` (5 s). */
export const INTERVALO_REFRESCO_TRACKS_MS = 5_000;

/**
 * Une los tramos vigentes devueltos por `GET /partido/{id}/tracks?solo_activos=true`
 * con los `tid` vistos en vivo (en la Fase 2A `tracksEnVivo` se pasa vacío; en la
 * Fase 2B se alimentará con las muestras del canal `/vivo`).
 *
 * Un track visto en vivo que aún no tenga tramo vigente en la respuesta HTTP
 * aparece como «Sin asignar» (`jugador_id = null`, `tieneTramoVigente = false`)
 * y sigue siendo asignable mediante `PUT /partido/{id}/tracks/{track_id}`.
 */
export function unirTracksParaVista(
  tramosActivos: readonly TrackDetectado[],
  tracksEnVivo: readonly TrackEnVivoLigero[] = [],
): TrackUnificadoVista[] {
  const porTrackId = new Map<number, TrackUnificadoVista>();

  for (const tramo of tramosActivos) {
    porTrackId.set(tramo.track_id, {
      track_id: tramo.track_id,
      equipo_detectado: tramo.equipo_detectado,
      jugador_id: tramo.jugador_id,
      desde_t: tramo.desde_t,
      confianza: tramo.confianza,
      tieneTramoVigente: true,
    });
  }

  for (const vivo of tracksEnVivo) {
    if (porTrackId.has(vivo.tid)) continue;
    porTrackId.set(vivo.tid, {
      track_id: vivo.tid,
      equipo_detectado: vivo.equipo,
      jugador_id: null,
      desde_t: vivo.t,
      confianza: vivo.conf,
      tieneTramoVigente: false,
    });
  }

  return [...porTrackId.values()].sort((a, b) => a.track_id - b.track_id);
}

/**
 * Determina si el `equipo_detectado` figura como rival o árbitro según
 * `esLocal` del partido (`Trabajo.es_local` en `backend/app/vision/schemas.py:244`).
 *
 * - Nuestro equipo es `LOCAL` si `esLocal === true`, o `VISITANTE` si `esLocal === false`.
 * - `DESCONOCIDO` y nuestro equipo se consideran directamente asignables sin advertencia de rival/árbitro.
 * - El equipo contrario y `ARBITRO` exigen confirmación en línea («Este identificador figura como rival/árbitro. ¿Asignarlo de todos modos?»).
 */
export function esTrackRivalOArbitro(equipoDetectado: EquipoDetectado, esLocal: boolean): boolean {
  if (equipoDetectado === "ARBITRO") return true;
  if (equipoDetectado === "DESCONOCIDO") return false;
  const equipoPropio: EquipoDetectado = esLocal ? "LOCAL" : "VISITANTE";
  return equipoDetectado !== equipoPropio;
}

/**
 * Etiqueta clara en español para `equipo_detectado` indicando si corresponde
 * a nuestro equipo, al rival, al árbitro o desconocido.
 */
export function describirEquipoDetectado(
  equipoDetectado: EquipoDetectado,
  esLocal: boolean,
): string {
  switch (equipoDetectado) {
    case "LOCAL":
      return esLocal ? "LOCAL (Nuestro equipo)" : "LOCAL (Rival)";
    case "VISITANTE":
      return esLocal ? "VISITANTE (Rival)" : "VISITANTE (Nuestro equipo)";
    case "ARBITRO":
      return "ÁRBITRO";
    case "DESCONOCIDO":
      return "DESCONOCIDO";
  }
}

export function es404TrackNoEncontrado(status: number | null, mensaje: string): boolean {
  if (status !== 404) return false;
  const normalizado = mensaje.toLowerCase();
  return normalizado.includes("track");
}
