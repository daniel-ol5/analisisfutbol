/** CU-02 · Iniciar sesión. */
import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import "@/features/seguridad/auth.css";

import { login } from "../api";
import { Campo } from "../components/Campo";
import { mensajeDeLogin } from "../errors";
import { iniciarSesion } from "../session";
import { normalizarEmail, validarEmail, validarPasswordLogin } from "../validation";

interface Errores {
  email?: string;
  password?: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errores, setErrores] = useState<Errores>({});

  const mutacion = useMutation({
    mutationFn: login,
    onSuccess: (sesion) => {
      iniciarSesion(sesion);
      navigate("/", { replace: true });
    },
  });

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const emailNormalizado = normalizarEmail(email);
    setEmail(emailNormalizado);

    const nuevos: Errores = {};
    const errorEmail = validarEmail(emailNormalizado);
    const errorPassword = validarPasswordLogin(password);
    if (errorEmail) nuevos.email = errorEmail;
    if (errorPassword) nuevos.password = errorPassword;
    setErrores(nuevos);
    if (errorEmail || errorPassword) return;

    mutacion.mutate({ email: emailNormalizado, password });
  }

  return (
    <main className="auth">
      <p className="kicker">Área Técnica</p>
      <h1>Iniciar sesión</h1>

      <form onSubmit={alEnviar} noValidate>
        <Campo
          id="email"
          etiqueta="Correo electrónico"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setEmail(normalizarEmail(email))}
          error={errores.email}
        />
        <Campo
          id="password"
          etiqueta="Contraseña"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errores.password}
        />
        <p className="auth-olvido">
          <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
        </p>

        {mutacion.isError && (
          <p className="auth-error" role="alert">
            {mensajeDeLogin(mutacion.error)}
          </p>
        )}

        <button type="submit" className="auth-boton" disabled={mutacion.isPending}>
          {mutacion.isPending ? "Iniciando sesión…" : "Iniciar sesión"}
        </button>
      </form>

      <p className="auth-alterna">
        ¿Tu club aún no tiene cuenta? <Link to="/registro">Registrar club</Link>
      </p>
    </main>
  );
}
