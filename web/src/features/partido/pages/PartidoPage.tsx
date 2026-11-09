/**
 * CU-30, CU-31 · Pantalla de control del partido y dirección de ataque (T-068, Fase 2A).
 *
 * Permite seleccionar un partido (`?partidoId=<id>`), consultar su estado en vivo
 * cada 5 s y al recuperar el foco de la pestaña, visualizar el cronómetro local
 * sincronizado con `performance.now()`, e iniciar, pausar/reanudar en entretiempo,
 * registrar tiempo de descuento (0..15 min) y finalizar con confirmación de dos pasos.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useState, type ChangeEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import "@/features/partido/partido.css";
import { obtenerRolActual } from "@/shared/api/client";
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import {
  entretiempoPartido,
  finalizarPartido,
  iniciarPartido,
  listarPartidosControl,
  obtenerEstadoPartido,
  obtenerPartidoControl,
  registrarDescuentoPartido,
} from "../api";
import { PanelAsignacionTracks } from "../components/PanelAsignacionTracks";
import { useCanalVivo } from "../hooks/useCanalVivo";
import { useRelojPartido } from "../hooks/useRelojPartido";
import { useSupervisionCalidad } from "../hooks/useSupervisionCalidad";
import type { MuestraSupervisionCalidad } from "../lib/calidad";
import {
  INTERVALO_SONDEO_CON_WS_MS,
  INTERVALO_SONDEO_SIN_WS_MS,
  MAX_DESCUENTO_MIN,
  MIN_DESCUENTO_MIN,
  determinarFaseControl,
  esErrorDeCalibracion409,
  ordenarPartidosParaSelector,
  rolPuedeOperarPartido,
} from "../lib/reloj";
import type {
  DireccionAtaque,
  EstadoCanalVivo,
  EstadoEnVivo,
  ResumenPartidoControl,
} from "../types";

interface ErrorOperacion {
  mensaje: string;
  status: number | null;
  esCalibracion409: boolean;
}

function describirDireccionAtaque(dir: DireccionAtaque): string {
  return dir === "DER"
    ? "→ Hacia la derecha, visto desde la cámara (tribuna)"
    : "← Hacia la izquierda, visto desde la cámara (tribuna)";
}

function claseInsigniaCanal(estadoCanal: EstadoCanalVivo): string {
  switch (estadoCanal) {
    case "CONECTADO":
      return "par-insignia-canal par-insignia-canal--conectado";
    case "RECONECTANDO":
      return "par-insignia-canal par-insignia-canal--reconectando";
    case "SESION_VENCIDA":
      return "par-insignia-canal par-insignia-canal--vencida";
    case "SIN_CONEXION":
      return "par-insignia-canal";
  }
}

export function PartidoPage() {
  const idSelectPartido = useId();
  const idInputDescuento = useId();
  const queryClient = useQueryClient();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const enVistaAsignar = location.pathname.replace(/\/+$/, "").endsWith("/asignar");

  // Rol actual leído a través del adaptador registrado en shared/api/client.ts
  const rolActual = obtenerRolActual();
  const puedeOperar = rolPuedeOperarPartido(rolActual);

  // Listado de partidos para el selector simple (priorizando EN_CURSO y PROGRAMADO)
  const partidosQuery = useQuery({
    queryKey: ["partido", "agenda-control"],
    queryFn: listarPartidosControl,
  });

  const partidosOrdenados = useMemo(
    () => ordenarPartidosParaSelector(partidosQuery.data ?? []),
    [partidosQuery.data],
  );

  // Determinación de partidoId activo desde ?partidoId=<id> o el primero priorizado
  const paramIdRaw = searchParams.get("partidoId");
  const paramIdNum = paramIdRaw ? Number(paramIdRaw) : Number.NaN;
  const partidoIdValidoEnUrl = Number.isInteger(paramIdNum) && paramIdNum > 0 ? paramIdNum : null;
  const partidoIdActivo = partidoIdValidoEnUrl ?? partidosOrdenados[0]?.id ?? null;

  // Sincroniza ?partidoId en la URL cuando se elige por defecto el primero de la lista
  useEffect(() => {
    if (partidoIdValidoEnUrl === null && partidosOrdenados.length > 0) {
      const primero = partidosOrdenados[0];
      if (primero) {
        setSearchParams({ partidoId: String(primero.id) }, { replace: true });
      }
    }
  }, [partidoIdValidoEnUrl, partidosOrdenados, setSearchParams]);

  // Estado local de controles
  const [direccionSeleccionada, setDireccionSeleccionada] = useState<DireccionAtaque | null>(null);
  const [descuentoTexto, setDescuentoTexto] = useState<string>("2");
  const [confirmandoFinalizar, setConfirmandoFinalizar] = useState<boolean>(false);
  const [errorOperacion, setErrorOperacion] = useState<ErrorOperacion | null>(null);

  // TODO: `EstadoEnVivo` no expone los minutos de descuento (`descuento_1_min` / `descuento_2_min`).
  // Guardamos solo en memoria de la sesión actual el último valor confirmado tras POST /descuento.
  const [descuentoSesion, setDescuentoSesion] = useState<{
    partidoId: number;
    parte: number;
    minutos: number;
  } | null>(null);

  // Canal WebSocket `/api/partido/{id}/vivo` (Fase 2B)
  const canalVivo = useCanalVivo(partidoIdActivo, queryClient);
  const muestraSupervision = useMemo<MuestraSupervisionCalidad>(
    () => ({
      canal: canalVivo.estado,
      calidad: canalVivo.calidad,
      recibidaEnMs: canalVivo.ultimaTelemetriaEnMs,
      tracksActivos: canalVivo.tracksActivos,
      latenciaWsMs: canalVivo.latenciaMs,
    }),
    [
      canalVivo.calidad,
      canalVivo.estado,
      canalVivo.latenciaMs,
      canalVivo.tracksActivos,
      canalVivo.ultimaTelemetriaEnMs,
    ],
  );
  useSupervisionCalidad(partidoIdActivo, muestraSupervision);

  // Sondeo HTTP de respaldo: 15 s con WS conectado y 2 s cuando está reconectando o caído
  const intervaloSondeoMs: number | false =
    canalVivo.estado === "SESION_VENCIDA"
      ? false
      : canalVivo.estado === "CONECTADO"
        ? INTERVALO_SONDEO_CON_WS_MS
        : INTERVALO_SONDEO_SIN_WS_MS;

  // Consulta del partido individual en deportivo para conocer estado (PROGRAMADO/EN_CURSO/FINALIZADO) y ataca_hacia
  const partidoDetalleQuery = useQuery({
    queryKey: ["partido", "detalle-control", partidoIdActivo],
    queryFn: () => obtenerPartidoControl(partidoIdActivo as number),
    enabled: partidoIdActivo !== null,
    refetchInterval: intervaloSondeoMs,
  });

  // Consulta de GET /partido/{id}/estado con frecuencia adaptada al estado del WebSocket
  const estadoQuery = useQuery({
    queryKey: ["partido", "estado-vivo", partidoIdActivo],
    queryFn: () => obtenerEstadoPartido(partidoIdActivo as number),
    enabled: partidoIdActivo !== null,
    refetchInterval: intervaloSondeoMs,
  });

  // Refetch inmediato al volver a la pestaña (visibilitychange)
  useEffect(() => {
    if (partidoIdActivo === null) return;
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") {
        void estadoQuery.refetch();
        void partidoDetalleQuery.refetch();
      }
    };
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    return () => {
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, [partidoIdActivo, estadoQuery, partidoDetalleQuery]);

  const partidoActual: ResumenPartidoControl | undefined =
    partidoDetalleQuery.data ?? partidosOrdenados.find((item) => item.id === partidoIdActivo);

  const estadoVivo = estadoQuery.data;
  const reloj = useRelojPartido(estadoVivo);
  const fase = determinarFaseControl(estadoVivo, partidoActual?.estado);

  function sincronizarEstadoTrasMutacion(nuevoEstado: EstadoEnVivo) {
    if (partidoIdActivo === null) return;
    queryClient.setQueryData(["partido", "estado-vivo", partidoIdActivo], nuevoEstado);
    void partidoDetalleQuery.refetch();
    void partidosQuery.refetch();
  }

  function manejarErrorMutacion(err: unknown) {
    const status = estadoHttp(err) ?? null;
    const mensaje = mensajeDeError(err);
    setErrorOperacion({
      mensaje,
      status,
      esCalibracion409: esErrorDeCalibracion409(status, mensaje),
    });
    // Tras cualquier 409 volvemos a pedir el estado real del servidor
    if (status === 409) {
      void estadoQuery.refetch();
      void partidoDetalleQuery.refetch();
      void partidosQuery.refetch();
    }
  }

  const iniciarMut = useMutation({
    mutationFn: (atacaHacia: DireccionAtaque) =>
      iniciarPartido(partidoIdActivo as number, { ataca_hacia: atacaHacia }),
    onSuccess: (datos) => {
      setErrorOperacion(null);
      setConfirmandoFinalizar(false);
      sincronizarEstadoTrasMutacion(datos);
    },
    onError: manejarErrorMutacion,
  });

  const entretiempoMut = useMutation({
    mutationFn: () => entretiempoPartido(partidoIdActivo as number),
    onSuccess: (datos) => {
      setErrorOperacion(null);
      setConfirmandoFinalizar(false);
      sincronizarEstadoTrasMutacion(datos);
    },
    onError: manejarErrorMutacion,
  });

  const descuentoMut = useMutation({
    mutationFn: (minutos: number) =>
      registrarDescuentoPartido(partidoIdActivo as number, { minutos }),
    onSuccess: (datos, minutos) => {
      setErrorOperacion(null);
      if (partidoIdActivo !== null) {
        setDescuentoSesion({
          partidoId: partidoIdActivo,
          parte: datos.parte,
          minutos,
        });
      }
      sincronizarEstadoTrasMutacion(datos);
    },
    onError: manejarErrorMutacion,
  });

  const finalizarMut = useMutation({
    mutationFn: () => finalizarPartido(partidoIdActivo as number),
    onSuccess: (datos) => {
      setErrorOperacion(null);
      setConfirmandoFinalizar(false);
      sincronizarEstadoTrasMutacion(datos);
    },
    onError: manejarErrorMutacion,
  });

  const accionEnVuelo =
    iniciarMut.isPending ||
    entretiempoMut.isPending ||
    descuentoMut.isPending ||
    finalizarMut.isPending;

  const controlesDeshabilitados = !puedeOperar || accionEnVuelo || partidoIdActivo === null;

  function alCambiarPartidoSelect(e: ChangeEvent<HTMLSelectElement>) {
    const valor = e.target.value;
    if (!valor) return;
    setConfirmandoFinalizar(false);
    setErrorOperacion(null);
    setSearchParams({ partidoId: valor });
  }

  function ejecutarGuardarDescuento() {
    const min = Number(descuentoTexto);
    if (!Number.isInteger(min) || min < MIN_DESCUENTO_MIN || min > MAX_DESCUENTO_MIN) {
      setErrorOperacion({
        mensaje: `El descuento debe ser un número entero entre ${MIN_DESCUENTO_MIN} y ${MAX_DESCUENTO_MIN} minutos.`,
        status: null,
        esCalibracion409: false,
      });
      return;
    }
    descuentoMut.mutate(min);
  }

  function reintentarCarga() {
    setErrorOperacion(null);
    void estadoQuery.refetch();
    void partidoDetalleQuery.refetch();
    void partidosQuery.refetch();
  }

  const descuentoVisibleEnParteActual =
    descuentoSesion !== null &&
    descuentoSesion.partidoId === partidoIdActivo &&
    descuentoSesion.parte === estadoVivo?.parte
      ? descuentoSesion.minutos
      : null;

  const etiquetaFase = (() => {
    switch (fase) {
      case "NO_INICIADO":
        return "NO INICIADO";
      case "PRIMER_TIEMPO":
        return "1.ER TIEMPO EN CURSO";
      case "ENTRETIEMPO":
        return "ENTRETIEMPO";
      case "SEGUNDO_TIEMPO":
        return "2.º TIEMPO EN CURSO";
      case "CERRADO":
        return partidoActual?.estado === "CANCELADO" ? "PARTIDO CANCELADO" : "PARTIDO FINALIZADO";
    }
  })();

  const claseInsigniaFase =
    fase === "PRIMER_TIEMPO" || fase === "SEGUNDO_TIEMPO"
      ? "par-insignia-fase par-insignia-fase--vivo"
      : fase === "ENTRETIEMPO"
        ? "par-insignia-fase par-insignia-fase--pausa"
        : "par-insignia-fase";

  const errorConsultaInicial = estadoQuery.isError
    ? {
        mensaje: mensajeDeError(estadoQuery.error),
        status: estadoHttp(estadoQuery.error) ?? null,
      }
    : null;

  return (
    <div className="par-pagina">
      <header className="par-cabecera">
        <div>
          <h1>
            {enVistaAsignar
              ? "Asignación de jugadores a identificadores"
              : "Control del partido en vivo"}
          </h1>
          <p className="par-subtitulo">
            {enVistaAsignar
              ? "Asociación de cada identificador detectado (track) a un jugador del plantel, con vigencia temporal y reasignación tras oclusiones (CU-34, CU-35)."
              : "Inicio del partido con dirección de ataque, entretiempo, tiempo de descuento y cierre del cronómetro (CU-30, CU-31)."}
          </p>
        </div>

        <div className="par-selector-caja">
          <label htmlFor={idSelectPartido}>Partido seleccionado</label>
          <select
            id={idSelectPartido}
            className="par-select"
            value={partidoIdActivo ?? ""}
            onChange={alCambiarPartidoSelect}
            disabled={accionEnVuelo}
          >
            {partidosOrdenados.length === 0 && partidoIdActivo === null && (
              <option value="">Sin partidos registrados</option>
            )}
            {partidoIdActivo !== null &&
              !partidosOrdenados.some((p) => p.id === partidoIdActivo) && (
                <option value={partidoIdActivo}>Partido #{partidoIdActivo}</option>
              )}
            {partidosOrdenados.map((p) => (
              <option key={p.id} value={p.id}>
                #{p.id} · vs. {p.rival} ({p.estado})
              </option>
            ))}
          </select>
        </div>
      </header>

      <nav className="par-tabs" aria-label="Secciones del partido">
        <Link
          to={`/partido${partidoIdActivo !== null ? `?partidoId=${partidoIdActivo}` : ""}`}
          className={`par-tab ${!enVistaAsignar ? "par-tab--activa" : ""}`}
          aria-current={!enVistaAsignar ? "page" : undefined}
        >
          Control y cronómetro
        </Link>
        <Link
          to={`/partido/asignar${partidoIdActivo !== null ? `?partidoId=${partidoIdActivo}` : ""}`}
          className={`par-tab ${enVistaAsignar ? "par-tab--activa" : ""}`}
          aria-current={enVistaAsignar ? "page" : undefined}
        >
          Asignar identificadores
        </Link>
      </nav>

      {!puedeOperar && (
        <div className="par-aviso-rol" role="note">
          Modo lectura ({rolActual ?? "sin rol"}): solo los roles <strong>ADMIN</strong> y{" "}
          <strong>ANALISTA</strong> pueden iniciar, pausar, agregar descuento, finalizar el partido
          o asignar jugadores a identificadores. Los controles están deshabilitados para evitar
          errores de permisos (403).
        </div>
      )}

      {canalVivo.aviso && (
        <div className="par-alerta-error" role="alert">
          <p className="par-alerta-error-titulo">Aviso del canal en vivo</p>
          <p className="par-alerta-error-mensaje">{canalVivo.aviso}</p>
          {canalVivo.estado === "SESION_VENCIDA" && (
            <div className="par-alerta-acciones">
              <Link to="/login" className="par-btn par-btn--primario">
                Iniciar sesión
              </Link>
            </div>
          )}
        </div>
      )}

      {errorConsultaInicial && (
        <div className="par-alerta-error" role="alert">
          <p className="par-alerta-error-titulo">
            Error al cargar el estado del partido
            {errorConsultaInicial.status ? ` (HTTP ${errorConsultaInicial.status})` : ""}
          </p>
          <p className="par-alerta-error-mensaje">{errorConsultaInicial.mensaje}</p>
          <div className="par-alerta-acciones">
            <button type="button" className="par-btn" onClick={reintentarCarga}>
              Reintentar
            </button>
          </div>
        </div>
      )}

      {errorOperacion && (
        <div className="par-alerta-error" role="alert">
          <p className="par-alerta-error-titulo">
            No se pudo ejecutar la acción
            {errorOperacion.status ? ` (HTTP ${errorOperacion.status})` : ""}
          </p>
          <p className="par-alerta-error-mensaje">{errorOperacion.mensaje}</p>
          <div className="par-alerta-acciones">
            {errorOperacion.esCalibracion409 && partidoIdActivo !== null && (
              <Link
                to={`/vision/calibracion?partidoId=${partidoIdActivo}`}
                className="par-btn par-btn--primario"
              >
                Ir a calibrar cámara
              </Link>
            )}
            <button type="button" className="par-btn" onClick={reintentarCarga}>
              Reintentar
            </button>
          </div>
        </div>
      )}

      {partidoIdActivo === null ? (
        <section className="par-tarjeta">
          <p>
            No hay ningún partido seleccionado. Registra un partido en la agenda o indica{" "}
            <code>?partidoId=&lt;id&gt;</code> en la dirección.
          </p>
        </section>
      ) : enVistaAsignar ? (
        <PanelAsignacionTracks
          partidoId={partidoIdActivo}
          equipoId={partidoActual?.equipo_id ?? null}
          partido={partidoActual}
          puedeOperar={puedeOperar}
        />
      ) : (
        <>
          <div className="par-tablero">
            {/* Tarjeta de Cronómetro */}
            <section className="par-tarjeta" aria-label="Cronómetro del partido">
              <div className="par-cronometro-cabecera">
                <span className={claseInsigniaFase}>{etiquetaFase}</span>
                <span className={claseInsigniaCanal(canalVivo.estado)} role="status">
                  Canal: {canalVivo.etiqueta}
                </span>
              </div>

              <p className="par-meta-reloj">
                Parte: {reloj.parte === 0 ? "—" : `${reloj.parte}.º tiempo`} ·{" "}
                {reloj.enCurso ? "Reloj corriendo" : "Reloj congelado"}
              </p>

              <div className="par-cronometro-digitos" aria-live="off">
                {reloj.textoCronometro}
              </div>

              {fase === "ENTRETIEMPO" && (
                <p className="par-meta-reloj">
                  <strong>ENTRETIEMPO:</strong> cronómetro pausado al cierre del 1.er tiempo.
                </p>
              )}

              {descuentoVisibleEnParteActual !== null && (
                <p className="par-descuento-sesion">
                  Descuento registrado en esta sesión: +{descuentoVisibleEnParteActual} min
                </p>
              )}

              {partidoActual?.ataca_hacia && (
                <p className="par-meta-reloj">
                  Dirección 1.er tiempo:{" "}
                  <strong>{describirDireccionAtaque(partidoActual.ataca_hacia)}</strong> (en el 2.º
                  tiempo el sistema invierte las coordenadas solo).
                </p>
              )}
            </section>

            {/* Tarjeta de Marcador y Posesión */}
            <section className="par-tarjeta" aria-label="Marcador del partido">
              <h2 className="par-seccion-titulo">
                {partidoActual
                  ? `Nuestro equipo vs. ${partidoActual.rival} (${partidoActual.es_local ? "Local" : "Visitante"})`
                  : `Partido #${partidoIdActivo}`}
              </h2>

              <div className="par-marcador-grid">
                <div>
                  <div className="par-equipo-etiqueta">A favor</div>
                  <div className="par-goles-numero">{estadoVivo?.goles_favor ?? 0}</div>
                </div>
                <div className="par-marcador-sep">—</div>
                <div>
                  <div className="par-equipo-etiqueta">
                    En contra {partidoActual ? `(${partidoActual.rival})` : ""}
                  </div>
                  <div className="par-goles-numero">{estadoVivo?.goles_contra ?? 0}</div>
                </div>
              </div>

              <div className="par-posesion-fila">
                <span>Posesión local</span>
                <strong>
                  {estadoVivo?.posesion_local_pct !== null &&
                  estadoVivo?.posesion_local_pct !== undefined
                    ? `${estadoVivo.posesion_local_pct.toFixed(1).replace(".", ",")} %`
                    : "Sin datos aún"}
                </strong>
              </div>
            </section>
          </div>

          {/* Botonera contextual según fase */}
          <section className="par-tarjeta" aria-label="Controles de operación del partido">
            <h2 className="par-seccion-titulo">Control de fase y cronómetro</h2>

            {fase === "NO_INICIADO" && (
              <div>
                <p className="par-subtitulo">
                  Selecciona obligatoriamente hacia qué lado ataca nuestro equipo en el 1.er tiempo:
                </p>
                <div
                  className="par-ataque-opciones"
                  role="radiogroup"
                  aria-label="Dirección de ataque"
                >
                  <label
                    className={`par-ataque-opcion ${
                      direccionSeleccionada === "DER" ? "par-ataque-opcion--activa" : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name="ataca_hacia"
                      value="DER"
                      checked={direccionSeleccionada === "DER"}
                      onChange={() => setDireccionSeleccionada("DER")}
                      disabled={controlesDeshabilitados}
                    />
                    <span>
                      <strong>→ DER:</strong> hacia la derecha, visto desde la cámara (tribuna)
                    </span>
                  </label>

                  <label
                    className={`par-ataque-opcion ${
                      direccionSeleccionada === "IZQ" ? "par-ataque-opcion--activa" : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name="ataca_hacia"
                      value="IZQ"
                      checked={direccionSeleccionada === "IZQ"}
                      onChange={() => setDireccionSeleccionada("IZQ")}
                      disabled={controlesDeshabilitados}
                    />
                    <span>
                      <strong>← IZQ:</strong> hacia la izquierda, visto desde la cámara (tribuna)
                    </span>
                  </label>
                </div>

                <p className="par-ataque-nota">
                  Nota: en el 2.º tiempo el sistema invierte las coordenadas solo para mantener una
                  referencia táctica uniforme.
                </p>

                <div className="par-acciones-fila">
                  <button
                    type="button"
                    className="par-btn par-btn--primario"
                    disabled={controlesDeshabilitados || direccionSeleccionada === null}
                    onClick={() => {
                      if (direccionSeleccionada) {
                        iniciarMut.mutate(direccionSeleccionada);
                      }
                    }}
                  >
                    {iniciarMut.isPending ? "Iniciando partido…" : "Iniciar partido"}
                  </button>
                </div>
              </div>
            )}

            {fase === "PRIMER_TIEMPO" && (
              <div>
                <div className="par-acciones-fila">
                  <button
                    type="button"
                    className="par-btn par-btn--primario"
                    disabled={controlesDeshabilitados}
                    onClick={() => entretiempoMut.mutate()}
                  >
                    {entretiempoMut.isPending
                      ? "Pausando para entretiempo…"
                      : "Pausar para entretiempo"}
                  </button>

                  {!confirmandoFinalizar && (
                    <button
                      type="button"
                      className="par-btn"
                      disabled={controlesDeshabilitados}
                      onClick={() => setConfirmandoFinalizar(true)}
                    >
                      Finalizar partido
                    </button>
                  )}
                </div>

                <div className="par-descuento-bloque">
                  <div>
                    <label htmlFor={idInputDescuento}>Tiempo de descuento (0 a 15 min)</label>
                    <div>
                      <input
                        id={idInputDescuento}
                        type="number"
                        min={MIN_DESCUENTO_MIN}
                        max={MAX_DESCUENTO_MIN}
                        step={1}
                        className="par-input-num"
                        value={descuentoTexto}
                        onChange={(e) => setDescuentoTexto(e.target.value)}
                        disabled={controlesDeshabilitados}
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="par-btn"
                    disabled={controlesDeshabilitados}
                    onClick={ejecutarGuardarDescuento}
                  >
                    {descuentoMut.isPending ? "Guardando descuento…" : "Registrar descuento"}
                  </button>
                </div>
              </div>
            )}

            {fase === "ENTRETIEMPO" && (
              <div>
                <p className="par-ataque-nota">
                  El 1.er tiempo está en pausa de <strong>ENTRETIEMPO</strong>. Al iniciar el 2.º
                  tiempo el cronómetro arrancará en <code>45:00</code> y en el 2.º tiempo el sistema
                  invierte las coordenadas solo.
                </p>
                <div className="par-acciones-fila">
                  <button
                    type="button"
                    className="par-btn par-btn--primario"
                    disabled={controlesDeshabilitados}
                    onClick={() => entretiempoMut.mutate()}
                  >
                    {entretiempoMut.isPending ? "Iniciando 2.º tiempo…" : "Iniciar 2.º tiempo"}
                  </button>

                  {!confirmandoFinalizar && (
                    <button
                      type="button"
                      className="par-btn"
                      disabled={controlesDeshabilitados}
                      onClick={() => setConfirmandoFinalizar(true)}
                    >
                      Finalizar partido
                    </button>
                  )}
                </div>
              </div>
            )}

            {fase === "SEGUNDO_TIEMPO" && (
              <div>
                <p className="par-ataque-nota">
                  2.º tiempo en curso (en el 2.º tiempo el sistema invierte las coordenadas solo).
                </p>

                <div className="par-descuento-bloque">
                  <div>
                    <label htmlFor={idInputDescuento}>Tiempo de descuento (0 a 15 min)</label>
                    <div>
                      <input
                        id={idInputDescuento}
                        type="number"
                        min={MIN_DESCUENTO_MIN}
                        max={MAX_DESCUENTO_MIN}
                        step={1}
                        className="par-input-num"
                        value={descuentoTexto}
                        onChange={(e) => setDescuentoTexto(e.target.value)}
                        disabled={controlesDeshabilitados}
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="par-btn"
                    disabled={controlesDeshabilitados}
                    onClick={ejecutarGuardarDescuento}
                  >
                    {descuentoMut.isPending ? "Guardando descuento…" : "Registrar descuento"}
                  </button>
                </div>

                {!confirmandoFinalizar && (
                  <div className="par-acciones-fila">
                    <button
                      type="button"
                      className="par-btn par-btn--peligro"
                      disabled={controlesDeshabilitados}
                      onClick={() => setConfirmandoFinalizar(true)}
                    >
                      Finalizar partido
                    </button>
                  </div>
                )}
              </div>
            )}

            {confirmandoFinalizar && fase !== "NO_INICIADO" && fase !== "CERRADO" && (
              <div className="par-confirmacion-cierre" role="region" aria-label="Confirmar cierre">
                <p>
                  ¿Confirmas finalizar definitivamente el partido? El cronómetro se detendrá y no
                  podrá volver a iniciarse.
                </p>
                <div className="par-acciones-fila">
                  <button
                    type="button"
                    className="par-btn par-btn--peligro"
                    disabled={controlesDeshabilitados}
                    onClick={() => finalizarMut.mutate()}
                  >
                    {finalizarMut.isPending ? "Finalizando partido…" : "Sí, finalizar partido"}
                  </button>
                  <button
                    type="button"
                    className="par-btn"
                    disabled={accionEnVuelo}
                    onClick={() => setConfirmandoFinalizar(false)}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {fase === "CERRADO" && (
              <p className="par-subtitulo">
                El partido se encuentra <strong>{etiquetaFase.toLowerCase()}</strong>. El cronómetro
                quedó detenido en <code>{reloj.textoCronometro}</code> y no admite más transiciones
                de control.
              </p>
            )}
          </section>

          {/* Panel de calidad mínimo */}
          <section className="par-tarjeta par-calidad" aria-label="Calidad de procesamiento">
            <h2 className="par-seccion-titulo">Calidad de procesamiento en vivo</h2>
            <ul className="par-calidad-lista">
              <li className="par-calidad-item">
                <span>Worker de visión</span>
                <strong>
                  {estadoVivo?.calidad.worker_conectado ? "Conectado" : "Desconectado"}
                </strong>
              </li>
              <li className="par-calidad-item">
                <span>Cuadros por segundo</span>
                <strong>
                  {estadoVivo ? `${estadoVivo.calidad.fps.toFixed(1).replace(".", ",")} FPS` : "—"}
                </strong>
              </li>
              <li className="par-calidad-item">
                <span>Jugadores detectados</span>
                <strong>{estadoVivo?.calidad.jugadores_detectados ?? 0}</strong>
              </li>
              <li className="par-calidad-item">
                <span>Balón visible</span>
                <strong>{estadoVivo?.calidad.balon_visible ? "Sí" : "No"}</strong>
              </li>
              <li className="par-calidad-item">
                <span>Retraso</span>
                <strong>
                  {estadoVivo
                    ? `${estadoVivo.calidad.retraso_s.toFixed(1).replace(".", ",")} s`
                    : "—"}
                </strong>
              </li>
            </ul>

            {estadoVivo?.calidad.degradado && (
              <p className="par-calidad-degradado" role="status">
                <strong>Procesamiento degradado:</strong>{" "}
                {estadoVivo.calidad.motivo ?? "Calidad reducida reportada por el worker."}
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
