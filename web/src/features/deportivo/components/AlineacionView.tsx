/**
 * Editor de alineación y formación  —  CU-17 · T-051 (HU-14).
 *
 * El DT o el asistente eligen un partido de la agenda (CU-15), la formación,
 * pasan jugadores del plantel a titulares o al banco, los acomodan en la cancha
 * y designan al capitán. El plantel es el del equipo del partido.
 *
 * Solo se edita con rol ADMIN, DT o ASISTENTE y con el partido PROGRAMADO o
 * EN_CURSO, igual que en el backend; en otro caso la alineación es de consulta.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSesion } from "@/features/seguridad";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Select } from "@/shared/ui";

import { guardarAlineacion, listarJugadores, obtenerAlineacion } from "../api";
import {
  PUESTOS,
  TITULARES,
  alineacionVacia,
  asignar,
  cambiarFormacion,
  cantidadTitulares,
  colocarEnPuesto,
  estadoDesdeAlineacion,
  huella,
  marcarCapitan,
  mover,
  aPedido,
  nombrePartido,
  partidoEditable,
  problemas,
  puedeEditarAlineacion,
  reubicar,
  rolDe,
  soltarEnCancha,
  type EstadoAlineacion,
  type RolEnAlineacion,
} from "../alineacion";
import { useEquiposAgenda, usePartidos } from "../hooks";
import {
  ETIQUETAS_POSICION,
  FORMACIONES,
  type Alineacion,
  type Formacion,
  type Jugador,
  type Partido,
  type Posicion,
} from "../types";
import { CanchaTactica, MIME_JUGADOR_ALINEACION } from "./CanchaTactica";
import "./alineacion.css";

const SIN_FILTROS = {};

export function AlineacionView({ partidoInicialId = null }: { partidoInicialId?: number | null }) {
  const rol = useSesion()?.usuario.rol;
  const puedeEditar = puedeEditarAlineacion(rol);

  const partidos = usePartidos(SIN_FILTROS);
  const equipos = useEquiposAgenda();
  const [elegido, setElegido] = useState<number | null>(partidoInicialId);

  const lista = useMemo(() => partidos.data ?? [], [partidos.data]);
  const grupos = useMemo(() => {
    const porFecha = (a: Partido, b: Partido) =>
      new Date(a.fecha_hora).getTime() - new Date(b.fecha_hora).getTime();
    return {
      proximos: lista.filter(partidoEditable).sort(porFecha),
      jugados: lista.filter((p) => !partidoEditable(p)).sort((a, b) => porFecha(b, a)),
    };
  }, [lista]);
  // Sin elección, el próximo partido; si no hay, el último jugado.
  const partidoId = elegido ?? grupos.proximos[0]?.id ?? grupos.jugados[0]?.id ?? null;
  const partido = lista.find((p) => p.id === partidoId) ?? null;

  const nombresEquipo = useMemo(
    () => new Map(equipos.data?.map((e) => [e.id, e.nombre]) ?? []),
    [equipos.data],
  );
  const conEquipo = (p: Partido) =>
    nombresEquipo.size > 1 ? ` · ${nombresEquipo.get(p.equipo_id) ?? ""}` : "";

  if (partidos.isLoading) return <p className="alin-cargando">Cargando partidos…</p>;
  if (partidos.isError) {
    return (
      <Alert tono="error" titulo="No se pudo cargar la agenda de partidos">
        {mensajeDeError(partidos.error)}
      </Alert>
    );
  }
  if (lista.length === 0) {
    return (
      <Alert tono="info" titulo="Todavía no hay partidos">
        Programa un partido en la pestaña «Competiciones y Calendario» para armar su alineación.
      </Alert>
    );
  }

  const editable = puedeEditar && partido !== null && partidoEditable(partido);

  return (
    <div className="alin">
      <div className="alin-elegir">
        <Select
          etiqueta="Partido"
          value={partidoId ?? ""}
          onChange={(e) => setElegido(Number(e.currentTarget.value))}
        >
          {grupos.proximos.length > 0 && (
            <optgroup label="Próximos">
              {grupos.proximos.map((p) => (
                <option key={p.id} value={p.id}>
                  {nombrePartido(p)}
                  {conEquipo(p)}
                  {p.estado === "EN_CURSO" ? " · En curso" : ""}
                </option>
              ))}
            </optgroup>
          )}
          {grupos.jugados.length > 0 && (
            <optgroup label="Jugados y cancelados">
              {grupos.jugados.map((p) => (
                <option key={p.id} value={p.id}>
                  {nombrePartido(p)}
                  {conEquipo(p)}
                  {p.estado === "CANCELADO" ? " · Cancelado" : ""}
                </option>
              ))}
            </optgroup>
          )}
        </Select>
      </div>

      {!puedeEditar && (
        <Alert tono="info">
          Tu rol puede ver la alineación, pero solo el DT, el asistente o un administrador pueden
          cambiarla.
        </Alert>
      )}
      {puedeEditar && partido !== null && !partidoEditable(partido) && (
        <Alert tono="info">
          Este partido ya no está programado ni en curso: su alineación queda solo para consulta.
        </Alert>
      )}

      {partido && <CargarAlineacion key={partido.id} partido={partido} editable={editable} />}
    </div>
  );
}

// ---------------- Carga de plantel + alineación ----------------

function CargarAlineacion({ partido, editable }: { partido: Partido; editable: boolean }) {
  const plantel = useQuery({
    queryKey: ["jugadores", partido.equipo_id, { activos: true, orden: "dorsal" }],
    queryFn: () => listarJugadores(partido.equipo_id, true, "dorsal"),
    retry: 1,
  });
  const alineacion = useQuery({
    queryKey: ["alineacion", partido.id],
    queryFn: () => obtenerAlineacion(partido.id),
    retry: false,
  });

  if (plantel.isLoading || alineacion.isLoading) {
    return <p className="alin-cargando">Cargando plantel y alineación…</p>;
  }
  if (plantel.isError || alineacion.isError) {
    const error = plantel.error ?? alineacion.error;
    return (
      <Alert tono="error" titulo="No se pudo abrir la alineación">
        {mensajeDeError(error)}
      </Alert>
    );
  }
  if (!editable && alineacion.data === null) {
    return <Alert tono="info">Este partido no tiene alineación guardada.</Alert>;
  }
  return (
    <Editor
      partido={partido}
      plantel={plantel.data ?? []}
      guardada={alineacion.data ?? null}
      editable={editable}
    />
  );
}

// ---------------- Editor ----------------

const ORDEN_POSICION: Record<Posicion, number> = { ARQ: 0, DEF: 1, MED: 2, DEL: 3 };

function Editor({
  partido,
  plantel,
  guardada,
  editable,
}: {
  partido: Partido;
  plantel: Jugador[];
  guardada: Alineacion | null;
  editable: boolean;
}) {
  const queryClient = useQueryClient();
  const inicial = useMemo(
    () =>
      guardada
        ? estadoDesdeAlineacion(guardada, plantel)
        : { estado: alineacionVacia(), descartados: [] },
    [guardada, plantel],
  );
  const [estado, setEstado] = useState<EstadoAlineacion>(inicial.estado);
  const [huellaGuardada, setHuellaGuardada] = useState(() =>
    guardada ? huella(inicial.estado) : null,
  );
  const [exito, setExito] = useState(false);
  const [puestoSeleccionado, setPuestoSeleccionado] = useState<number | null>(null);

  const porId = useMemo(() => new Map(plantel.map((j) => [j.id, j])), [plantel]);
  const lista = problemas(estado, plantel);
  const hayCambios = huella(estado) !== huellaGuardada;
  const titulares = cantidadTitulares(estado);

  const guardar = useMutation({
    mutationFn: () => guardarAlineacion(partido.id, aPedido(estado)),
    onSuccess: (respuesta) => {
      queryClient.setQueryData(["alineacion", partido.id], respuesta);
      setHuellaGuardada(huella(estado));
      setExito(true);
    },
  });

  const cambiar = (siguiente: EstadoAlineacion) => {
    setEstado(siguiente);
    setExito(false);
  };

  const grupos = useMemo(() => {
    const ordenados = [...plantel].sort(
      (a, b) => ORDEN_POSICION[a.posicion] - ORDEN_POSICION[b.posicion] || a.dorsal - b.dorsal,
    );
    const de = (r: RolEnAlineacion) => ordenados.filter((j) => rolDe(estado, j.id) === r);
    return { titular: de("titular"), suplente: de("suplente"), fuera: de("fuera") };
  }, [plantel, estado]);

  return (
    <section className="alin-editor" aria-label={`Alineación ${nombrePartido(partido)}`}>
      <div className="alin-barra">
        <div className="alin-barra-titulo">
          <h3>{nombrePartido(partido)}</h3>
          {guardada === null && huellaGuardada === null && (
            <Badge tono="info">Sin alineación guardada</Badge>
          )}
          {hayCambios && huellaGuardada !== null && <Badge tono="aviso">Cambios sin guardar</Badge>}
          {!hayCambios && <Badge tono="ok">Guardada</Badge>}
        </div>
        <div className="alin-formaciones" role="radiogroup" aria-label="Formación">
          {FORMACIONES.map((f: Formacion) => (
            <button
              key={f}
              type="button"
              role="radio"
              aria-checked={estado.formacion === f}
              className={
                estado.formacion === f ? "alin-formacion alin-formacion--activa" : "alin-formacion"
              }
              disabled={!editable}
              onClick={() => cambiar(cambiarFormacion(estado, f))}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {inicial.descartados.length > 0 && (
        <Alert tono="aviso" titulo="Jugadores que ya no están en este plantel">
          La alineación guardada incluía a{" "}
          {inicial.descartados.map((j) => `${j.dorsal} ${j.apellido}`).join(", ")}, que no están en
          el plantel activo de este equipo. Se quitaron del editor. Si elegiste otro equipo, vuelve
          a abrir el partido con el equipo correcto.
        </Alert>
      )}

      <div className="alin-cuerpo">
        <div className="alin-cancha-col">
          <CanchaTactica
            estado={estado}
            plantel={porId}
            editable={editable}
            puestoSeleccionado={puestoSeleccionado}
            onSeleccionarPuesto={setPuestoSeleccionado}
            onMover={(id, x, y) => cambiar(mover(estado, id, x, y))}
            onSoltarJugador={(id, x, y) => {
              cambiar(soltarEnCancha(estado, id, x, y));
              setPuestoSeleccionado(null);
            }}
            onColocarEnPuesto={(id, indice) => {
              cambiar(colocarEnPuesto(estado, id, indice));
              setPuestoSeleccionado(null);
            }}
          />
          {editable && (
            <div className="alin-cancha-acciones">
              <span>
                Arrastra cualquier jugador del plantel directamente al puesto deseado en la cancha,
                o haz clic en un círculo punteado para elegir ese puesto.
              </span>
              <Button
                variante="fantasma"
                onClick={() => {
                  cambiar(reubicar(estado));
                  setPuestoSeleccionado(null);
                }}
              >
                Reubicar según la formación
              </Button>
            </div>
          )}
        </div>

        <div className="alin-plantel">
          {editable && puestoSeleccionado !== null && (
            <div className="alin-puesto-aviso">
              <span>
                Elegir jugador para puesto{" "}
                <strong>{PUESTOS[estado.formacion][puestoSeleccionado]?.rol}</strong>
              </span>
              <button type="button" onClick={() => setPuestoSeleccionado(null)}>
                Cancelar
              </button>
            </div>
          )}
          <GrupoJugadores
            titulo={`Titulares (${titulares}/${TITULARES})`}
            jugadores={grupos.titular}
            estado={estado}
            editable={editable}
            puestoSeleccionado={puestoSeleccionado}
            onCambiar={(sig) => {
              cambiar(sig);
              setPuestoSeleccionado(null);
            }}
            vacio="Arrastra jugadores a la cancha o pulsa Titular."
          />
          <GrupoJugadores
            titulo={`Suplentes (${grupos.suplente.length})`}
            jugadores={grupos.suplente}
            estado={estado}
            editable={editable}
            puestoSeleccionado={puestoSeleccionado}
            onCambiar={(sig) => {
              cambiar(sig);
              setPuestoSeleccionado(null);
            }}
            vacio="Sin suplentes convocados."
          />
          <GrupoJugadores
            titulo={`No convocados (${grupos.fuera.length})`}
            jugadores={grupos.fuera}
            estado={estado}
            editable={editable}
            puestoSeleccionado={puestoSeleccionado}
            onCambiar={(sig) => {
              cambiar(sig);
              setPuestoSeleccionado(null);
            }}
            vacio={
              plantel.length === 0
                ? "El equipo no tiene jugadores activos."
                : "Todo el plantel está convocado."
            }
          />
        </div>
      </div>

      {editable && (
        <div className="alin-guardar">
          {lista.length > 0 && (
            <Alert tono="aviso" titulo="Antes de guardar">
              <ul className="alin-problemas">
                {lista.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </Alert>
          )}
          {guardar.isError && (
            <Alert tono="error" titulo="No se pudo guardar">
              {mensajeDeError(guardar.error)}
            </Alert>
          )}
          {exito && <Alert tono="ok">Alineación guardada.</Alert>}
          <Button
            onClick={() => guardar.mutate()}
            disabled={lista.length > 0 || !hayCambios || guardar.isPending}
          >
            {guardar.isPending ? "Guardando…" : "Guardar alineación"}
          </Button>
        </div>
      )}
    </section>
  );
}

const ACCIONES: { destino: RolEnAlineacion; texto: string }[] = [
  { destino: "titular", texto: "Titular" },
  { destino: "suplente", texto: "Suplente" },
  { destino: "fuera", texto: "Fuera" },
];

function GrupoJugadores({
  titulo,
  jugadores,
  estado,
  editable,
  puestoSeleccionado = null,
  onCambiar,
  vacio,
}: {
  titulo: string;
  jugadores: Jugador[];
  estado: EstadoAlineacion;
  editable: boolean;
  puestoSeleccionado?: number | null;
  onCambiar: (e: EstadoAlineacion) => void;
  vacio: string;
}) {
  const completo = cantidadTitulares(estado) >= TITULARES && puestoSeleccionado === null;
  return (
    <div className="alin-grupo">
      <h4>{titulo}</h4>
      {jugadores.length === 0 && <p className="alin-vacio">{vacio}</p>}
      <ul>
        {jugadores.map((j) => {
          const actual = rolDe(estado, j.id);
          const capitan = estado.capitanId === j.id;
          return (
            <li
              key={j.id}
              className={editable ? "alin-jugador alin-jugador--arrastrable" : "alin-jugador"}
              draggable={editable}
              onDragStart={(e) => {
                if (!editable) return;
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData(MIME_JUGADOR_ALINEACION, String(j.id));
                e.dataTransfer.setData("text/plain", String(j.id));
              }}
              title={
                editable
                  ? "Arrastra a este jugador hacia un puesto de la cancha"
                  : undefined
              }
            >
              <span
                className={
                  j.posicion === "ARQ" ? "alin-dorsal alin-dorsal--arquero" : "alin-dorsal"
                }
              >
                {j.dorsal}
              </span>
              <span className="alin-jugador-nombre">
                {j.nombre} {j.apellido}
                <small>{ETIQUETAS_POSICION[j.posicion]}</small>
              </span>
              {actual === "titular" && (
                <button
                  type="button"
                  className={capitan ? "alin-capitan alin-capitan--activo" : "alin-capitan"}
                  aria-pressed={capitan}
                  disabled={!editable}
                  title={capitan ? "Capitán" : "Designar capitán"}
                  aria-label={`${capitan ? "Capitán" : "Designar capitán"}: ${j.apellido}`}
                  onClick={() => onCambiar(marcarCapitan(estado, j.id))}
                >
                  C
                </button>
              )}
              {editable && (
                <span className="alin-acciones" role="group" aria-label={`Rol de ${j.apellido}`}>
                  {ACCIONES.filter(
                    (a) =>
                      a.destino !== actual ||
                      (a.destino === "titular" && puestoSeleccionado !== null),
                  ).map((a) => {
                    const sinLugar = a.destino === "titular" && completo;
                    return (
                      <button
                        key={a.destino}
                        type="button"
                        disabled={sinLugar}
                        title={sinLugar ? `Ya hay ${TITULARES} titulares` : undefined}
                        onClick={() =>
                          onCambiar(
                            asignar(
                              estado,
                              j,
                              a.destino,
                              a.destino === "titular" ? puestoSeleccionado : null,
                            ),
                          )
                        }
                      >
                        {a.texto}
                      </button>
                    );
                  })}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
