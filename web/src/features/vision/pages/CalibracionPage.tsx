/**
 * CU-19, CU-20 · Pantalla de marcado de puntos y medidas de cancha (T-030).
 *
 * Muestra el cuadro congelado de la cámara y el plano cenital de la cancha lado
 * a lado. Permite marcar pares de puntos mediante una plantilla de 14 hitos con
 * avance automático (o punto libre secundario), corregirlos arrastrando o con
 * teclado, eliminarlos y enviarlos al backend.
 *
 * Nota: Mostrar el error medio/máximo y el punto peor corresponde a T-031.
 */
import { useMutation } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";

import "@/features/vision/calibracion.css";
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import { guardarCalibracion } from "../api";
import {
  ANCHO_CANCHA_DEFECTO_M,
  AVISO_PROPUESTA_CALIBRACION,
  LARGO_CANCHA_DEFECTO_M,
  MIN_PUNTOS_CALIBRACION,
  acotar,
  construirPlantillaCancha,
  obtenerRolSesionActual,
  paresLibresFueraDeCancha,
  recalcularParesConMedidas,
  redondear2,
  rolPuedeGuardarCalibracion,
  validarEstadoCalibracion,
} from "../calibracion";
import { PlanoCancha } from "../components/PlanoCancha";
import { VisorCuadro } from "../components/VisorCuadro";
import type { Calibracion, HitoCancha, ParCalibracion, Punto } from "../types";

const MAX_HISTORIAL = 40;

