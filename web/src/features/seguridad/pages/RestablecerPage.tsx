/**
 * CU-06 · Elegir la contraseña nueva desde el enlace del correo (HU-52).
 *
 * Al terminar, el servidor devuelve una sesión y se entra directamente, sin
 * pasar por el login (criterio 3).
 */
import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import "@/features/seguridad/auth.css";

import { restablecerPassword } from "../api";
import { Campo } from "../components/Campo";
import { estadoHttp, mensajeDeError } from "../errors";
import { iniciarSesion } from "../session";
import { validarConfirmacion, validarPasswordRegistro } from "../validation";

interface Errores {
  nueva?: string;
  confirmacion?: string;
}

export function RestablecerPage() {
  const navigate = useNavigate();
  const [parametros] = useSearchParams();
  const token = parametros.get("token") ?? "";
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [errores, setErrores] = useState<Errores>({});

  const mutacion = useMutation({
    mutationFn: restablecerPassword,
    onSuccess: (sesion) => {
      iniciarSesion(sesion);
      navigate("/", { replace: true });
    },
  });

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const nuevos: Errores = {};
    const errorNueva = validarPasswordRegistro(nueva);
    const errorConfirmacion = validarConfirmacion(nueva, confirmacion);
    if (errorNueva) nuevos.nueva = errorNueva;
    if (errorConfirmacion) nuevos.confirmacion = errorConfirmacion;
    setErrores(nuevos);
    if (errorNueva || errorConfirmacion) return;

    mutacion.mutate({ token, password_nueva: nueva });
  }

  // 400: el enlace no sirve (vencido, ya usado o reemplazado por uno más nuevo).
  const enlaceInvalido = token === "" || estadoHttp(mutacion.error) === 400;

  return (
    <main className="auth">
      <p className="kicker">Área Técnica</p>
      <h1>Elegir contraseña nueva</h1>

      {enlaceInvalido ? (
        <>
          <p className="auth-error" role="alert">
            El enlace no es válido o ya venció. Los enlaces duran 1 hora y sirven una sola vez.
          </p>
          <Link to="/recuperar" className="auth-boton auth-boton-enlace">
            Pedir un enlace nuevo
          </Link>
        </>
      ) : (
        <form onSubmit={alEnviar} noValidate>
          <Campo
            id="password_nueva"
            etiqueta="Nueva contraseña"
            type="password"
            autoComplete="new-password"
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            error={errores.nueva}
          />
          <Campo
            id="confirmacion"
            etiqueta="Confirmar nueva contraseña"
            type="password"
            autoComplete="new-password"
            value={confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)}
            error={errores.confirmacion}
          />

          {mutacion.isError && (
            <p className="auth-error" role="alert">
              {mensajeDeError(mutacion.error)}
            </p>
          )}

          <button type="submit" className="auth-boton" disabled={mutacion.isPending}>
            {mutacion.isPending ? "Guardando…" : "Guardar y entrar"}
          </button>
        </form>
      )}

      <p className="auth-alterna">
        <Link to="/login">Volver a iniciar sesión</Link>
      </p>
    </main>
  );
}
