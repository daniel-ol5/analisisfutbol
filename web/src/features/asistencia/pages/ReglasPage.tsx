/**
 * CU-54 · Catálogo de reglas (T-092). Pestaña "Reglas tácticas" de AsistenciaPage.
 *
 * Lista las reglas globales del sistema y las propias del club, y permite
 * activarlas o desactivarlas sin tocar código. Criterio de T-092: el cambio
 * surte efecto en el siguiente partido sin desplegar (en realidad, en la
 * siguiente evaluación del motor, cada 5 s). Una regla global se desactiva
 * solo para el club; las propias se pueden crear, editar y probar contra un
 * partido ya jugado.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import "@/features/asistencia/reglas.css";
import { useSesion } from "@/features/seguridad/session";
import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button, Table } from "@/shared/ui";

import { editarRegla, listarReglas } from "../api";
import { FormularioRegla } from "../components/FormularioRegla";
import { ProbarRegla } from "../components/ProbarRegla";
import {
  ETIQUETA_PRIORIDAD,
  TONO_PRIORIDAD,
  describirCondicion,
  formatoEspera,
  ordenarReglas,
  puedeGestionarReglas,
} from "../reglas";
import type { Regla } from "../types";

const CLAVE_REGLAS = ["asistencia", "reglas"] as const;

type Edicion = { modo: "nueva" } | { modo: "editar"; regla: Regla };

export function ReglasPage() {
  const sesion = useSesion();
  const puedeGestionar = puedeGestionarReglas(sesion?.usuario.rol);
  const cliente = useQueryClient();

  const [edicion, setEdicion] = useState<Edicion | null>(null);
  const [probando, setProbando] = useState<Regla | null>(null);
  const [cambiandoId, setCambiandoId] = useState<number | null>(null);

  const consulta = useQuery({ queryKey: CLAVE_REGLAS, queryFn: listarReglas });

  const activar = useMutation({
    mutationFn: ({ regla, activa }: { regla: Regla; activa: boolean }) =>
      editarRegla(regla.id, { activa }),
    onMutate: ({ regla }) => setCambiandoId(regla.id),
    onSettled: () => setCambiandoId(null),
    onSuccess: () => void cliente.invalidateQueries({ queryKey: CLAVE_REGLAS }),
  });

  const reglas = ordenarReglas(consulta.data ?? []);
  const activas = reglas.filter((r) => r.activa).length;

  return (
    <section className="reg-pagina" aria-label="Catálogo de reglas">
      <p className="reg-intro">
        Las reglas deciden qué recomendaciones recibe el cuerpo técnico durante el partido. Activar
        o desactivar una regla vale desde la próxima evaluación del motor, sin desplegar nada. Las
        reglas <strong>globales</strong> son del sistema: solo se activan o desactivan, y el cambio
        vale únicamente para tu club. Para otra variante, crea una regla propia.
      </p>

      {!puedeGestionar && (
        <p className="reg-nota" role="note">
          Solo el Administrador y el Director Técnico pueden activar, crear o probar reglas. Puedes
          ver el catálogo.
        </p>
      )}

      <div className="reg-barra">
        <p className="reg-resumen" aria-live="polite">
          {consulta.isSuccess && `${activas} activas de ${reglas.length}`}
        </p>
        {puedeGestionar && (
          <Button onClick={() => setEdicion({ modo: "nueva" })}>Nueva regla</Button>
        )}
      </div>

      {activar.isError && (
        <Alert tono="error" titulo="No se pudo cambiar la activación">
          {mensajeDeError(activar.error)}
        </Alert>
      )}

      {consulta.isError ? (
        <Alert tono="error" titulo="No se pudo cargar el catálogo">
          {mensajeDeError(consulta.error)}
        </Alert>
      ) : consulta.isLoading ? (
        <p className="reg-vacio">Cargando reglas…</p>
      ) : reglas.length === 0 ? (
        <p className="reg-vacio">El catálogo está vacío.</p>
      ) : (
        <Table titulo="Reglas del catálogo">
          <thead>
            <tr>
              <th scope="col">Regla</th>
              <th scope="col">Se dispara cuando</th>
              <th scope="col">Prioridad</th>
              <th scope="col">Espera</th>
              <th scope="col">Origen</th>
              <th scope="col">Activa</th>
              {puedeGestionar && <th scope="col">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {reglas.map((regla) => (
              <tr key={regla.id} className={regla.activa ? undefined : "reg-fila-inactiva"}>
                <td>
                  <strong>{regla.nombre}</strong>
                  <span className="reg-mensaje">{regla.plantilla_mensaje}</span>
                </td>
                <td className="reg-condicion">{describirCondicion(regla.condicion)}</td>
                <td>
                  <Badge tono={TONO_PRIORIDAD[regla.prioridad]}>
                    {ETIQUETA_PRIORIDAD[regla.prioridad]}
                  </Badge>
                </td>
                <td title="Tiempo de partido entre dos recomendaciones de esta regla">
                  {formatoEspera(regla.cooldown_s)}
                </td>
                <td>
                  {regla.club_id === null ? (
                    <Badge tono="neutro">Global</Badge>
                  ) : (
                    <Badge tono="ok">Del club</Badge>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={regla.activa}
                    aria-label={`${regla.activa ? "Desactivar" : "Activar"} ${regla.nombre}`}
                    className="reg-interruptor"
                    disabled={!puedeGestionar || cambiandoId === regla.id}
                    onClick={() => activar.mutate({ regla, activa: !regla.activa })}
                  >
                    <span className="reg-interruptor-perilla" aria-hidden="true" />
                  </button>
                </td>
                {puedeGestionar && (
                  <td className="reg-acciones">
                    <Button variante="secundario" onClick={() => setProbando(regla)}>
                      Probar
                    </Button>
                    {regla.club_id !== null && (
                      <Button
                        variante="fantasma"
                        onClick={() => setEdicion({ modo: "editar", regla })}
                      >
                        Editar
                      </Button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      {edicion && (
        <FormularioRegla
          regla={edicion.modo === "editar" ? edicion.regla : null}
          onCerrar={() => setEdicion(null)}
          onGuardada={() => {
            setEdicion(null);
            void cliente.invalidateQueries({ queryKey: CLAVE_REGLAS });
          }}
        />
      )}
      {probando && <ProbarRegla regla={probando} onCerrar={() => setProbando(null)} />}
    </section>
  );
}
