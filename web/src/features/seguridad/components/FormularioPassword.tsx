import { useState, type SubmitEvent } from "react";

import { Alert, Button, Input } from "@/shared/ui";

import { estadoHttp, mensajeDeError } from "../errors";
import { useCambiarPassword } from "../hooks";
import { validarConfirmacion, validarPasswordActual, validarPasswordNueva } from "../validation";

const MENSAJE_PASSWORD_ACTUAL_INCORRECTA = "La contraseña actual es incorrecta.";

interface Errores {
  actual?: string;
  nueva?: string;
  confirmacion?: string;
}

/**
 * Cambio de contraseña propia (CU-05). Exige la actual y la confirmación de la
 * nueva. El servidor cierra las demás sesiones; aquí solo se informa.
 */
export function FormularioPassword() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const cambiar = useCambiarPassword();

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const nuevos: Errores = {};
    const errorActual = validarPasswordActual(actual);
    const errorNueva = validarPasswordNueva(actual, nueva);
    const errorConfirmacion = validarConfirmacion(nueva, confirmacion);
    if (errorActual) nuevos.actual = errorActual;
    if (errorNueva) nuevos.nueva = errorNueva;
    if (errorConfirmacion) nuevos.confirmacion = errorConfirmacion;
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) return;

    cambiar.mutate(
      { password_actual: actual, password_nueva: nueva },
      {
        onSuccess: () => {
          setActual("");
          setNueva("");
          setConfirmacion("");
        },
      },
    );
  }

  const mensajeServidor = cambiar.isError
    ? estadoHttp(cambiar.error) === 403
      ? MENSAJE_PASSWORD_ACTUAL_INCORRECTA
      : mensajeDeError(cambiar.error)
    : null;

  return (
    <form onSubmit={alEnviar} noValidate>
      {mensajeServidor && <Alert tono="error">{mensajeServidor}</Alert>}
      {cambiar.isSuccess && (
        <Alert tono="ok" titulo="Contraseña cambiada">
          Por seguridad, las demás sesiones abiertas con tu cuenta se cerrarán. Esta sesión
          sigue activa.
        </Alert>
      )}
      <Input
        etiqueta="Contraseña actual"
        type="password"
        autoComplete="current-password"
        value={actual}
        onChange={(e) => setActual(e.target.value)}
        error={errores.actual}
      />
      <Input
        etiqueta="Nueva contraseña"
        type="password"
        autoComplete="new-password"
        value={nueva}
        onChange={(e) => setNueva(e.target.value)}
        ayuda="De 8 a 72 caracteres."
        error={errores.nueva}
      />
      <Input
        etiqueta="Confirmar nueva contraseña"
        type="password"
        autoComplete="new-password"
        value={confirmacion}
        onChange={(e) => setConfirmacion(e.target.value)}
        error={errores.confirmacion}
      />
      <Alert tono="aviso">Al cambiar la contraseña se cerrarán tus demás sesiones abiertas.</Alert>
      <Button type="submit" disabled={cambiar.isPending}>
        {cambiar.isPending ? "Cambiando…" : "Cambiar contraseña"}
      </Button>
    </form>
  );
}
