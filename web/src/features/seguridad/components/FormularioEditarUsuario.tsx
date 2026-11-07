import { useState, type SubmitEvent } from "react";

import { Alert, Button, Input, Select } from "@/shared/ui";

import { mensajeDeError } from "../errors";
import { useActualizarUsuario } from "../hooks";
import { ETIQUETA_ROL, ROLES, type ActualizarUsuario, type Rol, type Usuario } from "../types";
import { validarOpcional, validarPasswordRegistro, validarRol } from "../validation";

interface Errores {
  nombre?: string;
  apellido?: string;
  rol?: string;
  password?: string;
}

/**
 * Formulario de edición de un usuario del club (CU-04 · PATCH /seguridad/usuarios/{id}).
 * Permite modificar nombre, apellido, rol, estado activo/inactivo y restablecer contraseña.
 */
export function FormularioEditarUsuario({
  usuario,
  esCuentaPropia,
  onActualizado,
  onCancelar,
}: {
  usuario: Usuario;
  esCuentaPropia: boolean;
  onActualizado: (usuario: Usuario) => void;
  onCancelar: () => void;
}) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [apellido, setApellido] = useState(usuario.apellido);
  const [rol, setRol] = useState<Rol>(usuario.rol);
  const [activo, setActivo] = useState<boolean>(usuario.activo);
  const [password, setPassword] = useState("");
  const [errores, setErrores] = useState<Errores>({});

  const actualizar = useActualizarUsuario();

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();

    const nuevos: Errores = {};
    const errorNombre = validarOpcional(nombre, 80, "El nombre");
    const errorApellido = validarOpcional(apellido, 80, "El apellido");
    const errorRol = validarRol(rol);
    const errorPassword =
      password.length > 0 ? validarPasswordRegistro(password) : null;

    if (errorNombre) nuevos.nombre = errorNombre;
    if (errorApellido) nuevos.apellido = errorApellido;
    if (errorRol) nuevos.rol = errorRol;
    if (errorPassword) nuevos.password = errorPassword;

    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) return;

    const cambios: ActualizarUsuario = {
      nombre: nombre.trim(),
      apellido: apellido.trim(),
    };

    if (!esCuentaPropia) {
      cambios.rol = rol;
      cambios.activo = activo;
    }

    if (password.length > 0) {
      cambios.password = password;
    }

    actualizar.mutate(
      { id: usuario.id, cambios },
      { onSuccess: (actualizado) => onActualizado(actualizado) }
    );
  }

  return (
    <form onSubmit={alEnviar} noValidate>
      {actualizar.isError && (
        <Alert tono="error">{mensajeDeError(actualizar.error)}</Alert>
      )}

      <div className="usuarios-form-readonly">
        <span className="usuarios-form-readonly-label">Correo electrónico (identificador)</span>
        <strong className="usuarios-form-readonly-val">{usuario.email}</strong>
      </div>

      <div className="usuarios-form-grid">
        <Input
          etiqueta="Nombre"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          error={errores.nombre}
        />
        <Input
          etiqueta="Apellido"
          value={apellido}
          onChange={(e) => setApellido(e.target.value)}
          error={errores.apellido}
        />
      </div>

      <Select
        etiqueta="Rol en el club"
        value={rol}
        disabled={esCuentaPropia}
        onChange={(e) => setRol(e.target.value as Rol)}
        ayuda={
          esCuentaPropia
            ? "Por seguridad no puedes quitarte el rol de Administrador a ti mismo."
            : undefined
        }
        error={errores.rol}
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {r} — {ETIQUETA_ROL[r]}
          </option>
        ))}
      </Select>

      <Select
        etiqueta="Estado de la cuenta"
        value={activo ? "activo" : "inactivo"}
        disabled={esCuentaPropia}
        onChange={(e) => setActivo(e.target.value === "activo")}
        ayuda={
          esCuentaPropia
            ? "No puedes desactivar tu propia cuenta administradora."
            : "Las cuentas inactivas no pueden iniciar sesión en Web ni en Móvil."
        }
      >
        <option value="activo">Activo (Acceso permitido)</option>
        <option value="inactivo">Inactivo (Acceso bloqueado)</option>
      </Select>

      <Input
        etiqueta="Restablecer contraseña (opcional)"
        type="password"
        autoComplete="new-password"
        placeholder="Dejar en blanco para conservar la actual"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        ayuda="Si ingresas una nueva clave (8 a 72 caracteres), reemplazará la actual del usuario."
        error={errores.password}
      />

      <div className="ui-modal-acciones">
        <Button
          variante="fantasma"
          onClick={onCancelar}
          disabled={actualizar.isPending}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={actualizar.isPending}>
          {actualizar.isPending ? "Guardando…" : "Guardar cambios"}
        </Button>
      </div>
    </form>
  );
}

