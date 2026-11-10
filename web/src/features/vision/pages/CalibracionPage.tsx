/**
 * CU-19, CU-20 · Pantalla de marcado de puntos y medidas de cancha (T-030).
 *
 * Muestra el cuadro congelado de la cámara y el plano cenital de la cancha lado
 * a lado. Permite marcar pares de puntos mediante una plantilla de 14 hitos con
 * avance automático (o punto libre secundario), corregirlos arrastrando o con
 * teclado, eliminarlos y enviarlos al backend.
 *
 * Valida el error de la calibración con `/validar` (CU-21, T-031): automático con
 * retardo y manual; señala el punto con mayor error y avisa si no permite iniciar.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import "@/features/vision/calibracion.css";
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import { detectarCalibracionIA, guardarCalibracion, listarPartidos } from "../api";
import {
  ANCHO_CANCHA_DEFECTO_M,
  AVISO_PROPUESTA_CALIBRACION,
  LARGO_CANCHA_DEFECTO_M,
  MIN_PUNTOS_CALIBRACION,
  acotar,
  construirCuerpoCalibracion,
  construirPlantillaCancha,
  formatearMetros,
  indicePeorValido,
  obtenerRolSesionActual,
  paresLibresFueraDeCancha,
  recalcularParesConMedidas,
  redondear2,
  rolPuedeGuardarCalibracion,
  validarEstadoCalibracion,
} from "../calibracion";
import { PanelResultado } from "../components/PanelResultado";
import { PlanoCancha } from "../components/PlanoCancha";
import { VisorCuadro } from "../components/VisorCuadro";
import type { Calibracion, HitoCancha, ParCalibracion, Punto } from "../types";
import { useValidacionCalibracion } from "../useValidacionCalibracion";

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
  const [archivoBlob, setArchivoBlob] = useState<Blob | File | null>(null);
  const [detectandoIA, setDetectandoIA] = useState(false);
  const [mensajeIA, setMensajeIA] = useState<string | null>(null);

  // Cámara en vivo (WebRTC / getUserMedia) para congelar un cuadro directamente
  const [camaraActiva, setCamaraActiva] = useState(false);
  const [camarasDisponibles, setCamarasDisponibles] = useState<MediaDeviceInfo[]>([]);
  const [camaraDeviceId, setCamaraDeviceId] = useState<string>("");
  const [errorCamara, setErrorCamara] = useState<string | null>(null);
  const videoCamaraRef = useRef<HTMLVideoElement | null>(null);
  const streamCamaraRef = useRef<MediaStream | null>(null);

  // Parámetros del partido y dimensiones reales editables (CU-20)
  const [searchParams] = useSearchParams();
  const paramPartidoInicial = searchParams.get("partidoId")?.trim() || null;
  const [partidoIdTexto, setPartidoIdTexto] = useState(paramPartidoInicial || "1");
  const partidosClub = useQuery({
    queryKey: ["vision", "partidos"],
    queryFn: listarPartidos,
  });

  // Si no se pasó ?partidoId en la URL y hay partidos del club, selecciona el primero del club
  useEffect(() => {
    if (paramPartidoInicial) return;
    const lista = partidosClub.data;
    if (!lista || lista.length === 0) return;
    const actualExiste = lista.some((p) => String(p.id) === partidoIdTexto);
    if (!actualExiste) {
      setPartidoIdTexto(String(lista[0].id));
    }
  }, [paramPartidoInicial, partidosClub.data, partidoIdTexto]);
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

  // Limpieza del stream de cámara al desmontar la página
  useEffect(() => {
    return () => {
      if (streamCamaraRef.current) {
        streamCamaraRef.current.getTracks().forEach((t) => t.stop());
        streamCamaraRef.current = null;
      }
    };
  }, []);

  async function abrirCamaraEnVivo(deviceIdPreferido?: string) {
    setErrorCamara(null);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorCamara("Tu navegador no permite acceder a cámaras de video (getUserMedia).");
      return;
    }
    try {
      if (streamCamaraRef.current) {
        streamCamaraRef.current.getTracks().forEach((t) => t.stop());
      }
      const idElegido = deviceIdPreferido ?? camaraDeviceId;
      const constraints: MediaStreamConstraints = {
        video: idElegido
          ? { deviceId: { exact: idElegido }, width: { ideal: 1920 }, height: { ideal: 1080 } }
          : { width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamCamaraRef.current = stream;
      setCamaraActiva(true);

      const dispositivos = await navigator.mediaDevices.enumerateDevices();
      const cams = dispositivos.filter((d) => d.kind === "videoinput");
      setCamarasDisponibles(cams);
      if (!idElegido && cams.length > 0 && cams[0]) {
        setCamaraDeviceId(cams[0].deviceId);
      }

      requestAnimationFrame(() => {
        if (videoCamaraRef.current) {
          videoCamaraRef.current.srcObject = stream;
          void videoCamaraRef.current.play();
        }
      });
    } catch (err) {
      setErrorCamara(
        err instanceof Error
          ? `No se pudo abrir la cámara: ${err.message}`
          : "No se pudo acceder a la cámara conectada.",
      );
      setCamaraActiva(false);
    }
  }

  function cerrarCamaraEnVivo() {
    if (streamCamaraRef.current) {
      streamCamaraRef.current.getTracks().forEach((t) => t.stop());
      streamCamaraRef.current = null;
    }
    setCamaraActiva(false);
  }

  function congelarCuadroCamara() {
    const videoEl = videoCamaraRef.current;
    if (!videoEl || videoEl.videoWidth <= 0 || videoEl.videoHeight <= 0) {
      setErrorCamara("La cámara aún no está entregando imagen de video.");
      return;
    }
    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(videoEl, 0, 0, w, h);

    canvas.toBlob((blob) => {
      if (!blob) return;
      if (imagenUrl) {
        URL.revokeObjectURL(imagenUrl);
      }
      const nuevaUrl = URL.createObjectURL(blob);
      setImagenUrl(nuevaUrl);
      setArchivoBlob(blob);
      setNombreArchivo(`captura_camara_${w}x${h}.png`);
      setDimensiones({ ancho: w, alto: h });
      limpiarEstadoEnvio();
      cerrarCamaraEnVivo();
    }, "image/png");
  }

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

  // Cuerpo común de «Validar» y «Guardar»; `null` mientras no cumpla los requisitos de cliente.
  const cuerpo = useMemo(
    () => (validacion.valido ? construirCuerpoCalibracion(pares, largoM, anchoM) : null),
    [validacion.valido, pares, largoM, anchoM],
  );

  // Validación del error con /validar (CU-21): automática con retardo + manual.
  const validacionError = useValidacionCalibracion(validacion.partidoId, cuerpo);
  const resultadoError = validacionError.resultado;
  // Solo se resalta si hay un resultado de los puntos ACTUALES y el índice es válido.
  const indicePeor = indicePeorValido(resultadoError?.punto_peor, pares.length);
  const peorEnAlerta = resultadoError !== null && !resultadoError.valida;
  const errorNoValido = peorEnAlerta;

  const mutacionGuardar = useMutation({
    mutationFn: async () => {
      if (!validacion.valido || validacion.partidoId === null) {
        throw new Error("Revisa los datos antes de guardar.");
      }
      return guardarCalibracion(
        validacion.partidoId,
        construirCuerpoCalibracion(pares, largoM, anchoM),
      );
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
    setArchivoBlob(archivo);
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

  function autocompletarPuntosValidos() {
    limpiarEstadoEnvio();
    guardarInstantanea(pares);

    const anchoPx = dimensiones?.ancho ?? 1280;
    const altoPx = dimensiones?.alto ?? 720;

    if (!imagenUrl) {
      const svgPrueba = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
        <rect width="1280" height="720" fill="#1b5e36"/>
        <rect x="90" y="60" width="1100" height="600" fill="#217040" stroke="#ffffff" stroke-width="4"/>
        <line x1="640" y1="60" x2="640" y2="660" stroke="#ffffff" stroke-width="4"/>
        <circle cx="640" cy="360" r="85" fill="none" stroke="#ffffff" stroke-width="4"/>
        <rect x="90" y="182" width="173" height="356" fill="none" stroke="#ffffff" stroke-width="4"/>
        <rect x="1017" y="182" width="173" height="356" fill="none" stroke="#ffffff" stroke-width="4"/>
      </svg>`;
      const blob = new Blob([svgPrueba], { type: "image/svg+xml" });
      setImagenUrl(URL.createObjectURL(blob));
      setNombreArchivo("cuadro_referencia_cancha.svg");
      setDimensiones({ ancho: 1280, alto: 720 });
    }

    const L = Number.isFinite(largoM) && largoM > 0 ? largoM : LARGO_CANCHA_DEFECTO_M;
    const W = Number.isFinite(anchoM) && anchoM > 0 ? anchoM : ANCHO_CANCHA_DEFECTO_M;
    const margenX = 90;
    const margenY = 60;
    const utilW = Math.max(200, anchoPx - margenX * 2);
    const utilH = Math.max(150, altoPx - margenY * 2);

    const hitosBase = plantilla.slice(0, MIN_PUNTOS_CALIBRACION);
    const nuevos: ParCalibracion[] = hitosBase.map((hito) => ({
      id: `par-${contadorIdRef.current++}`,
      hitoId: hito.id,
      etiqueta: hito.nombre,
      imagen: {
        x: redondear2(margenX + (hito.x / L) * utilW),
        y: redondear2(margenY + ((W - hito.y) / W) * utilH),
      },
      cancha: { x: hito.x, y: hito.y },
    }));

    setModoLibre(false);
    setPares(nuevos);
    setParSeleccionadoId(nuevos[nuevos.length - 1]?.id ?? null);
  }

  async function detectarPuntosConIA() {
    limpiarEstadoEnvio();
    setMensajeIA(null);

    let blobAEnviar: Blob | null = archivoBlob;
    if (!blobAEnviar && imagenUrl) {
      try {
        const resp = await fetch(imagenUrl);
        blobAEnviar = await resp.blob();
      } catch {
        blobAEnviar = null;
      }
    }

    if (!blobAEnviar) {
      setMensajeIA("Primero carga una imagen o congela un cuadro de la cámara para analizarlo con IA.");
      return;
    }

    setDetectandoIA(true);
    try {
      const pid = validacion.partidoId ?? (Number(partidoIdTexto) || 1);
      const data = await detectarCalibracionIA(
        pid,
        blobAEnviar,
        largoM,
        anchoM,
      );

      if (!data.es_valida || !data.puntos_imagen || data.puntos_imagen.length < 4) {
        setMensajeIA(
          `Solo se detectaron ${data.puntos_detectados} puntos (${data.puntos_inliers} válidos). Se requieren al menos 4 puntos visibles de la cancha.`
        );
        return;
      }

      guardarInstantanea(pares);
      const nuevos: ParCalibracion[] = data.puntos_imagen.map((ptImg, idx) => {
        const ptCnc = data.puntos_cancha[idx];
        return {
          id: `par-${contadorIdRef.current++}`,
          hitoId: null,
          etiqueta: `IA P${idx + 1}`,
          imagen: { x: redondear2(ptImg.x), y: redondear2(ptImg.y) },
          cancha: { x: redondear2(ptCnc.x), y: redondear2(ptCnc.y) },
        };
      });

      setModoLibre(true);
      setPares(nuevos);
      setParSeleccionadoId(nuevos[0]?.id ?? null);
      setMensajeIA(
        `¡Excelente! ${nuevos.length} puntos reglamentarios detectados por IA con error medio de ${data.error_medio_m} m.`
      );
    } catch (err: unknown) {
      setMensajeIA(`Error al detectar con IA: ${mensajeDeError(err)}`);
    } finally {
      setDetectandoIA(false);
    }
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
          <label htmlFor={idArchivo}>Fuente del cuadro (Imagen o Cámara en vivo)</label>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              id={idArchivo}
              type="file"
              accept="image/*"
              onChange={alCambiarArchivo}
              className="cal-input-archivo"
            />
            <button
              type="button"
              className={`cal-btn ${camaraActiva ? "es-activo" : ""}`}
              onClick={() => (camaraActiva ? cerrarCamaraEnVivo() : void abrirCamaraEnVivo())}
            >
              {camaraActiva ? "Cerrar cámara en vivo" : "Usar cámara en vivo"}
            </button>
          </div>
        </div>

        <div className="cal-campo">
          <label htmlFor={idPartido}>Partido del club</label>
          {partidosClub.data && partidosClub.data.length > 0 ? (
            <select
              id={idPartido}
              value={partidoIdTexto}
              onChange={(e) => {
                setPartidoIdTexto(e.target.value);
                limpiarEstadoEnvio();
              }}
              className="cal-input"
            >
              {partidosClub.data.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  #{p.id} · vs {p.rival} · {p.sede} ({p.estado})
                </option>
              ))}
            </select>
          ) : (
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
          )}
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

      {errorCamara && (
        <div className="cal-alerta cal-alerta-error" role="alert">
          <p>{errorCamara}</p>
        </div>
      )}

      {camaraActiva && (
        <section
          className="cal-barra-config"
          aria-label="Vista previa de cámara en vivo"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div>
              <strong>Cámara en vivo conectada</strong>
              <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--text-2)" }}>
                Enfoca la cancha y pulsa «Congelar cuadro para calibrar» para tomar la captura
                exacta de la lente.
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              {camarasDisponibles.length > 1 && (
                <select
                  value={camaraDeviceId}
                  onChange={(e) => {
                    const nuevoId = e.target.value;
                    setCamaraDeviceId(nuevoId);
                    void abrirCamaraEnVivo(nuevoId);
                  }}
                  className="cal-input"
                >
                  {camarasDisponibles.map((cam, idx) => (
                    <option key={cam.deviceId || idx} value={cam.deviceId}>
                      {cam.label || `Cámara #${idx + 1}`}
                    </option>
                  ))}
                </select>
              )}
              <button
                type="button"
                className="cal-btn-primario"
                onClick={congelarCuadroCamara}
              >
                Congelar cuadro para calibrar
              </button>
              <button type="button" className="cal-btn" onClick={cerrarCamaraEnVivo}>
                Cancelar
              </button>
            </div>
          </div>

          <div
            style={{
              width: "100%",
              maxWidth: 860,
              margin: "0 auto",
              borderRadius: 8,
              overflow: "hidden",
              border: "1px solid var(--line)",
              background: "#000",
            }}
          >
            <video
              ref={videoCamaraRef}
              muted
              playsInline
              style={{ width: "100%", maxHeight: 440, display: "block", objectFit: "contain" }}
            />
          </div>
        </section>
      )}

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
            className="cal-btn"
            style={{
              backgroundColor: "#0284c7",
              color: "#ffffff",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
            onClick={detectarPuntosConIA}
            disabled={detectandoIA}
            title="Analiza el cuadro con la red neuronal especializada para encontrar automáticamente las líneas y áreas de la cancha"
          >
            {detectandoIA ? "Detectando con IA..." : "⚡ Detectar puntos con IA"}
          </button>

          <button
            type="button"
            className="cal-btn"
            onClick={autocompletarPuntosValidos}
            title="Genera 8 pares de referencia válidos listos para validar y guardar"
          >
            Autocompletar 8 puntos válidos
          </button>

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
        {mensajeIA && (
          <div
            style={{
              marginTop: 10,
              padding: "8px 14px",
              borderRadius: 6,
              fontSize: 13,
              backgroundColor: mensajeIA.startsWith("¡Excelente!") ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
              color: mensajeIA.startsWith("¡Excelente!") ? "#10b981" : "#ef4444",
              border: `1px solid ${mensajeIA.startsWith("¡Excelente!") ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
            }}
          >
            {mensajeIA}
          </div>
        )}
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
          indicePeor={indicePeor}
          peorEnAlerta={peorEnAlerta}
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
          indicePeor={indicePeor}
          peorEnAlerta={peorEnAlerta}
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

      {/* Validación del error con /validar (CU-21): reserva su espacio, no salta de altura */}
      <PanelResultado
        validacion={validacionError}
        cantidadPares={pares.length}
        requisitosPendientes={[...validacion.erroresMedidas, ...validacion.erroresPuntos]}
      />

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
              {mutacionGuardar.isPending
                ? "Guardando calibración…"
                : errorNoValido
                  ? "Guardar de todos modos (quedará NO válida)"
                  : "Guardar calibración"}
            </button>
            {errorNoValido && puedeGuardarPorRol && (
              <p className="cal-nota-rol" role="note">
                Se puede guardar, pero quedará marcada como NO válida y no permitirá iniciar el
                partido hasta que corrijas los puntos.
              </p>
            )}
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
          <div
            className={`cal-alerta ${
              ultimaCalibracion.valida ? "cal-alerta-exito" : "cal-alerta-aviso"
            }`}
            role="status"
            aria-live="polite"
          >
            <p>
              <strong>
                {ultimaCalibracion.valida
                  ? "Calibración guardada"
                  : "Calibración guardada, pero NO permite iniciar el partido"}
              </strong>{" "}
              (partido #{ultimaCalibracion.partido_id} · {ultimaCalibracion.puntos_imagen.length}{" "}
              pares · cancha de {ultimaCalibracion.largo_m} × {ultimaCalibracion.ancho_m} m
              {ultimaCalibracion.error_medio_m !== null && ultimaCalibracion.error_max_m !== null
                ? ` · error medio ${formatearMetros(ultimaCalibracion.error_medio_m)} m, máximo ${formatearMetros(ultimaCalibracion.error_max_m)} m`
                : ""}
              ).
            </p>
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
                  const esPeor = indicePeor === idx;
                  return (
                    <tr
                      key={par.id}
                      className={`${seleccionado ? "es-seleccionada" : ""} ${
                        esPeor ? `es-peor-fila ${peorEnAlerta ? "es-alerta" : "es-suave"}` : ""
                      }`}
                      onClick={() => setParSeleccionadoId(par.id)}
                    >
                      <td className="cal-col-num" title={`Índice base 0: ${idx}`}>
                        {idx + 1}
                      </td>
                      <td>
                        {par.etiqueta}
                        {esPeor && <span className="cal-insignia-peor">▲ Mayor error</span>}
                      </td>
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