function focoEnCampoEditable(target: EventTarget | null): boolean {
  const el = target instanceof HTMLElement ? target : document.activeElement;
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export function CalibracionPage() {
  const idArchivo = useId();
  const idPartido = useId();
  const idLargo = useId();
  const idAncho = useId();

  // Archivo de imagen local (nunca se sube al servidor)
  const [imagenUrl, setImagenUrl] = useState<string | null>(null);
  const [nombreArchivo, setNombreArchivo] = useState<string | null>(null);
  const [dimensiones, setDimensiones] = useState<{ ancho: number; alto: number } | null>(null);

  // Parámetros del partido y dimensiones reales editables (CU-20)
  const [partidoIdTexto, setPartidoIdTexto] = useState("1");
  const [largoTexto, setLargoTexto] = useState(String(LARGO_CANCHA_DEFECTO_M));
  const [anchoTexto, setAnchoTexto] = useState(String(ANCHO_CANCHA_DEFECTO_M));

  const largoM = Number(largoTexto);
  const anchoM = Number(anchoTexto);

  // Estado de pares marcados e historial para Deshacer (Ctrl+Z)
  const [pares, setPares] = useState<ParCalibracion[]>([]);
  const [historial, setHistorial] = useState<ParCalibracion[][]>([]);
  const [parSeleccionadoId, setParSeleccionadoId] = useState<string | null>(null);
  const contadorIdRef = useRef(1);

  // Plantilla de 14 hitos con avance automático y modo libre secundario
  const plantilla = useMemo(() => construirPlantillaCancha(largoM, anchoM), [largoM, anchoM]);
  const [hitoElegidoManualId, setHitoElegidoManualId] = useState<string | null>(null);
  const [hitosSaltadosIds, setHitosSaltadosIds] = useState<string[]>([]);
  const [modoLibre, setModoLibre] = useState(false);
  const [puntoLibrePendiente, setPuntoLibrePendiente] = useState<Punto | null>(null);

  // Resultado del último guardado (punto de extensión para T-031)
  const [ultimaCalibracion, setUltimaCalibracion] = useState<Calibracion | null>(null);

  // Permiso por rol (solo ADMIN y ANALISTA pueden hacer POST)
  const rolActual = obtenerRolSesionActual();
  const puedeGuardarPorRol = rolPuedeGuardarCalibracion(rolActual);

  // Limpieza de ObjectURL al desmontar o cambiar de imagen
  useEffect(() => {
    return () => {
      if (imagenUrl) {
        URL.revokeObjectURL(imagenUrl);
      }
    };
  }, [imagenUrl]);

  // Hitos que todavía no tienen un par asignado
  const hitosDisponibles = useMemo(() => {
    const usados = new Set(pares.map((p) => p.hitoId).filter((id): id is string => id !== null));
    return plantilla.filter((h) => !usados.has(h.id));
  }, [plantilla, pares]);

  // Determina el hito activo de la plantilla
  const hitoActivo: HitoCancha | null = useMemo(() => {
    if (hitosDisponibles.length === 0) return null;
    if (hitoElegidoManualId) {
      const manual = hitosDisponibles.find((h) => h.id === hitoElegidoManualId);
      if (manual) return manual;
    }
    const noSaltado = hitosDisponibles.find((h) => !hitosSaltadosIds.includes(h.id));
    return noSaltado ?? hitosDisponibles[0] ?? null;
  }, [hitosDisponibles, hitoElegidoManualId, hitosSaltadosIds]);

  // Validaciones en cliente y advertencias de puntos libres fuera de cancha
  const validacion = useMemo(
    () => validarEstadoCalibracion(partidoIdTexto, largoM, anchoM, pares),
    [partidoIdTexto, largoM, anchoM, pares],
  );

  const libresFuera = useMemo(
    () => paresLibresFueraDeCancha(pares, largoM, anchoM),
    [pares, largoM, anchoM],
  );

  const mutacionGuardar = useMutation({
    mutationFn: async () => {
      if (!validacion.valido || validacion.partidoId === null) {
        throw new Error("Revisa los datos antes de guardar.");
      }
      return guardarCalibracion(validacion.partidoId, {
        largo_m: redondear2(largoM),
        ancho_m: redondear2(anchoM),
        puntos_imagen: pares.map((p) => p.imagen),
        puntos_cancha: pares.map((p) => p.cancha),
      });
    },
    onSuccess: (calibracion) => {
      setUltimaCalibracion(calibracion);
    },
  });

  function guardarInstantanea(actual: ParCalibracion[]) {
    setHistorial((prev) => [...prev.slice(-(MAX_HISTORIAL - 1)), actual]);
  }

  function limpiarEstadoEnvio() {
    setUltimaCalibracion(null);
    mutacionGuardar.reset();
  }

  function alCambiarArchivo(e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    if (imagenUrl) {
      URL.revokeObjectURL(imagenUrl);
    }
    const nuevaUrl = URL.createObjectURL(archivo);
    setImagenUrl(nuevaUrl);
    setNombreArchivo(archivo.name);
    setDimensiones(null);
    limpiarEstadoEnvio();
  }

  function alCambiarLargo(nuevoTexto: string) {
    setLargoTexto(nuevoTexto);
    const num = Number(nuevoTexto);
    if (Number.isFinite(num) && num > 0) {
      setPares((prev) => recalcularParesConMedidas(prev, num, anchoM));
    }
    limpiarEstadoEnvio();
  }

  function alCambiarAncho(nuevoTexto: string) {
    setAnchoTexto(nuevoTexto);
    const num = Number(nuevoTexto);
    if (Number.isFinite(num) && num > 0) {
      setPares((prev) => recalcularParesConMedidas(prev, largoM, num));
    }
    limpiarEstadoEnvio();
  }

  function alClicNuevoPuntoImagen(puntoPx: Punto) {
    limpiarEstadoEnvio();

    if (modoLibre) {
      const destino = puntoLibrePendiente ?? {
        x: redondear2((Number.isFinite(largoM) ? largoM : LARGO_CANCHA_DEFECTO_M) / 2),
        y: redondear2((Number.isFinite(anchoM) ? anchoM : ANCHO_CANCHA_DEFECTO_M) / 2),
      };
      const nuevoPar: ParCalibracion = {
        id: `par-${contadorIdRef.current++}`,
        hitoId: null,
        etiqueta: `Punto libre (${destino.x} m, ${destino.y} m)`,
        imagen: puntoPx,
        cancha: destino,
      };
      guardarInstantanea(pares);
      setPares((prev) => [...prev, nuevoPar]);
      setParSeleccionadoId(nuevoPar.id);
      setPuntoLibrePendiente(null);
      return;
    }

    if (hitoActivo) {
      const nuevoPar: ParCalibracion = {
        id: `par-${contadorIdRef.current++}`,
        hitoId: hitoActivo.id,
        etiqueta: hitoActivo.nombre,
        imagen: puntoPx,
        cancha: { x: hitoActivo.x, y: hitoActivo.y },
      };
      guardarInstantanea(pares);
      setPares((prev) => [...prev, nuevoPar]);
      setParSeleccionadoId(nuevoPar.id);
      setHitoElegidoManualId(null);
      return;
    }

    // Si ya se completaron los 14 hitos de la plantilla y hace otro clic, si hay un par seleccionado actualiza su posición
    if (parSeleccionadoId) {
      guardarInstantanea(pares);
      setPares((prev) =>
        prev.map((p) => (p.id === parSeleccionadoId ? { ...p, imagen: puntoPx } : p)),
      );
    }
  }

  function saltarHitoActual() {
    if (!hitoActivo || hitosDisponibles.length <= 1) return;
    setHitoElegidoManualId(null);
    setHitosSaltadosIds((prev) => {
      const siguientes = [...prev.filter((id) => id !== hitoActivo.id), hitoActivo.id];
      // Si ya se saltaron todos los disponibles, reinicia el ciclo dejando al actual al final
      const quedanSinSaltar = hitosDisponibles.some((h) => !siguientes.includes(h.id));
      return quedanSinSaltar ? siguientes : [hitoActivo.id];
    });
  }

  function eliminarPar(parId: string) {
    limpiarEstadoEnvio();
    guardarInstantanea(pares);
    setPares((prev) => prev.filter((p) => p.id !== parId));
    if (parSeleccionadoId === parId) {
      setParSeleccionadoId(null);
    }
  }

  function deshacer() {
    if (historial.length === 0) return;
    limpiarEstadoEnvio();
    const anterior = historial[historial.length - 1];
    if (!anterior) return;
    setHistorial((prev) => prev.slice(0, -1));
    setPares(anterior);
    if (parSeleccionadoId && !anterior.some((p) => p.id === parSeleccionadoId)) {
      setParSeleccionadoId(null);
    }
  }

  function borrarTodos() {
    if (pares.length === 0) return;
    limpiarEstadoEnvio();
    guardarInstantanea(pares);
    setPares([]);
    setParSeleccionadoId(null);
    setHitoElegidoManualId(null);
    setHitosSaltadosIds([]);
  }

  // Atajos de teclado globales (solo cuando el foco NO está en input, textarea o select)
  useEffect(() => {
    function alPresionarTecla(e: KeyboardEvent) {
      if (focoEnCampoEditable(e.target)) return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        deshacer();
        return;
      }

      if (e.key === "Escape") {
        setParSeleccionadoId(null);
        return;
      }

      if ((e.key === "Delete" || e.key === "Backspace") && parSeleccionadoId !== null) {
        e.preventDefault();
        eliminarPar(parSeleccionadoId);
        return;
      }

      if (
        parSeleccionadoId !== null &&
        dimensiones !== null &&
        (e.key === "ArrowUp" ||
          e.key === "ArrowDown" ||
          e.key === "ArrowLeft" ||
          e.key === "ArrowRight")
      ) {
        e.preventDefault();
        const paso = e.shiftKey ? 5 : 1;
        const dx = e.key === "ArrowRight" ? paso : e.key === "ArrowLeft" ? -paso : 0;
        const dy = e.key === "ArrowDown" ? paso : e.key === "ArrowUp" ? -paso : 0;

        limpiarEstadoEnvio();
        guardarInstantanea(pares);
        setPares((prev) =>
          prev.map((par) =>
            par.id === parSeleccionadoId
              ? {
                  ...par,
                  imagen: {
                    x: redondear2(acotar(par.imagen.x + dx, 0, dimensiones.ancho)),
                    y: redondear2(acotar(par.imagen.y + dy, 0, dimensiones.alto)),
                  },
                }
              : par,
          ),
        );
      }
    }

    window.addEventListener("keydown", alPresionarTecla);
    return () => window.removeEventListener("keydown", alPresionarTecla);
  });

  function mensajeErrorEnvio(error: unknown): string {
    const status = estadoHttp(error);
    if (status === 403) {
      return "Tu rol no tiene permiso para guardar la calibración. Se requiere rol Administrador o Analista.";
    }
    if (status === 404) {
      return "No se encontró el partido indicado dentro de tu club.";
    }
    return mensajeDeError(error);
  }

  const etiquetaDestinoActual = modoLibre
    ? puntoLibrePendiente
      ? `Punto libre (${puntoLibrePendiente.x} m, ${puntoLibrePendiente.y} m)`
      : "Haz clic primero en el plano de la cancha (o clic directo para centro)"
    : hitoActivo
      ? `${hitoActivo.nombre} (${hitoActivo.x} m, ${hitoActivo.y} m)`
      : "Plantilla completa (14/14). Selecciona un marcador para ajustarlo o activa el modo libre.";

  return (
    <main className="cal-pagina">
      <div className="cal-navegacion-sup">
        <Link to="/vision" className="volver">
          ← Visión por computadora
        </Link>
        <Link to="/vision/guia-montaje" className="volver">
          Ver guía de montaje (CU-18)
        </Link>
      </div>

      <p className="kicker">P3 · CU-19 y CU-20</p>
      <h1>Calibración de cámara y medidas de cancha</h1>
      <p className="cal-intro">
        Carga un cuadro congelado del partido, verifica las medidas reales del campo y marca al
        menos {MIN_PUNTOS_CALIBRACION} puntos de referencia sobre las líneas del suelo (nunca sobre
        el travesaño).
      </p>

      {AVISO_PROPUESTA_CALIBRACION && (
        <p className="cal-aviso-propuesta" role="note">
          {AVISO_PROPUESTA_CALIBRACION}
        </p>
      )}

      {/* Barra de configuración: cuadro congelado, partido y dimensiones reales */}
      <section
        className="cal-barra-config"
        aria-label="Configuración de imagen y medidas de cancha"
      >
        <div className="cal-campo">
          <label htmlFor={idArchivo}>Cuadro congelado (imagen local)</label>
          <input
            id={idArchivo}
            type="file"
            accept="image/*"
            onChange={alCambiarArchivo}
            className="cal-input-archivo"
          />
        </div>

        <div className="cal-campo cal-campo-corto">
          <label htmlFor={idPartido}>ID del partido</label>
          <input
            id={idPartido}
            type="number"
            min={1}
            step={1}
            value={partidoIdTexto}
            onChange={(e) => {
              setPartidoIdTexto(e.target.value);
              limpiarEstadoEnvio();
            }}
            className="cal-input"
          />
        </div>

        <div className="cal-campo cal-campo-corto">
          <label htmlFor={idLargo}>Largo real (m)</label>
          <input
            id={idLargo}
            type="number"
            min={40.1}
            max={129.9}
            step="0.5"
            value={largoTexto}
            onChange={(e) => alCambiarLargo(e.target.value)}
            className="cal-input"
          />
        </div>

        <div className="cal-campo cal-campo-corto">
          <label htmlFor={idAncho}>Ancho real (m)</label>
          <input
            id={idAncho}
            type="number"
            min={25.1}
            max={89.9}
            step="0.5"
            value={anchoTexto}
            onChange={(e) => alCambiarAncho(e.target.value)}
            className="cal-input"
          />
        </div>
      </section>

      {validacion.erroresMedidas.length > 0 && (
        <div className="cal-alerta cal-alerta-error" role="alert">
          {validacion.erroresMedidas.map((err) => (
            <p key={err}>{err}</p>
          ))}
        </div>
      )}

      {libresFuera.length > 0 && (
        <div className="cal-alerta cal-alerta-aviso" role="status">
          <p>
            Atención: al cambiar las medidas de la cancha, los puntos libres #
            {libresFuera.join(", #")} quedaron fuera de los límites ({largoM} × {anchoM} m).
            Revísalos o elimínalos si no corresponden.
          </p>
        </div>
      )}

      {/* Barra de flujo de marcado y acciones rápidas */}
      <section className="cal-barra-acciones" aria-label="Controles de marcado de puntos">
        <div className="cal-progreso">
          <span
            className={`cal-badge-contador ${
              pares.length >= MIN_PUNTOS_CALIBRACION ? "es-completo" : ""
            }`}
          >
            {pares.length} / {MIN_PUNTOS_CALIBRACION} puntos mínimos
          </span>
          {!modoLibre && hitoActivo && (
            <span className="cal-hito-actual-texto">
              Plantilla: <strong>{hitoActivo.nombre}</strong> ({hitoActivo.x} m, {hitoActivo.y} m)
            </span>
          )}
        </div>

        <div className="cal-botones-accion">
          {!modoLibre && (
            <button
              type="button"
              className="cal-btn"
              onClick={saltarHitoActual}
              disabled={!hitoActivo || hitosDisponibles.length <= 1}
              title="Pasa al siguiente hito de la plantilla si este punto no se ve bien en la cámara"
            >
              Saltar este punto
            </button>
          )}

          <button
            type="button"
            className={`cal-btn ${modoLibre ? "es-activo" : ""}`}
            onClick={() => {
              setModoLibre((prev) => !prev);
              setPuntoLibrePendiente(null);
            }}
          >
            {modoLibre ? "Volver a plantilla guiada" : "Punto libre en cancha (secundario)"}
          </button>

          <button
            type="button"
            className="cal-btn"
            onClick={deshacer}
            disabled={historial.length === 0}
            title="Atajo: Ctrl+Z"
          >
            Deshacer
          </button>

          <button
            type="button"
            className="cal-btn"
            onClick={() => parSeleccionadoId && eliminarPar(parSeleccionadoId)}
            disabled={parSeleccionadoId === null}
            title="Atajo: Supr o Retroceso"
          >
            Eliminar seleccionado
          </button>

          <button
            type="button"
            className="cal-btn cal-btn-peligro"
            onClick={borrarTodos}
            disabled={pares.length === 0}
          >
            Borrar todos
          </button>
        </div>
      </section>

      {/* Paneles lado a lado: Cuadro de cámara y Plano de cancha */}
      <section className="cal-grilla-paneles" aria-label="Visor de cámara y plano de cancha">
        <VisorCuadro
          imagenUrl={imagenUrl}
          nombreArchivo={nombreArchivo}
          dimensiones={dimensiones}
          pares={pares}
          parSeleccionadoId={parSeleccionadoId}
          etiquetaDestinoActual={etiquetaDestinoActual}
          indicePeor={null}
          onCargarDimensiones={(ancho, alto) => setDimensiones({ ancho, alto })}
          onClicNuevoPunto={alClicNuevoPuntoImagen}
          onSeleccionarPar={setParSeleccionadoId}
          onInicioArrastreMarcador={() => {
            limpiarEstadoEnvio();
            guardarInstantanea(pares);
          }}
          onMoverMarcador={(parId, puntoPx) => {
            setPares((prev) =>
              prev.map((par) => (par.id === parId ? { ...par, imagen: puntoPx } : par)),
            );
          }}
        />

        <PlanoCancha
          largoM={largoM}
          anchoM={anchoM}
          plantilla={plantilla}
          hitoActivoId={hitoActivo?.id ?? null}
          modoLibre={modoLibre}
          puntoLibrePendiente={puntoLibrePendiente}
          pares={pares}
          parSeleccionadoId={parSeleccionadoId}
          indicePeor={null}
          onSeleccionarHito={(hitoId) => {
            setModoLibre(false);
            setHitoElegidoManualId(hitoId);
          }}
          onSeleccionarPar={setParSeleccionadoId}
          onElegirPuntoLibre={(puntoM) => {
            setPuntoLibrePendiente(puntoM);
          }}
        />
      </section>

      {/* Lista de pares marcados y envío */}
      <section className="cal-seccion-inferior" aria-labelledby="cal-titulo-pares">
        <div className="cal-cabecera-inferior">
          <div>
            <h2 id="cal-titulo-pares">3. Pares de puntos marcados ({pares.length})</h2>
            <p className="cal-texto-suave">
              Al eliminar un punto, los demás se renumeran automáticamente conservando el
              apareamiento índice a índice.
            </p>
          </div>

          <div className="cal-bloque-envio">
            <button
              type="button"
              className="cal-btn-primario"
              disabled={!puedeGuardarPorRol || !validacion.valido || mutacionGuardar.isPending}
              onClick={() => mutacionGuardar.mutate()}
            >
              {mutacionGuardar.isPending ? "Guardando calibración…" : "Guardar calibración"}
            </button>
            {!puedeGuardarPorRol && (
              <p className="cal-nota-rol" role="note">
                Solo los roles Administrador y Analista pueden guardar la calibración
                {rolActual ? ` (tu rol actual: ${rolActual})` : ""}.
              </p>
            )}
          </div>
        </div>

        {validacion.erroresPuntos.length > 0 && (
          <p className="cal-requisitos-pendientes" role="status">
            {validacion.erroresPuntos.join(" · ")}
          </p>
        )}

        {mutacionGuardar.isError && (
          <div className="cal-alerta cal-alerta-error" role="alert">
            <p>{mensajeErrorEnvio(mutacionGuardar.error)}</p>
          </div>
        )}

        {ultimaCalibracion && (
          <div className="cal-alerta cal-alerta-exito" role="status" aria-live="polite">
            <p>
              <strong>Calibración guardada</strong> (partido #{ultimaCalibracion.partido_id} ·{" "}
              {ultimaCalibracion.puntos_imagen.length} pares · cancha de {ultimaCalibracion.largo_m}{" "}
              × {ultimaCalibracion.ancho_m} m).
            </p>
            {/*
             * TODO T-031 (CU-21): punto de extensión para mostrar `error_medio_m`,
             * `error_max_m`, el estado `valida` (bloqueo > 2 m) y resaltar el
             * `punto_peor` (índice base 0 sobre la lista enviada) pasando `indicePeor`
             * a <VisorCuadro /> y <PlanoCancha />.
             */}
          </div>
        )}

        {pares.length === 0 ? (
          <p className="cal-tabla-vacia">
            Aún no has marcado ningún par. Carga una imagen y haz clic sobre las referencias de la
            cancha.
          </p>
        ) : (
          <div className="cal-tabla-contenedor">
            <table className="cal-tabla">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Referencia</th>
                  <th scope="col">Imagen (px)</th>
                  <th scope="col">Cancha (m)</th>
                  <th scope="col">Origen</th>
                  <th scope="col">Acción</th>
                </tr>
              </thead>
              <tbody>
                {pares.map((par, idx) => {
                  const seleccionado = par.id === parSeleccionadoId;
                  return (
                    <tr
                      key={par.id}
                      className={seleccionado ? "es-seleccionada" : ""}
                      onClick={() => setParSeleccionadoId(par.id)}
                    >
                      <td className="cal-col-num" title={`Índice base 0: ${idx}`}>
                        {idx + 1}
                      </td>
                      <td>{par.etiqueta}</td>
                      <td className="cal-col-mono">
                        ({par.imagen.x}, {par.imagen.y})
                      </td>
                      <td className="cal-col-mono">
                        ({par.cancha.x}, {par.cancha.y})
                      </td>
                      <td>{par.hitoId ? "Plantilla" : "Libre"}</td>
                      <td>
                        <button
                          type="button"
                          className="cal-btn-fila"
                          onClick={(e) => {
                            e.stopPropagation();
                            eliminarPar(par.id);
                          }}
                        >
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
