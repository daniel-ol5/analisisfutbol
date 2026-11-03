/**
 * Editor de alineación y formación  —  CU-17 · T-051 (HU-14).
 *
 * El DT o el asistente eligen la formación, pasan jugadores del plantel a
 * titulares o al banco, los acomodan en la cancha y designan al capitán. El
 * analista ve la alineación pero no la cambia (el backend tampoco lo deja).
 *
 * PROVISORIO hasta CU-15 (Susana): sin `GET /deportivo/partidos` no hay agenda
 * ni forma de saber el equipo de un partido, así que se eligen a mano el equipo
 * y el número de partido. Si el equipo no es el del partido, el backend
 * rechaza el guardado con un 422 que se muestra tal cual.
 */
import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSesion } from "@/features/seguridad";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Input, Select } from "@/shared/ui";

import { guardarAlineacion, listarEquipos, listarJugadores, obtenerAlineacion } from "../api";
import {
  TITULARES,
  alineacionVacia,
  asignar,
  cambiarFormacion,
  cantidadTitulares,
  estadoDesdeAlineacion,
  huella,
  marcarCapitan,
  mover,
  aPedido,
  problemas,
  puedeEditarAlineacion,
  reubicar,
  rolDe,
  type EstadoAlineacion,
  type RolEnAlineacion,
} from "../alineacion";
import {
  ETIQUETAS_POSICION,
  FORMACIONES,
  type Alineacion,
  type Formacion,
  type Jugador,
  type Posicion,
} from "../types";
import { CanchaTactica } from "./CanchaTactica";
import "./alineacion.css";

interface Seleccion {
  equipoId: number;
  partidoId: number;
}

export function AlineacionView() {
  const rol = useSesion()?.usuario.rol;
  const editable = puedeEditarAlineacion(rol);
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null);

  return (
    <div className="alin">
      <ElegirPartido onElegir={setSeleccion} actual={seleccion} />
      {!editable && (
        <Alert tono="info">
          Tu rol puede ver la alineación, pero solo el DT, el asistente o un administrador pueden
          cambiarla.
        </Alert>
      )}
      {seleccion && (
        <CargarAlineacion
          key={`${seleccion.equipoId}-${seleccion.partidoId}`}
          {...seleccion}
          editable={editable}
        />
      )}
    </div>
  );
}

// ---------------- Elegir equipo y partido (provisorio hasta CU-15) ----------------

function ElegirPartido({
  actual,
  onElegir,
}: {
  actual: Seleccion | null;
  onElegir: (s: Seleccion) => void;
}) {
  const { data: equipos = [], isLoading } = useQuery({
    queryKey: ["equipos", { activos: true }],
    queryFn: () => listarEquipos(true),
    retry: 1,
  });
  const [equipoElegido, setEquipoId] = useState<number | null>(actual?.equipoId ?? null);
  // Mientras no se elija uno, el primer equipo del club.
  const equipoId = equipoElegido ?? equipos[0]?.id ?? null;
  const [numero, setNumero] = useState(actual ? String(actual.partidoId) : "");
  const [error, setError] = useState<string | undefined>();

  const enviar = (e: FormEvent) => {
    e.preventDefault();
    const partidoId = Number(numero.trim());
    if (!Number.isInteger(partidoId) || partidoId < 1) {
      setError("Escribe un número de partido válido.");
      return;
    }
    if (equipoId === null) return;
    setError(undefined);
    onElegir({ equipoId, partidoId });
  };

  return (
    <form className="alin-elegir" onSubmit={enviar}>
      <Select
        etiqueta="Equipo del partido"
        value={equipoId ?? ""}
        onChange={(e) => setEquipoId(Number(e.target.value))}
        disabled={isLoading || equipos.length === 0}
      >
        {equipos.length === 0 && (
          <option value="">{isLoading ? "Cargando…" : "Sin equipos"}</option>
        )}
        {equipos.map((eq) => (
          <option key={eq.id} value={eq.id}>
            {eq.nombre}
            {eq.categoria ? ` · ${eq.categoria}` : ""}
          </option>
        ))}
      </Select>
      <Input
        etiqueta="Número de partido"
        inputMode="numeric"
        value={numero}
        onChange={(e) => setNumero(e.target.value)}
        error={error}
        ayuda="Provisorio: la agenda de partidos (CU-15) todavía no está disponible."
      />
      <Button type="submit" disabled={equipoId === null}>
        Abrir alineación
      </Button>
    </form>
  );
}

