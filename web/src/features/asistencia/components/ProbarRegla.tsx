/**
 * CU-54 · Probar una regla contra un partido ya registrado (T-092).
 *
 * El backend reproduce las posiciones guardadas del partido con el mismo motor
 * que en vivo y cuenta cuántas veces se habría disparado. No guarda nada.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Button, Modal, Select } from "@/shared/ui";

import { listarPartidos, probarRegla } from "../api";
import { textoResultadoPrueba } from "../reglas";
import type { Regla } from "../types";

function etiquetaPartido(p: { rival: string; fecha_hora: string; es_local: boolean }): string {
  const fecha = new Date(p.fecha_hora).toLocaleDateString();
  return `${p.es_local ? "vs" : "en"} ${p.rival} · ${fecha}`;
}

export function ProbarRegla({ regla, onCerrar }: Readonly<{ regla: Regla; onCerrar: () => void }>) {
  const [partidoId, setPartidoId] = useState("");
  const partidos = useQuery({ queryKey: ["asistencia", "partidos"], queryFn: listarPartidos });
  const prueba = useMutation({ mutationFn: (id: number) => probarRegla(regla.id, id) });

  // Los ya jugados primero: son los que tienen posiciones para reproducir.
  const opciones = [...(partidos.data ?? [])].sort((a, b) =>
    b.fecha_hora.localeCompare(a.fecha_hora),
  );

  return (
    <Modal
      abierto
      titulo={`Probar "${regla.nombre}"`}
      onCerrar={onCerrar}
      acciones={
        <>
          <Button variante="fantasma" onClick={onCerrar}>
            Cerrar
          </Button>
          <Button
            disabled={!partidoId || prueba.isPending}
            onClick={() => prueba.mutate(Number(partidoId))}
          >
            {prueba.isPending ? "Reproduciendo el partido…" : "Probar"}
          </Button>
        </>
      }
    >
      <p className="reg-ayuda-prueba">
        Se reproduce el partido con el mismo motor que en vivo, evaluando cada 5 segundos y
        respetando la espera entre avisos. Sirve también para reglas desactivadas.
      </p>
      {partidos.isError ? (
        <Alert tono="error">{mensajeDeError(partidos.error)}</Alert>
      ) : (
        <Select
          etiqueta="Partido"
          value={partidoId}
          disabled={partidos.isLoading}
          onChange={(e) => {
            setPartidoId(e.target.value);
            prueba.reset();
          }}
        >
          <option value="">{partidos.isLoading ? "Cargando partidos…" : "Elige un partido"}</option>
          {opciones.map((p) => (
            <option key={p.id} value={p.id}>
              {etiquetaPartido(p)}
            </option>
          ))}
        </Select>
      )}
      {prueba.isSuccess && (
        <Alert tono={prueba.data.evaluaciones === 0 ? "aviso" : "info"} titulo="Resultado">
          {textoResultadoPrueba(prueba.data)}
        </Alert>
      )}
      {prueba.isError && (
        <Alert tono="error" titulo="No se pudo probar la regla">
          {mensajeDeError(prueba.error)}
        </Alert>
      )}
    </Modal>
  );
}
