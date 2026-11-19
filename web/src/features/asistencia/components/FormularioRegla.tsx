/**
 * CU-54 · Crear o editar una regla propia del club (T-092).
 *
 * La condición se arma como lista de comparaciones "métrica operador número"
 * unidas por "todas" (y) o "alguna" (o). Una regla con grupos anidados se
 * edita como JSON. Las métricas de las plantillas las valida el backend (422).
 */
import { useMutation } from "@tanstack/react-query";
import { useId, useState, type SubmitEvent } from "react";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Button, Input, Modal, Select } from "@/shared/ui";

import { crearRegla, editarRegla } from "../api";
import {
  COMPARACION_VACIA,
  ETIQUETA_PRIORIDAD,
  FORMULARIO_NUEVO,
  METRICAS,
  OPERADORES,
  PRIORIDADES,
  formularioDesdeRegla,
  validarFormulario,
  type Comparacion,
  type ErroresFormulario,
  type FormularioRegla as Formulario,
  type Metrica,
  type Operador,
} from "../reglas";
import type { Prioridad, Regla, ReglaCrear } from "../types";

const METRICAS_ORDENADAS = Object.entries(METRICAS) as [Metrica, { etiqueta: string }][];

// Clave estable de cada comparación (el índice cambia al quitar una del medio).
let ultimaClave = 0;
const nuevaClave = () => ++ultimaClave;

