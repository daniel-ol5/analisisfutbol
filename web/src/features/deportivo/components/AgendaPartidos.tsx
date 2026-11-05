import { useMemo, useState } from "react";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Input, Select } from "@/shared/ui";
import type { TonoBadge } from "@/shared/ui/Badge";

import { useCompeticiones, useEquiposAgenda, usePartidos } from "../hooks";
import type { EstadoPartido, FiltrosPartidos, Partido } from "../types";
import "./agenda-partidos.css";

const ESTADOS: Array<{ valor: EstadoPartido; etiqueta: string }> = [
  { valor: "PROGRAMADO", etiqueta: "Programado" },
  { valor: "EN_CURSO", etiqueta: "En curso" },
  { valor: "FINALIZADO", etiqueta: "Finalizado" },
  { valor: "PROCESANDO", etiqueta: "Procesando" },
  { valor: "ANALIZADO", etiqueta: "Analizado" },
  { valor: "CANCELADO", etiqueta: "Cancelado" },
];

const ETIQUETA_ESTADO = Object.fromEntries(
  ESTADOS.map(({ valor, etiqueta }) => [valor, etiqueta]),
) as Record<EstadoPartido, string>;

const TONO_ESTADO: Record<EstadoPartido, TonoBadge> = {
  PROGRAMADO: "info",
  EN_CURSO: "error",
  FINALIZADO: "neutro",
  PROCESANDO: "aviso",
  ANALIZADO: "ok",
  CANCELADO: "error",
};

