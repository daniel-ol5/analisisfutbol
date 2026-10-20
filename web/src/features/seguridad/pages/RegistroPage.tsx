/** CU-01 · Registrar club y cuenta administradora. */
import { useMutation } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import "@/features/seguridad/auth.css";

import { registrar } from "../api";
import { Campo } from "../components/Campo";
import { MENSAJE_EMAIL_DUPLICADO, estadoHttp, mensajeDeError } from "../errors";
import { iniciarSesion } from "../session";
import {
  normalizarEmail,
  validarEmail,
  validarNombreClub,
  validarOpcional,
  validarPasswordRegistro,
} from "../validation";

interface Errores {
  nombreClub?: string;
  ciudad?: string;
  email?: string;
  password?: string;
  nombre?: string;
  apellido?: string;
}

export function RegistroPage() {
  const navigate = useNavigate();
  const [nombreClub, setNombreClub] = useState("");
  const [ciudad, setCiudad] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [errores, setErrores] = useState<Errores>({});

  const mutacion = useMutation({
    mutationFn: registrar,
    onSuccess: (sesion) => {
      iniciarSesion(sesion);
      navigate("/", { replace: true });
    },
    onError: (error) => {
      // 409: el error pertenece al campo email, no al mensaje general.
      if (estadoHttp(error) === 409) {
        setErrores((previos) => ({
          ...previos,
          email: MENSAJE_EMAIL_DUPLICADO,
        }));
      }
    },
  });

  function alEnviar(evento: SubmitEvent<HTMLFormElement>) {
    evento.preventDefault();
    const emailNormalizado = normalizarEmail(email);
    setEmail(emailNormalizado);

    const nuevos: Errores = {};
    const asignar = (campo: keyof Errores, mensaje: string | null) => {
      if (mensaje) nuevos[campo] = mensaje;
    };
    asignar("nombreClub", validarNombreClub(nombreClub));
    asignar("ciudad", validarOpcional(ciudad, 80, "La ciudad"));
    asignar("email", validarEmail(emailNormalizado));
    asignar("password", validarPasswordRegistro(password));
    asignar("nombre", validarOpcional(nombre, 80, "El nombre"));
    asignar("apellido", validarOpcional(apellido, 80, "El apellido"));
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) return;

    mutacion.mutate({
      nombre_club: nombreClub.trim(),
      ciudad: ciudad.trim(),
      email: emailNormalizado,
      password,
      nombre: nombre.trim(),
      apellido: apellido.trim(),
    });
  }

  const errorGeneral =
    mutacion.isError && estadoHttp(mutacion.error) !== 409 ? mensajeDeError(mutacion.error) : null;

  return (
    <main className="auth">
      <p className="kicker">Área Técnica</p>
      <h1>Registrar club</h1>

      <form onSubmit={alEnviar} noValidate>
        <Campo
          id="nombre_club"
          etiqueta="Nombre del club"
          autoComplete="organization"
          value={nombreClub}
          onChange={(e) => setNombreClub(e.target.value)}
          error={errores.nombreClub}
        />
        <Campo
          id="ciudad"
          etiqueta="Ciudad (opcional)"
          autoComplete="address-level2"
          value={ciudad}
          onChange={(e) => setCiudad(e.target.value)}
          error={errores.ciudad}
        />
        <Campo
          id="email"
          etiqueta="Correo electrónico"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setErrores((previos) => ({ ...previos, email: undefined }));
          }}
          onBlur={() => setEmail(normalizarEmail(email))}
          error={errores.email}
        />
        <Campo
          id="password"
          etiqueta="Contraseña (8 a 72 caracteres)"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errores.password}
        />
        <Campo
          id="nombre"
          etiqueta="Nombre (opcional)"
          autoComplete="given-name"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          error={errores.nombre}
        />
        <Campo
          id="apellido"
          etiqueta="Apellido (opcional)"
          autoComplete="family-name"
          value={apellido}
          onChange={(e) => setApellido(e.target.value)}
          error={errores.apellido}
        />

        {errorGeneral && (
          <p className="auth-error" role="alert">
            {errorGeneral}
          </p>
        )}

        <button type="submit" className="auth-boton" disabled={mutacion.isPending}>
          {mutacion.isPending ? "Registrando…" : "Registrar club"}
        </button>
      </form>

      <p className="auth-alterna">
        ¿Ya tienes cuenta? <Link to="/login">Iniciar sesión</Link>
      </p>
    </main>
  );
}
