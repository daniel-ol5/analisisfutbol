import { useState, type SubmitEvent } from "react";

import { Alert, Button, Input, Select } from "@/shared/ui";

import { MENSAJE_EMAIL_DUPLICADO, estadoHttp, mensajeDeError } from "../errors";
import { useCrearUsuario } from "../hooks";
import { ROLES, type Rol } from "../types";
import {
  normalizarEmail,
  validarEmail,
  validarOpcional,
  validarPasswordRegistro,
  validarRol,
} from "../validation";

interface Errores {
  email?: string;
  password?: string;
  nombre?: string;
  apellido?: string;
  rol?: string;
}

/** Formulario de alta de usuario (CU-04). Se monta al abrir el modal y se desmonta al cerrarlo. */
export function FormularioUsuario({
  onCreado,
  onCancelar,
}: {
  onCreado: () => void;
  onCancelar: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [rol, setRol] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const crear = useCrearUsuario();

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const emailNormalizado = normalizarEmail(email);
    setEmail(emailNormalizado);

    const nuevos: Errores = {};
    const errorEmail = validarEmail(emailNormalizado);
    const errorPassword = validarPasswordRegistro(password);
    const errorNombre = validarOpcional(nombre, 80, "El nombre");
    const errorApellido = validarOpcional(apellido, 80, "El apellido");
    const errorRol = validarRol(rol);
    if (errorEmail) nuevos.email = errorEmail;
    if (errorPassword) nuevos.password = errorPassword;
    if (errorNombre) nuevos.nombre = errorNombre;
    if (errorApellido) nuevos.apellido = errorApellido;
    if (errorRol) nuevos.rol = errorRol;
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) return;

    crear.mutate(
      {
        email: emailNormalizado,
        password,
        rol: rol as Rol,
        nombre: nombre.trim(),
        apellido: apellido.trim(),
      },
      { onSuccess: onCreado },
    );
  }

  const mensajeServidor = crear.isError
    ? estadoHttp(crear.error) === 409
      ? MENSAJE_EMAIL_DUPLICADO
      : mensajeDeError(crear.error)
    : null;

  return (
    <form onSubmit={alEnviar} noValidate>
      {mensajeServidor && <Alert tono="error">{mensajeServidor}</Alert>}
      <Input
        etiqueta="Correo electrónico"
        type="email"
        autoComplete="off"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={errores.email}
      />
      <Input
        etiqueta="Contraseña inicial"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        ayuda="De 8 a 72 caracteres."
        error={errores.password}
      />
      <Input
        etiqueta="Nombre (opcional)"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        error={errores.nombre}
      />
      <Input
        etiqueta="Apellido (opcional)"
        value={apellido}
        onChange={(e) => setApellido(e.target.value)}
        error={errores.apellido}
      />
      <Select
        etiqueta="Rol"
        value={rol}
        onChange={(e) => setRol(e.target.value)}
        error={errores.rol}
      >
        <option value="">Selecciona un rol</option>
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </Select>
      <div className="ui-modal-acciones">
        <Button variante="fantasma" onClick={onCancelar} disabled={crear.isPending}>
          Cancelar
        </Button>
        <Button type="submit" disabled={crear.isPending}>
          {crear.isPending ? "Creando…" : "Crear usuario"}
        </Button>
      </div>
    </form>
  );
}
