/** CU-06 · Pedir el enlace para restablecer la contraseña (HU-52). */
import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link } from "react-router-dom";

import "@/features/seguridad/auth.css";

import { pedirRecuperacion } from "../api";
import { Campo } from "../components/Campo";
import { mensajeDeError } from "../errors";
import { normalizarEmail, validarEmail } from "../validation";

export function RecuperarPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string>();
  const mutacion = useMutation({ mutationFn: pedirRecuperacion });

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const emailNormalizado = normalizarEmail(email);
    setEmail(emailNormalizado);

    const errorEmail = validarEmail(emailNormalizado);
    setError(errorEmail ?? undefined);
    if (errorEmail) return;

    mutacion.mutate({ email: emailNormalizado });
  }

  return (
    <main className="auth">
      <p className="kicker">Área Técnica</p>
      <h1>Recuperar contraseña</h1>

      {mutacion.isSuccess ? (
        // Mismo mensaje exista o no la cuenta: no se revela qué correos están registrados.
        <p className="auth-ok" role="status">
          Si <strong>{email}</strong> está registrado, te enviamos un enlace para elegir una
          contraseña nueva. Vence en 1 hora y sirve una sola vez. Revisa también la carpeta de spam.
        </p>
      ) : (
        <>
          <p className="auth-texto">
            Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una contraseña
            nueva.
          </p>
          <form onSubmit={alEnviar} noValidate>
            <Campo
              id="email"
              etiqueta="Correo electrónico"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setEmail(normalizarEmail(email))}
              error={error}
            />

            {mutacion.isError && (
              <p className="auth-error" role="alert">
                {mensajeDeError(mutacion.error)}
              </p>
            )}

            <button type="submit" className="auth-boton" disabled={mutacion.isPending}>
              {mutacion.isPending ? "Enviando…" : "Enviar enlace"}
            </button>
          </form>
        </>
      )}

      <p className="auth-alterna">
        ¿La recordaste? <Link to="/login">Volver a iniciar sesión</Link>
      </p>
    </main>
  );
}
