/** CU-05 · Administrar perfil propio. Para cualquier usuario autenticado. */
import { Alert, Badge, Button } from "@/shared/ui";

import { FormularioPassword } from "../components/FormularioPassword";
import { FormularioPerfil } from "../components/FormularioPerfil";
import { HABILITAR_CAMBIO_PASSWORD, HABILITAR_EDICION_PERFIL } from "../config";
import { mensajeDeError } from "../errors";
import { usePerfil } from "../hooks";

import "./perfil.css";

export function PerfilPage() {
  const perfil = usePerfil();

  return (
    <main className="perfil">
      <h1>Mi perfil</h1>

      {perfil.isPending && <p className="perfil-estado">Cargando tu perfil…</p>}

      {perfil.isError && (
        <Alert tono="error" titulo="No se pudo cargar tu perfil">
          {mensajeDeError(perfil.error)}{" "}
          <Button variante="secundario" onClick={() => perfil.refetch()}>
            Reintentar
          </Button>
        </Alert>
      )}

      {perfil.isSuccess && (
        <>
          <section className="perfil-tarjeta" aria-labelledby="perfil-datos">
            <h2 id="perfil-datos">Mis datos</h2>
            <dl className="perfil-datos">
              <dt>Correo electrónico</dt>
              <dd>{perfil.data.email}</dd>
              <dt>Club</dt>
              <dd>{perfil.data.club_nombre}</dd>
              <dt>Rol</dt>
              <dd>
                <Badge tono="info">{perfil.data.rol}</Badge>
              </dd>
              <dt>Estado</dt>
              <dd>
                <Badge tono={perfil.data.activo ? "ok" : "error"}>
                  {perfil.data.activo ? "Activo" : "Inactivo"}
                </Badge>
              </dd>
              {!HABILITAR_EDICION_PERFIL && (
                <>
                  <dt>Nombre</dt>
                  <dd>{perfil.data.nombre || "—"}</dd>
                  <dt>Apellido</dt>
                  <dd>{perfil.data.apellido || "—"}</dd>
                </>
              )}
            </dl>
            {HABILITAR_EDICION_PERFIL ? (
              <FormularioPerfil usuario={perfil.data} />
            ) : (
              <Alert tono="info">La edición del perfil todavía no está disponible.</Alert>
            )}
          </section>

          {HABILITAR_CAMBIO_PASSWORD && (
            <section className="perfil-tarjeta" aria-labelledby="perfil-password">
              <h2 id="perfil-password">Contraseña</h2>
              <FormularioPassword />
            </section>
          )}
        </>
      )}
    </main>
  );
}