// ---------------- Carga de plantel + alineación ----------------

function CargarAlineacion({ equipoId, partidoId, editable }: Seleccion & { editable: boolean }) {
  const plantel = useQuery({
    queryKey: ["jugadores", equipoId, { activos: true, orden: "dorsal" }],
    queryFn: () => listarJugadores(equipoId, true, "dorsal"),
    retry: 1,
  });
  const alineacion = useQuery({
    queryKey: ["alineacion", partidoId],
    queryFn: () => obtenerAlineacion(partidoId),
    retry: false,
  });

  if (plantel.isLoading || alineacion.isLoading) {
    return <p className="alin-cargando">Cargando plantel y alineación…</p>;
  }
  if (plantel.isError || alineacion.isError) {
    const error = plantel.error ?? alineacion.error;
    return (
      <Alert tono="error" titulo={`No se pudo abrir el partido ${partidoId}`}>
        {mensajeDeError(error)}
      </Alert>
    );
  }
  return (
    <Editor
      partidoId={partidoId}
      plantel={plantel.data ?? []}
      guardada={alineacion.data ?? null}
      editable={editable}
    />
  );
}

// ---------------- Editor ----------------

const ORDEN_POSICION: Record<Posicion, number> = { ARQ: 0, DEF: 1, MED: 2, DEL: 3 };

function Editor({
  partidoId,
  plantel,
  guardada,
  editable,
}: {
  partidoId: number;
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

  const porId = useMemo(() => new Map(plantel.map((j) => [j.id, j])), [plantel]);
  const lista = problemas(estado, plantel);
  const hayCambios = huella(estado) !== huellaGuardada;
  const titulares = cantidadTitulares(estado);

  const guardar = useMutation({
    mutationFn: () => guardarAlineacion(partidoId, aPedido(estado)),
    onSuccess: (respuesta) => {
      queryClient.setQueryData(["alineacion", partidoId], respuesta);
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
    <section className="alin-editor" aria-label={`Alineación del partido ${partidoId}`}>
      <div className="alin-barra">
        <div className="alin-barra-titulo">
          <h3>Partido {partidoId}</h3>
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
            onMover={(id, x, y) => cambiar(mover(estado, id, x, y))}
          />
          {editable && (
            <div className="alin-cancha-acciones">
              <span>
                Arrastra las fichas para ajustar la posición, o usa las flechas del teclado.
              </span>
              <Button variante="fantasma" onClick={() => cambiar(reubicar(estado))}>
                Reubicar según la formación
              </Button>
            </div>
          )}
        </div>

        <div className="alin-plantel">
          <GrupoJugadores
            titulo={`Titulares (${titulares}/${TITULARES})`}
            jugadores={grupos.titular}
            estado={estado}
            editable={editable}
            onCambiar={cambiar}
            vacio="Pasa jugadores del plantel a titulares."
          />
          <GrupoJugadores
            titulo={`Suplentes (${grupos.suplente.length})`}
            jugadores={grupos.suplente}
            estado={estado}
            editable={editable}
            onCambiar={cambiar}
            vacio="Sin suplentes convocados."
          />
          <GrupoJugadores
            titulo={`No convocados (${grupos.fuera.length})`}
            jugadores={grupos.fuera}
            estado={estado}
            editable={editable}
            onCambiar={cambiar}
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
  onCambiar,
  vacio,
}: {
  titulo: string;
  jugadores: Jugador[];
  estado: EstadoAlineacion;
  editable: boolean;
  onCambiar: (e: EstadoAlineacion) => void;
  vacio: string;
}) {
  const completo = cantidadTitulares(estado) >= TITULARES;
  return (
    <div className="alin-grupo">
      <h4>{titulo}</h4>
      {jugadores.length === 0 && <p className="alin-vacio">{vacio}</p>}
      <ul>
        {jugadores.map((j) => {
          const actual = rolDe(estado, j.id);
          const capitan = estado.capitanId === j.id;
          return (
            <li key={j.id} className="alin-jugador">
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
                  {ACCIONES.filter((a) => a.destino !== actual).map((a) => {
                    const sinLugar = a.destino === "titular" && completo;
                    return (
                      <button
                        key={a.destino}
                        type="button"
                        disabled={sinLugar}
                        title={sinLugar ? `Ya hay ${TITULARES} titulares` : undefined}
                        onClick={() => onCambiar(asignar(estado, j, a.destino))}
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
