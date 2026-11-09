import { useState, type FormEvent } from "react";

import { useSesion } from "@/features/seguridad/session";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Button, Input, Select } from "@/shared/ui";

import {
  useCompeticiones,
  useCrearCompeticion,
  useEquiposParaPartido,
  useProgramarPartido,
} from "../hooks";
import type { Competicion, Partido } from "../types";
import { AgendaPartidos } from "./AgendaPartidos";
import "./partidos.css";

type CampoFormulario = "equipo" | "rival" | "fecha" | "hora" | "sede";
type ErroresFormulario = Partial<Record<CampoFormulario, string>>;

function fechaLocal(fecha = new Date()): string {
  const anio = fecha.getFullYear();
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  const dia = String(fecha.getDate()).padStart(2, "0");
  return `${anio}-${mes}-${dia}`;
}

function fechaLegible(valor: string): string {
  return new Intl.DateTimeFormat("es-BO", {
    dateStyle: "full",
    timeStyle: "short",
  }).format(new Date(valor));
}

export function PartidosView({
  onVerAlineacion,
}: { onVerAlineacion?: (partidoId: number) => void } = {}) {
  const sesion = useSesion();
  const esAdmin = sesion?.usuario.rol === "ADMIN";
  const puedeProgramar = esAdmin || sesion?.usuario.rol === "DT";
  const equipos = useEquiposParaPartido(puedeProgramar);
  const competiciones = useCompeticiones(puedeProgramar);
  const programar = useProgramarPartido();
  const crearCompeticionMut = useCrearCompeticion();

  const [mostrarFormCompeticion, setMostrarFormCompeticion] = useState(false);
  const [nombreCompeticion, setNombreCompeticion] = useState("");
  const [temporadaCompeticion, setTemporadaCompeticion] = useState(
    String(new Date().getFullYear()),
  );
  const [fechaInicioComp, setFechaInicioComp] = useState("");
  const [fechaFinComp, setFechaFinComp] = useState("");
  const [errorCompeticion, setErrorCompeticion] = useState<string | null>(null);
  const [competicionCreada, setCompeticionCreada] = useState<Competicion | null>(null);

  const [equipoId, setEquipoId] = useState("");
  const [rival, setRival] = useState("");
  const [condicion, setCondicion] = useState<"LOCAL" | "VISITANTE">("LOCAL");
  const [fecha, setFecha] = useState("");
  const [hora, setHora] = useState("");
  const [sede, setSede] = useState("");
  const [competicionId, setCompeticionId] = useState("");
  const [errores, setErrores] = useState<ErroresFormulario>({});
  const [partidoCreado, setPartidoCreado] = useState<Partido | null>(null);

  const limpiarError = (campo: CampoFormulario) => {
    setErrores((actuales) => ({ ...actuales, [campo]: undefined }));
    setPartidoCreado(null);
    if (programar.isError) programar.reset();
  };

  const alEnviar = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    const siguientes: ErroresFormulario = {};

    if (!equipoId) siguientes.equipo = "Selecciona el equipo propio.";
    if (!rival.trim()) siguientes.rival = "Escribe el nombre del rival.";
    if (!fecha) siguientes.fecha = "Selecciona la fecha del partido.";
    if (!hora) siguientes.hora = "Selecciona la hora del partido.";
    if (!sede.trim()) siguientes.sede = "Escribe la sede o cancha.";

    let fechaHora: Date | null = null;
    if (fecha && hora) {
      fechaHora = new Date(`${fecha}T${hora}`);
      if (Number.isNaN(fechaHora.getTime()) || fechaHora.getTime() <= Date.now()) {
        siguientes.fecha = "La fecha y hora deben estar en el futuro.";
        siguientes.hora = "La fecha y hora deben estar en el futuro.";
      }
    }

    setErrores(siguientes);
    if (Object.keys(siguientes).length > 0 || fechaHora === null) return;

    try {
      const creado = await programar.mutateAsync({
        equipo_id: Number(equipoId),
        rival: rival.trim(),
        es_local: condicion === "LOCAL",
        fecha_hora: fechaHora.toISOString(),
        sede: sede.trim(),
        competicion_id: competicionId ? Number(competicionId) : null,
      });
      setPartidoCreado(creado);
      setRival("");
      setFecha("");
      setHora("");
      setSede("");
      setCompeticionId("");
      setErrores({});
    } catch {
      // React Query conserva el error para mostrarlo debajo del formulario.
    }
  };

  const alCrearCompeticion = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setErrorCompeticion(null);
    setCompeticionCreada(null);

    if (!nombreCompeticion.trim()) {
      setErrorCompeticion("Escribe el nombre de la competición (ej. LaLiga EA Sports).");
      return;
    }
    if (!temporadaCompeticion.trim()) {
      setErrorCompeticion("Escribe la temporada (ej. 2026 o 2025/2026).");
      return;
    }
    if (Boolean(fechaInicioComp) !== Boolean(fechaFinComp)) {
      setErrorCompeticion("Si indicas fechas de la competición, debes completar inicio y fin.");
      return;
    }
    if (fechaInicioComp && fechaFinComp && fechaFinComp < fechaInicioComp) {
      setErrorCompeticion("La fecha de fin no puede ser anterior a la fecha de inicio.");
      return;
    }

    try {
      const nueva = await crearCompeticionMut.mutateAsync({
        nombre: nombreCompeticion.trim(),
        temporada: temporadaCompeticion.trim(),
        fecha_inicio: fechaInicioComp || null,
        fecha_fin: fechaFinComp || null,
      });
      setCompeticionCreada(nueva);
      setCompeticionId(String(nueva.id));
      setNombreCompeticion("");
      setFechaInicioComp("");
      setFechaFinComp("");
      setMostrarFormCompeticion(false);
    } catch (err) {
      setErrorCompeticion(mensajeDeError(err));
    }
  };

  const errorCarga = equipos.error ?? competiciones.error;
  const cargando = equipos.isLoading || competiciones.isLoading;
  const sinEquipos = !cargando && (equipos.data?.length ?? 0) === 0;

  if (!puedeProgramar) {
    return <AgendaPartidos onVerAlineacion={onVerAlineacion} />;
  }

  return (
    <section className="partidos-vista" aria-labelledby="partidos-titulo">
      <div className="partidos-cabecera">
        <div>
          <span className="kicker">CU-14 · PROGRAMACIÓN DE PARTIDOS</span>
          <h3 id="partidos-titulo">Programar un encuentro</h3>
          <p>
            Registra la logística del partido. Al guardar quedará disponible en estado PROGRAMADO
            para la agenda y la alineación.
          </p>
        </div>
        <span className="partidos-estado-inicial">Estado inicial · PROGRAMADO</span>
      </div>

      {errorCarga && (
        <Alert tono="error" titulo="No se pudieron cargar los datos">
          <p>{mensajeDeError(errorCarga)}</p>
          <Button
            variante="secundario"
            onClick={() => {
              void equipos.refetch();
              void competiciones.refetch();
            }}
          >
            Reintentar
          </Button>
        </Alert>
      )}

      {partidoCreado && (
        <Alert tono="ok" titulo="Partido programado correctamente">
          {partidoCreado.rival} · {fechaLegible(partidoCreado.fecha_hora)} · {partidoCreado.sede}
        </Alert>
      )}

      {competicionCreada && (
        <Alert tono="ok" titulo="Competición registrada (CU-13)">
          {competicionCreada.nombre} · Temporada {competicionCreada.temporada} quedó disponible y
          seleccionada para programar partidos.
        </Alert>
      )}

      {/* CU-13 · Gestión de Competiciones y Temporadas */}
      <div
        className="partidos-formulario"
        style={{ marginBottom: 18, padding: "16px 20px" }}
        aria-labelledby="competiciones-titulo"
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
            <span className="kicker">CU-13 · COMPETICIONES Y TEMPORADAS</span>
            <h4 id="competiciones-titulo" style={{ margin: "2px 0 4px", fontSize: 16 }}>
              Torneos del club ({competiciones.data?.length ?? 0})
            </h4>
            <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)" }}>
              {competiciones.data && competiciones.data.length > 0
                ? competiciones.data.map((c) => `${c.nombre} (${c.temporada})`).join(" · ")
                : "Aún no hay competiciones registradas en el club. Registra un torneo oficial o programa partidos amistosos."}
            </p>
          </div>
          {esAdmin && (
            <Button
              type="button"
              variante={mostrarFormCompeticion ? "secundario" : "primario"}
              onClick={() => {
                setErrorCompeticion(null);
                setMostrarFormCompeticion((prev) => !prev);
              }}
            >
              {mostrarFormCompeticion ? "Cancelar" : "+ Nueva competición"}
            </Button>
          )}
        </div>

        {esAdmin && mostrarFormCompeticion && (
          <form
            onSubmit={alCrearCompeticion}
            noValidate
            style={{
              marginTop: 16,
              paddingTop: 16,
              borderTop: "1px solid var(--line)",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            <div className="partidos-grilla">
              <Input
                etiqueta="Nombre de la competición *"
                placeholder="Ej. LaLiga EA Sports, Copa del Rey"
                maxLength={120}
                value={nombreCompeticion}
                disabled={crearCompeticionMut.isPending}
                onChange={(e) => setNombreCompeticion(e.currentTarget.value)}
              />
              <Input
                etiqueta="Temporada *"
                placeholder="Ej. 2026 o 2025/2026"
                maxLength={20}
                value={temporadaCompeticion}
                disabled={crearCompeticionMut.isPending}
                onChange={(e) => setTemporadaCompeticion(e.currentTarget.value)}
              />
              <Input
                etiqueta="Fecha de inicio (opcional)"
                type="date"
                value={fechaInicioComp}
                disabled={crearCompeticionMut.isPending}
                onChange={(e) => setFechaInicioComp(e.currentTarget.value)}
              />
              <Input
                etiqueta="Fecha de finalización (opcional)"
                type="date"
                value={fechaFinComp}
                disabled={crearCompeticionMut.isPending}
                onChange={(e) => setFechaFinComp(e.currentTarget.value)}
              />
            </div>
            {errorCompeticion && (
              <Alert tono="error" titulo="No se pudo registrar la competición">
                {errorCompeticion}
              </Alert>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button type="submit" disabled={crearCompeticionMut.isPending}>
                {crearCompeticionMut.isPending ? "Guardando…" : "Guardar competición"}
              </Button>
            </div>
          </form>
        )}
      </div>

      <div className="partidos-distribucion">
        <form className="partidos-formulario" onSubmit={alEnviar} noValidate>
          <div className="partidos-formulario-cabecera">
            <div>
              <strong>Datos del encuentro</strong>
              <span>Los campos marcados son obligatorios.</span>
            </div>
          </div>

          {cargando ? (
            <div className="partidos-cargando" role="status">
              Cargando equipos y competiciones…
            </div>
          ) : (
            <div className="partidos-grilla">
              <Select
                etiqueta="Equipo propio *"
                value={equipoId}
                error={errores.equipo}
                disabled={Boolean(errorCarga) || sinEquipos || programar.isPending}
                onChange={(evento) => {
                  setEquipoId(evento.currentTarget.value);
                  limpiarError("equipo");
                }}
              >
                <option value="">Selecciona un equipo</option>
                {equipos.data?.map((equipo) => (
                  <option key={equipo.id} value={equipo.id}>
                    {equipo.nombre} · {equipo.categoria || "Sin categoría"}
                  </option>
                ))}
              </Select>

              <Input
                etiqueta="Rival *"
                value={rival}
                error={errores.rival}
                maxLength={120}
                placeholder="Ej. Club Atlético Central"
                disabled={programar.isPending}
                onChange={(evento) => {
                  setRival(evento.currentTarget.value);
                  limpiarError("rival");
                }}
              />

              <Select
                etiqueta="Condición *"
                value={condicion}
                disabled={programar.isPending}
                onChange={(evento) =>
                  setCondicion(evento.currentTarget.value as "LOCAL" | "VISITANTE")
                }
              >
                <option value="LOCAL">Local</option>
                <option value="VISITANTE">Visitante</option>
              </Select>

              <Select
                etiqueta="Competición"
                value={competicionId}
                ayuda="Opcional para partidos amistosos."
                disabled={Boolean(errorCarga) || programar.isPending}
                onChange={(evento) => {
                  setCompeticionId(evento.currentTarget.value);
                  setPartidoCreado(null);
                }}
              >
                <option value="">Partido amistoso · Sin competición</option>
                {competiciones.data?.map((competicion) => (
                  <option key={competicion.id} value={competicion.id}>
                    {competicion.nombre} · {competicion.temporada}
                  </option>
                ))}
              </Select>

              <Input
                etiqueta="Fecha *"
                type="date"
                min={fechaLocal()}
                value={fecha}
                error={errores.fecha}
                disabled={programar.isPending}
                onChange={(evento) => {
                  setFecha(evento.currentTarget.value);
                  limpiarError("fecha");
                }}
              />

              <Input
                etiqueta="Hora *"
                type="time"
                step={60}
                value={hora}
                error={errores.hora}
                disabled={programar.isPending}
                onChange={(evento) => {
                  setHora(evento.currentTarget.value);
                  limpiarError("hora");
                }}
              />

              <div className="partidos-columna-completa">
                <Input
                  etiqueta="Sede o cancha *"
                  value={sede}
                  error={errores.sede}
                  maxLength={160}
                  placeholder="Ej. Estadio Municipal, cancha principal"
                  ayuda="Se utilizará después para asociar la calibración de cámara de la cancha."
                  disabled={programar.isPending}
                  onChange={(evento) => {
                    setSede(evento.currentTarget.value);
                    limpiarError("sede");
                  }}
                />
              </div>
            </div>
          )}

          {sinEquipos && (
            <Alert tono="aviso" titulo="Primero registra un equipo">
              No hay equipos activos disponibles. Créalo en la pestaña Gestionar Equipos antes de
              programar el partido.
            </Alert>
          )}

          {programar.isError && (
            <Alert tono="error" titulo="No se pudo programar el partido">
              {mensajeDeError(programar.error)}
            </Alert>
          )}

          <div className="partidos-acciones">
            <Button
              type="submit"
              disabled={cargando || Boolean(errorCarga) || sinEquipos || programar.isPending}
            >
              {programar.isPending ? "Guardando…" : "Programar partido"}
            </Button>
          </div>
        </form>

        <aside className="partidos-resumen" aria-label="Resumen de programación">
          <span className="kicker">Antes de guardar</span>
          <h4>Verifica la logística</h4>
          <ol>
            <li>El equipo debe estar activo y pertenecer a tu club.</li>
            <li>La fecha y hora deben estar en el futuro.</li>
            <li>La competición es opcional para encuentros amistosos.</li>
            <li>El partido aparecerá en la agenda después de guardarlo.</li>
          </ol>
          <div className="partidos-resumen-nota">
            Administradores y directores técnicos pueden programar. Solo el administrador podrá
            reprogramar o cancelar posteriormente.
          </div>
        </aside>
      </div>
      <AgendaPartidos onVerAlineacion={onVerAlineacion} />
    </section>
  );
}