export function FormularioRegla({
  regla,
  onCerrar,
  onGuardada,
}: Readonly<{
  /** null: regla nueva. */
  regla: Regla | null;
  onCerrar: () => void;
  onGuardada: () => void;
}>) {
  const [form, setForm] = useState<Formulario>(() =>
    regla ? formularioDesdeRegla(regla) : FORMULARIO_NUEVO,
  );
  const [errores, setErrores] = useState<ErroresFormulario>({});
  const [claves, setClaves] = useState<number[]>(() =>
    (form.condicion?.comparaciones ?? []).map(nuevaClave),
  );
  const idUnion = useId();
  const idJson = useId();
  const idMensaje = useId();
  const idJustificacion = useId();
  const idFormulario = useId();

  const guardar = useMutation({
    // Una regla nueva nace activa; al editar, la activación no se toca.
    mutationFn: (datos: Omit<ReglaCrear, "activa">) =>
      regla ? editarRegla(regla.id, datos) : crearRegla({ ...datos, activa: true }),
    onSuccess: onGuardada,
  });

  const cambiar = <K extends keyof Formulario>(campo: K, valor: Formulario[K]) =>
    setForm((f) => ({ ...f, [campo]: valor }));

  const cambiarComparacion = (indice: number, cambio: Partial<Comparacion>) =>
    setForm((f) =>
      f.condicion
        ? {
            ...f,
            condicion: {
              ...f.condicion,
              comparaciones: f.condicion.comparaciones.map((c, i) =>
                i === indice ? { ...c, ...cambio } : c,
              ),
            },
          }
        : f,
    );

  function enviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const resultado = validarFormulario(form);
    if (!resultado.ok) {
      setErrores(resultado.errores);
      return;
    }
    setErrores({});
    guardar.mutate(resultado.datos);
  }

  const condicion = form.condicion;

  return (
    <Modal
      abierto
      titulo={regla ? `Editar "${regla.nombre}"` : "Nueva regla del club"}
      onCerrar={onCerrar}
      acciones={
        <>
          <Button variante="fantasma" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button type="submit" form={idFormulario} disabled={guardar.isPending}>
            {guardar.isPending ? "Guardando…" : "Guardar regla"}
          </Button>
        </>
      }
    >
      <form id={idFormulario} className="reg-form" onSubmit={enviar} noValidate>
        <Input
          etiqueta="Nombre"
          value={form.nombre}
          maxLength={120}
          error={errores.nombre}
          onChange={(e) => cambiar("nombre", e.target.value)}
        />

        <div className="reg-form-fila">
          <Select
            etiqueta="Prioridad"
            value={form.prioridad}
            onChange={(e) => cambiar("prioridad", e.target.value as Prioridad)}
          >
            {PRIORIDADES.map((p) => (
              <option key={p} value={p}>
                {ETIQUETA_PRIORIDAD[p]}
              </option>
            ))}
          </Select>
          <Input
            etiqueta="Espera entre avisos (min)"
            inputMode="decimal"
            value={form.espera_min}
            error={errores.espera_min}
            ayuda="Tiempo de partido antes de que la misma regla vuelva a avisar."
            onChange={(e) => cambiar("espera_min", e.target.value)}
          />
        </div>

        <fieldset className="reg-condicion-campo">
          <legend>Se dispara cuando</legend>
          {condicion ? (
            <>
              <label htmlFor={idUnion} className="reg-union">
                <span>Se cumplen</span>
                <select
                  id={idUnion}
                  className="ui-control"
                  value={condicion.union}
                  onChange={(e) =>
                    cambiar("condicion", { ...condicion, union: e.target.value as "y" | "o" })
                  }
                >
                  <option value="y">todas</option>
                  <option value="o">alguna</option>
                </select>
                <span>de estas condiciones:</span>
              </label>
              <ul className="reg-comparaciones">
                {condicion.comparaciones.map((c, i) => (
                  <li key={claves[i]} className="reg-comparacion">
                    <select
                      aria-label={`Métrica de la condición ${i + 1}`}
                      className="ui-control"
                      value={c.metrica}
                      onChange={(e) =>
                        cambiarComparacion(i, { metrica: e.target.value as Metrica })
                      }
                    >
                      {METRICAS_ORDENADAS.map(([clave, { etiqueta }]) => (
                        <option key={clave} value={clave}>
                          {etiqueta}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label={`Comparación de la condición ${i + 1}`}
                      className="ui-control reg-operador"
                      value={c.operador}
                      onChange={(e) =>
                        cambiarComparacion(i, { operador: e.target.value as Operador })
                      }
                    >
                      {OPERADORES.map((op) => (
                        <option key={op} value={op}>
                          {op}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label={`Valor de la condición ${i + 1}`}
                      className="ui-control reg-valor"
                      inputMode="decimal"
                      value={c.valor}
                      onChange={(e) => cambiarComparacion(i, { valor: e.target.value })}
                    />
                    <Button
                      variante="fantasma"
                      aria-label={`Quitar la condición ${i + 1}`}
                      onClick={() => {
                        setClaves((k) => k.filter((_, j) => j !== i));
                        cambiar("condicion", {
                          ...condicion,
                          comparaciones: condicion.comparaciones.filter((_, j) => j !== i),
                        });
                      }}
                    >
                      Quitar
                    </Button>
                  </li>
                ))}
              </ul>
              {errores.comparaciones && <p className="ui-error">{errores.comparaciones}</p>}
              <div className="reg-condicion-acciones">
                <Button
                  variante="secundario"
                  onClick={() => {
                    setClaves((k) => [...k, nuevaClave()]);
                    cambiar("condicion", {
                      ...condicion,
                      comparaciones: [...condicion.comparaciones, COMPARACION_VACIA],
                    });
                  }}
                >
                  Agregar condición
                </Button>
                <Button
                  variante="fantasma"
                  onClick={() => {
                    const resultado = validarFormulario(form);
                    setForm((f) => ({
                      ...f,
                      condicion: null,
                      condicion_json: JSON.stringify(
                        resultado.ok ? resultado.datos.condicion : {},
                        null,
                        2,
                      ),
                    }));
                  }}
                >
                  Editar como JSON
                </Button>
              </div>
            </>
          ) : (
            <>
              <label htmlFor={idJson} className="ui-etiqueta">
                Condición en JSON (grupos <code>y</code> / <code>o</code> y comparaciones)
              </label>
              <textarea
                id={idJson}
                className="ui-control reg-json"
                rows={6}
                value={form.condicion_json}
                aria-invalid={errores.condicion_json ? true : undefined}
                onChange={(e) => cambiar("condicion_json", e.target.value)}
              />
              {errores.condicion_json && <p className="ui-error">{errores.condicion_json}</p>}
            </>
          )}
        </fieldset>

        <div className="ui-campo">
          <label htmlFor={idMensaje} className="ui-etiqueta">
            Qué se le recomienda al cuerpo técnico
          </label>
          <textarea
            id={idMensaje}
            className="ui-control"
            rows={2}
            value={form.plantilla_mensaje}
            aria-invalid={errores.plantilla_mensaje ? true : undefined}
            onChange={(e) => cambiar("plantilla_mensaje", e.target.value)}
          />
          {errores.plantilla_mensaje && <p className="ui-error">{errores.plantilla_mensaje}</p>}
        </div>

        <div className="ui-campo">
          <label htmlFor={idJustificacion} className="ui-etiqueta">
            Por qué (con las cifras reales)
          </label>
          <textarea
            id={idJustificacion}
            className="ui-control"
            rows={2}
            placeholder="La línea está a {altura_linea_m:.1f} m de nuestro arco."
            value={form.plantilla_justificacion}
            onChange={(e) => cambiar("plantilla_justificacion", e.target.value)}
          />
          <p className="ui-ayuda">
            Escribe el nombre de una métrica entre llaves para mostrar su valor, por ejemplo{" "}
            <code>{"{posesion_rival_pct:.0f}"}</code>.
          </p>
        </div>

        {guardar.isError && (
          <Alert tono="error" titulo="No se guardó la regla">
            {mensajeDeError(guardar.error)}
          </Alert>
        )}
      </form>
    </Modal>
  );
}
