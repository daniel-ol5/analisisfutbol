/**
 * CU-29 · Versionado de modelos ML (T-063).
 *
 * Lista las versiones de modelo registradas en el club (más nueva primero),
 * permite registrar una versión ya entrenada (nunca activa por defecto) y
 * activar una versión existente; el backend desactiva cualquier otra del
 * mismo club, de modo que siempre hay a lo sumo una versión activa.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import "@/features/vision/modelos.css";
import { estadoHttp, mensajeDeError } from "@/shared/lib/errors";

import { activarModelo, listarModelos, registrarModelo } from "../api";
import { obtenerRolSesionActual } from "../calibracion";
import type { Modelo, ModeloCrear, TipoModelo } from "../types";

const CLAVE_MODELOS = ["vision", "modelos"] as const;

/** Roles autorizados por el backend para `POST /vision/modelos` y `/activar`. */
const ROLES_PUEDEN_GESTIONAR_MODELOS: readonly string[] = ["ADMIN", "ANALISTA"];

function rolPuedeGestionarModelos(rol: string | null): boolean {
  return rol !== null && ROLES_PUEDEN_GESTIONAR_MODELOS.includes(rol);
}

interface FormularioModelo {
  nombre: string;
  version: string;
  tipo: TipoModelo;
  archivo_url: string;
  map50_jugador: string;
  map50_balon: string;
  idf1: string;
  notas: string;
}

const FORMULARIO_VACIO: FormularioModelo = {
  nombre: "",
  version: "",
  tipo: "DETECCION",
  archivo_url: "",
  map50_jugador: "",
  map50_balon: "",
  idf1: "",
  notas: "",
};

/** Convierte un texto de métrica opcional a número, o `null` si está vacío. */
function numeroOpcional(texto: string): number | null {
  const limpio = texto.trim();
  if (limpio === "") return null;
  const num = Number(limpio);
  return Number.isFinite(num) ? num : null;
}

function formularioADatos(form: FormularioModelo): ModeloCrear {
  return {
    nombre: form.nombre.trim(),
    version: form.version.trim(),
    tipo: form.tipo,
    archivo_url: form.archivo_url.trim(),
    map50_jugador: numeroOpcional(form.map50_jugador),
    map50_balon: numeroOpcional(form.map50_balon),
    idf1: numeroOpcional(form.idf1),
    notas: form.notas.trim(),
  };
}

