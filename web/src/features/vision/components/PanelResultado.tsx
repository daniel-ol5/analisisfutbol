/**
 * Panel con el resultado de la validación del error (CU-21, T-031).
 *
 * Reserva SIEMPRE el mismo espacio: todas las filas están presentes en todos los
 * estados (las que no aplican quedan invisibles pero ocupan su alto), de modo que
 * al arrastrar un marcador el panel no salta de altura.
 */
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import { evaluarBloqueoInicio } from "../bloqueo";
import { UMBRAL_ERROR_MEDIO_M, formatearMetros, indicePeorValido } from "../calibracion";
import type { ValidacionCalibracion } from "../useValidacionCalibracion";
import { GuiaCorreccion } from "./GuiaCorreccion";

const ESPACIO = "\u00A0";

export interface PanelResultadoProps {
  validacion: ValidacionCalibracion;
  cantidadPares: number;
  /** Requisitos de cliente que faltan (si los hay) para poder validar. */
  requisitosPendientes: readonly string[];
}

export function PanelResultado({
  validacion,
  cantidadPares,
  requisitosPendientes,
}: PanelResultadoProps) {
  const { estado, resultado, error, validarAhora } = validacion;

  const listo = estado === "listo" && resultado !== null;
  const noValida = listo && !resultado.valida;
  const errorDeDatos = estado === "error" && estadoHttp(error) === 422;
  const bloqueo = evaluarBloqueoInicio(listo ? resultado : null);

  const indicePeor = listo ? indicePeorValido(resultado.punto_peor, cantidadPares) : null;
  const redondeaAlUmbral =
    noValida && formatearMetros(resultado.error_medio_m) === formatearMetros(UMBRAL_ERROR_MEDIO_M);

  let icono = "–";
  let titulo = "Sin validar";
  let tono = "neutro";
  let mensaje = ESPACIO;

  if (estado === "sin-datos") {
    mensaje =
      requisitosPendientes.length > 0
        ? `Para validar: ${requisitosPendientes.join(" · ")}`
        : "Completa los datos para poder validar.";
  } else if (estado === "pendiente") {
    icono = "↻";
    titulo = "Desactualizado";
    tono = "espera";
    mensaje =
      "Cambiaste los puntos o las medidas: el resultado anterior ya no vale y no se muestra. Se recalculará en un momento o pulsa «Validar ahora».";
  } else if (estado === "calculando") {
    icono = "…";
    titulo = "Calculando";
    tono = "espera";
    mensaje = "Calculando el error de reproyección…";
  } else if (estado === "error") {
    icono = "!";
    titulo = errorDeDatos ? "No se pudo calcular" : "No se pudo validar";
    tono = "aviso";
    mensaje = errorDeDatos
      ? mensajeDeError(error)
      : `${mensajeDeError(error)} Pulsa «Reintentar» cuando quieras.`;
  } else if (listo) {
    icono = resultado.valida ? "✔" : "✖";
    titulo = resultado.valida ? "VÁLIDA" : "NO VÁLIDA";
    tono = resultado.valida ? "valida" : "invalida";
    mensaje = resultado.valida
      ? "El error medio está dentro del máximo permitido."
      : `El error medio supera el máximo permitido${
          redondeaAlUmbral ? " por muy poco (el valor se redondea a 2 decimales)" : ""
        }.`;
  }

  const anuncio = listo
    ? `Calibración ${resultado.valida ? "válida" : "no válida"}. Error medio ${formatearMetros(
        resultado.error_medio_m,
      )} metros, error máximo ${formatearMetros(resultado.error_max_m)} metros.${
        indicePeor !== null ? ` Mayor error en el punto ${indicePeor + 1}.` : ""
      }`
    : estado === "error"
      ? mensaje
      : "";

  const tituloGuia = noValida || errorDeDatos ? "Cómo corregirlo" : "Consejos para un error bajo";

  return (
    <section className="cal-resultado" aria-labelledby="cal-titulo-resultado">
      <div className="cal-resultado-cabecera">
        <h2 id="cal-titulo-resultado">Validación del error de la calibración</h2>
        <div className="cal-botones-accion">
          <button
            type="button"
            className="cal-btn"
            onClick={validarAhora}
            disabled={estado === "sin-datos" || estado === "calculando"}
          >
            Validar ahora
          </button>
          {estado === "error" && (
            <button type="button" className="cal-btn" onClick={validarAhora}>
              Reintentar
            </button>
          )}
        </div>
      </div>

      <p className={`cal-resultado-estado es-${tono}`}>
        <span aria-hidden="true" className="cal-resultado-icono">
          {icono}
        </span>
        <strong>{titulo}</strong>
      </p>

      <dl className="cal-resultado-cifras">
        <div>
          <dt>Error medio</dt>
          <dd>{listo ? `${formatearMetros(resultado.error_medio_m)} m` : "—"}</dd>
        </div>
        <div>
          <dt>Error máximo</dt>
          <dd>{listo ? `${formatearMetros(resultado.error_max_m)} m` : "—"}</dd>
        </div>
        <div>
          <dt>Máximo permitido (error medio)</dt>
          <dd>{formatearMetros(UMBRAL_ERROR_MEDIO_M, 1)} m</dd>
        </div>
      </dl>

      <p className="cal-resultado-peor">
        {indicePeor !== null
          ? `Mayor error en el punto ${indicePeor + 1}: revisa ese punto y los cercanos.`
          : ESPACIO}
      </p>

      <p
        className={`cal-resultado-bloqueo ${listo && bloqueo.bloqueado ? "" : "es-oculto"}`}
        aria-hidden={!(listo && bloqueo.bloqueado)}
      >
        <span aria-hidden="true">⛔ </span>
        Esta calibración no permite iniciar el partido.
      </p>

      <p className="cal-resultado-mensaje">{mensaje}</p>

      <GuiaCorreccion titulo={tituloGuia} />

      {/* Un solo anuncio, solo con el resultado final (no los estados intermedios). */}
      <p className="cal-sr-solo" aria-live="polite" role="status">
        {anuncio}
      </p>
    </section>
  );
}