function fechaPartido(valor: string) {
  const fecha = new Date(valor);
  return {
    dia: new Intl.DateTimeFormat("es-BO", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(fecha),
    hora: new Intl.DateTimeFormat("es-BO", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(fecha),
  };
}

function Marcador({ partido }: { partido: Partido }) {
  if (
    !(["EN_CURSO", "FINALIZADO", "PROCESANDO", "ANALIZADO"] as EstadoPartido[]).includes(
      partido.estado,
    )
  ) {
    return null;
  }
  return (
    <strong
      className="agenda-marcador"
      aria-label={`Marcador ${partido.goles_favor} a ${partido.goles_contra}`}
    >
      {partido.goles_favor} – {partido.goles_contra}
    </strong>
  );
}

export function AgendaPartidos() {
  const [equipoId, setEquipoId] = useState("");
  const [competicionId, setCompeticionId] = useState("");
  const [estado, setEstado] = useState<EstadoPartido | "">("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  const rangoInvalido = Boolean(desde && hasta && desde > hasta);
  const filtros = useMemo<FiltrosPartidos>(
    () => ({
      ...(equipoId ? { equipo_id: Number(equipoId) } : {}),
      ...(competicionId ? { competicion_id: Number(competicionId) } : {}),
      ...(estado ? { estado } : {}),
      ...(desde ? { desde } : {}),
      ...(hasta ? { hasta } : {}),
    }),
    [competicionId, desde, equipoId, estado, hasta],
  );

  const equipos = useEquiposAgenda();
  const competiciones = useCompeticiones();
  const partidos = usePartidos(filtros, !rangoInvalido);

  const nombresEquipo = useMemo(
    () => new Map(equipos.data?.map((equipo) => [equipo.id, equipo.nombre]) ?? []),
    [equipos.data],
  );
  const nombresCompeticion = useMemo(
    () =>
      new Map(
        competiciones.data?.map((competicion) => [
          competicion.id,
          `${competicion.nombre} · ${competicion.temporada}`,
        ]) ?? [],
      ),
    [competiciones.data],
  );

  const agenda = useMemo(
    () =>
      [...(partidos.data ?? [])].sort(
        (primero, segundo) =>
          new Date(primero.fecha_hora).getTime() - new Date(segundo.fecha_hora).getTime(),
      ),
    [partidos.data],
  );

  const limpiarFiltros = () => {
    setEquipoId("");
    setCompeticionId("");
    setEstado("");
    setDesde("");
    setHasta("");
  };

  const hayFiltros = Boolean(equipoId || competicionId || estado || desde || hasta);
  const errorCarga = partidos.error ?? equipos.error ?? competiciones.error;

  return (
    <section className="agenda" aria-labelledby="agenda-titulo">
      <header className="agenda-cabecera">
        <div>
          <span className="kicker">CU-15 · AGENDA DE PARTIDOS</span>
          <h3 id="agenda-titulo">Calendario del club</h3>
          <p>Consulta los encuentros del club y acota los resultados con los filtros.</p>
        </div>
        <Button
          variante="secundario"
          disabled={partidos.isFetching || rangoInvalido}
          onClick={() => void partidos.refetch()}
        >
          {partidos.isFetching ? "Actualizando…" : "Actualizar agenda"}
        </Button>
      </header>

      <div className="agenda-filtros" aria-label="Filtros de la agenda">
        <Select
          etiqueta="Equipo"
          value={equipoId}
          onChange={(e) => setEquipoId(e.currentTarget.value)}
        >
          <option value="">Todos los equipos</option>
          {equipos.data?.map((equipo) => (
            <option key={equipo.id} value={equipo.id}>
              {equipo.nombre}
              {equipo.activo ? "" : " · Inactivo"}
            </option>
          ))}
        </Select>

        <Select
          etiqueta="Competición"
          value={competicionId}
          onChange={(e) => setCompeticionId(e.currentTarget.value)}
        >
          <option value="">Todas las competiciones</option>
          {competiciones.data?.map((competicion) => (
            <option key={competicion.id} value={competicion.id}>
              {competicion.nombre} · {competicion.temporada}
            </option>
          ))}
        </Select>

        <Select
          etiqueta="Estado"
          value={estado}
          onChange={(e) => setEstado(e.currentTarget.value as EstadoPartido | "")}
        >
          <option value="">Todos los estados</option>
          {ESTADOS.map((opcion) => (
            <option key={opcion.valor} value={opcion.valor}>
              {opcion.etiqueta}
            </option>
          ))}
        </Select>

        <Input
          etiqueta="Desde"
          type="date"
          value={desde}
          onChange={(e) => setDesde(e.currentTarget.value)}
        />
        <Input
          etiqueta="Hasta"
          type="date"
          value={hasta}
          min={desde || undefined}
          error={rangoInvalido ? "Debe ser igual o posterior a la fecha desde." : undefined}
          onChange={(e) => setHasta(e.currentTarget.value)}
        />

        <div className="agenda-filtros-accion">
          <Button variante="fantasma" disabled={!hayFiltros} onClick={limpiarFiltros}>
            Limpiar filtros
          </Button>
        </div>
      </div>

      {errorCarga && (
        <Alert tono="error" titulo="No se pudo cargar la agenda">
          <p>{mensajeDeError(errorCarga)}</p>
          <Button
            variante="secundario"
            onClick={() => {
              void equipos.refetch();
              void competiciones.refetch();
              if (!rangoInvalido) void partidos.refetch();
            }}
          >
            Reintentar
          </Button>
        </Alert>
      )}

      {partidos.isLoading && !rangoInvalido && (
        <div className="agenda-estado" role="status">
          Cargando partidos…
        </div>
      )}

      {!errorCarga && !partidos.isLoading && !rangoInvalido && agenda.length === 0 && (
        <div className="agenda-vacia">
          <strong>
            {hayFiltros ? "No hay partidos que coincidan" : "Todavía no hay partidos"}
          </strong>
          <p>
            {hayFiltros
              ? "Prueba quitando alguno de los filtros de la agenda."
              : "Cuando se programe el primer encuentro aparecerá aquí."}
          </p>
        </div>
      )}

      {!errorCarga && !rangoInvalido && agenda.length > 0 && (
        <div className="agenda-resultados">
          <div className="agenda-resultados-cabecera">
            <strong>
              {agenda.length} {agenda.length === 1 ? "partido" : "partidos"}
            </strong>
            {partidos.isFetching && !partidos.isLoading && <span>Actualizando…</span>}
          </div>

          <div className="agenda-lista">
            {agenda.map((partido) => {
              const fecha = fechaPartido(partido.fecha_hora);
              const equipo = nombresEquipo.get(partido.equipo_id) ?? `Equipo #${partido.equipo_id}`;
              const local = partido.es_local ? equipo : partido.rival;
              const visitante = partido.es_local ? partido.rival : equipo;

              return (
                <article
                  key={partido.id}
                  className={`agenda-partido${partido.estado === "EN_CURSO" ? " agenda-partido--en-curso" : ""}`}
                >
                  <div className="agenda-fecha">
                    <span>{fecha.dia}</span>
                    <strong>{fecha.hora}</strong>
                  </div>

                  <div className="agenda-encuentro">
                    <div className="agenda-encuentro-superior">
                      <Badge tono={TONO_ESTADO[partido.estado]}>
                        {ETIQUETA_ESTADO[partido.estado]}
                      </Badge>
                      <span>
                        {partido.competicion_id
                          ? (nombresCompeticion.get(partido.competicion_id) ??
                            `Competición #${partido.competicion_id}`)
                          : "Amistoso"}
                      </span>
                    </div>
                    <div className="agenda-equipos">
                      <strong>{local}</strong>
                      <span>vs.</span>
                      <strong>{visitante}</strong>
                      <Marcador partido={partido} />
                    </div>
                    <div className="agenda-detalle">
                      <span>{partido.sede}</span>
                      <span>
                        {partido.es_local
                          ? "Nuestro equipo es local"
                          : "Nuestro equipo es visitante"}
                      </span>
                    </div>
                  </div>

                  {partido.estado === "EN_CURSO" && (
                    <div className="agenda-en-vivo" aria-label="Partido en curso">
                      <span aria-hidden="true" /> EN VIVO
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