function formatoFecha(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatoMetrica(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? "—" : valor.toString();
}

export function ModelosPage() {
  const idNombre = useId();
  const idVersion = useId();
  const idTipo = useId();
  const idArchivoUrl = useId();
  const idMap50Jugador = useId();
  const idMap50Balon = useId();
  const idIdf1 = useId();
  const idNotas = useId();

  const rolActual = obtenerRolSesionActual();
  const puedeGestionar = rolPuedeGestionarModelos(rolActual);

  const cliente = useQueryClient();
  const [form, setForm] = useState<FormularioModelo>(FORMULARIO_VACIO);
  const [activandoId, setActivandoId] = useState<number | null>(null);

  const consultaModelos = useQuery({
    queryKey: CLAVE_MODELOS,
    queryFn: listarModelos,
  });

  const mutacionRegistrar = useMutation({
    mutationFn: (datos: ModeloCrear) => registrarModelo(datos),
    onSuccess: () => {
      setForm(FORMULARIO_VACIO);
      void cliente.invalidateQueries({ queryKey: CLAVE_MODELOS });
    },
  });

  const mutacionActivar = useMutation({
    mutationFn: (modeloId: number) => activarModelo(modeloId),
    onMutate: (modeloId: number) => setActivandoId(modeloId),
    onSettled: () => setActivandoId(null),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: CLAVE_MODELOS });
    },
  });

  function mensajeErrorRegistro(error: unknown): string {
    const status = estadoHttp(error);
    if (status === 403) {
      return "Tu rol no tiene permiso para registrar modelos. Se requiere rol Administrador o Analista.";
    }
    if (status === 409) {
      return "Ya existe una versión registrada con ese nombre y número de versión.";
    }
    return mensajeDeError(error);
  }

  function mensajeErrorActivar(error: unknown): string {
    const status = estadoHttp(error);
    if (status === 403) {
      return "Tu rol no tiene permiso para activar modelos. Se requiere rol Administrador o Analista.";
    }
    if (status === 404) {
      return "No se encontró esa versión dentro de tu club.";
    }
    return mensajeDeError(error);
  }

  function alEnviarFormulario(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!puedeGestionar) return;
    mutacionRegistrar.mutate(formularioADatos(form));
  }

  const modelos: Modelo[] = consultaModelos.data ?? [];

  return (
    <main className="mod-pagina">
      <Link to="/vision" className="volver">
        ← Visión por computadora
      </Link>

      <p className="kicker">P3 · CU-29</p>
      <h1>Versionado de modelos ML</h1>
      <p className="mod-intro">
        Registra aquí las versiones de modelo (detección o pose) ya entrenadas fuera de la
        plataforma. Solo una versión puede estar activa por club a la vez: el worker usa la versión
        activa en el siguiente procesamiento, y activar una versión desactiva automáticamente
        cualquier otra, sin necesidad de reentrenar.
      </p>

      {!puedeGestionar && (
        <p className="mod-nota-rol" role="note">
          Solo los roles Administrador y Analista pueden registrar o activar versiones
          {rolActual ? ` (tu rol actual: ${rolActual})` : ""}. Puedes ver el listado en modo
          lectura.
        </p>
      )}

      <form
        className="mod-formulario"
        onSubmit={alEnviarFormulario}
        aria-label="Registrar versión de modelo"
      >
        <div className="mod-campo">
          <label htmlFor={idNombre}>Nombre</label>
          <input
            id={idNombre}
            type="text"
            value={form.nombre}
            onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
            className="mod-input"
            required
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo">
          <label htmlFor={idVersion}>Versión</label>
          <input
            id={idVersion}
            type="text"
            placeholder="p. ej. v1.2.0"
            value={form.version}
            onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
            className="mod-input"
            required
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo">
          <label htmlFor={idTipo}>Tipo</label>
          <select
            id={idTipo}
            value={form.tipo}
            onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value as TipoModelo }))}
            className="mod-select"
            disabled={!puedeGestionar}
          >
            <option value="DETECCION">Detección</option>
            <option value="POSE">Pose</option>
          </select>
        </div>

        <div className="mod-campo mod-campo-ancho">
          <label htmlFor={idArchivoUrl}>URL del archivo del modelo (https)</label>
          <input
            id={idArchivoUrl}
            type="url"
            placeholder="https://..."
            value={form.archivo_url}
            onChange={(e) => setForm((f) => ({ ...f, archivo_url: e.target.value }))}
            className="mod-input"
            required
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo">
          <label htmlFor={idMap50Jugador}>mAP@50 jugador (opcional)</label>
          <input
            id={idMap50Jugador}
            type="number"
            step="0.0001"
            min={0}
            max={1}
            value={form.map50_jugador}
            onChange={(e) => setForm((f) => ({ ...f, map50_jugador: e.target.value }))}
            className="mod-input"
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo">
          <label htmlFor={idMap50Balon}>mAP@50 balón (opcional)</label>
          <input
            id={idMap50Balon}
            type="number"
            step="0.0001"
            min={0}
            max={1}
            value={form.map50_balon}
            onChange={(e) => setForm((f) => ({ ...f, map50_balon: e.target.value }))}
            className="mod-input"
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo">
          <label htmlFor={idIdf1}>IDF1 (opcional)</label>
          <input
            id={idIdf1}
            type="number"
            step="0.0001"
            min={0}
            max={1}
            value={form.idf1}
            onChange={(e) => setForm((f) => ({ ...f, idf1: e.target.value }))}
            className="mod-input"
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-campo mod-campo-ancho">
          <label htmlFor={idNotas}>Notas (opcional)</label>
          <input
            id={idNotas}
            type="text"
            value={form.notas}
            onChange={(e) => setForm((f) => ({ ...f, notas: e.target.value }))}
            className="mod-input"
            disabled={!puedeGestionar}
          />
        </div>

        <div className="mod-formulario-acciones">
          <button
            type="submit"
            className="mod-btn-primario"
            disabled={!puedeGestionar || mutacionRegistrar.isPending}
          >
            {mutacionRegistrar.isPending ? "Registrando…" : "Registrar versión"}
          </button>
        </div>
      </form>

      {mutacionRegistrar.isError && (
        <div className="mod-alerta mod-alerta-error" role="alert">
          <p>{mensajeErrorRegistro(mutacionRegistrar.error)}</p>
        </div>
      )}

      {mutacionRegistrar.isSuccess && (
        <div className="mod-alerta mod-alerta-exito" role="status" aria-live="polite">
          <p>Versión registrada correctamente. Actívala cuando quieras usarla en el worker.</p>
        </div>
      )}

      {mutacionActivar.isError && (
        <div className="mod-alerta mod-alerta-error" role="alert">
          <p>{mensajeErrorActivar(mutacionActivar.error)}</p>
        </div>
      )}

      {consultaModelos.isError ? (
        <div className="mod-alerta mod-alerta-error" role="alert">
          <p>{mensajeDeError(consultaModelos.error)}</p>
        </div>
      ) : consultaModelos.isLoading ? (
        <p className="mod-tabla-vacia">Cargando versiones…</p>
      ) : modelos.length === 0 ? (
        <p className="mod-tabla-vacia">Aún no hay versiones registradas en este club.</p>
      ) : (
        <div className="mod-tabla-contenedor">
          <table className="mod-tabla">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Versión</th>
                <th scope="col">Tipo</th>
                <th scope="col">mAP@50 jugador</th>
                <th scope="col">mAP@50 balón</th>
                <th scope="col">IDF1</th>
                <th scope="col">Entrenado en</th>
                <th scope="col">Estado</th>
                <th scope="col">Acción</th>
              </tr>
            </thead>
            <tbody>
              {modelos.map((modelo) => (
                <tr key={modelo.id} className={modelo.activo ? "es-activa" : ""}>
                  <td>{modelo.nombre}</td>
                  <td>{modelo.version}</td>
                  <td>{modelo.tipo === "DETECCION" ? "Detección" : "Pose"}</td>
                  <td>{formatoMetrica(modelo.map50_jugador)}</td>
                  <td>{formatoMetrica(modelo.map50_balon)}</td>
                  <td>{formatoMetrica(modelo.idf1)}</td>
                  <td>{formatoFecha(modelo.entrenado_en)}</td>
                  <td>
                    {modelo.activo ? (
                      <span className="mod-badge-activo">Activo</span>
                    ) : (
                      <span className="mod-badge-inactivo">Inactivo</span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="mod-btn-fila"
                      disabled={
                        !puedeGestionar ||
                        modelo.activo ||
                        (mutacionActivar.isPending && activandoId === modelo.id)
                      }
                      onClick={() => mutacionActivar.mutate(modelo.id)}
                    >
                      {mutacionActivar.isPending && activandoId === modelo.id
                        ? "Activando…"
                        : "Activar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
