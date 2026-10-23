import { useState, type SubmitEvent } from "react";

import { Alert, Button, Input } from "@/shared/ui";

import { mensajeDeError } from "../errors";
import { useEditarPerfil } from "../hooks";
import type { Usuario } from "../types";
import { validarOpcional } from "../validation";

interface Errores {
  nombre?: string;
  apellido?: string;
}

/** Edición de nombre y apellido propios (CU-05). El correo y el rol no se editan. */
export function FormularioPerfil({ usuario }: { usuario: Usuario }) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [apellido, setApellido] = useState(usuario.apellido);
  const [errores, setErrores] = useState<Errores>({});
  const editar = useEditarPerfil();

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const nuevos: Errores = {};
    const errorNombre = validarOpcional(nombre, 80, "El nombre");
    const errorApellido = validarOpcional(apellido, 80, "El apellido");
    if (errorNombre) nuevos.nombre = errorNombre;
    if (errorApellido) nuevos.apellido = errorApellido;
    setErrores(nuevos);
    if (errorNombre || errorApellido) return;

    editar.mutate({ nombre: nombre.trim(), apellido: apellido.trim() });
  }

  return (
    <form onSubmit={alEnviar} noValidate>
      {editar.isError && <Alert tono="error">{mensajeDeError(editar.error)}</Alert>}
      {editar.isSuccess && <Alert tono="ok">Datos actualizados.</Alert>}
      <Input
        etiqueta="Nombre"
        autoComplete="given-name"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        error={errores.nombre}
      />
      <Input
        etiqueta="Apellido"
        autoComplete="family-name"
        value={apellido}
        onChange={(e) => setApellido(e.target.value)}
        error={errores.apellido}
      />
      <Button type="submit" disabled={editar.isPending}>
        {editar.isPending ? "Guardando…" : "Guardar cambios"}
      </Button>
    </form>
  );
}
