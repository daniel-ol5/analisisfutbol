/** CU-04 · Gestionar usuarios y roles. Solo ADMIN (ver app/permisos.ts). */
import { useState } from "react";

import { Alert, Badge, Button, Modal, Table } from "@/shared/ui";

import { FormularioUsuario } from "../components/FormularioUsuario";
import { HABILITAR_EDICION_USUARIOS } from "../config";
import { mensajeDeError } from "../errors";
import { useActualizarUsuario, useUsuarios } from "../hooks";
import { useSesion } from "../session";
import type { Usuario } from "../types";

import "./usuarios.css";

export function UsuariosPage() {
  const usuarios = useUsuarios();
  const actualizar = useActualizarUsuario();
  const idPropio = useSesion()?.usuario.id;

  const [creando, setCreando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [aDesactivar, setADesactivar] = useState<Usuario | null>(null);

  function cerrarConfirmacion() {
    setADesactivar(null);
    actualizar.reset();
  }

  function confirmarDesactivacion() {
    if (!aDesactivar) return;
    actualizar.mutate(
      { id: aDesactivar.id, cambios: { activo: false } },
      {
        onSuccess: () => {
          setAviso(`Usuario ${aDesactivar.email} desactivado.`);
          cerrarConfirmacion();
        },
      },
    );
  }

  return (
    <main className="usuarios">
      
      <div className="usuarios-cabecera">
        <h1>Usuarios</h1>
        <Button
          onClick={() => {
            setAviso(null);
            setCreando(true);
          }}
        >
          Nuevo usuario
        </Button>
      </div>

      {aviso && <Alert tono="ok">{aviso}</Alert>}

      {usuarios.isPending && <p className="usuarios-estado">Cargando usuarios…</p>}

      {usuarios.isError && (
        <Alert tono="error" titulo="No se pudo cargar el listado">
          {mensajeDeError(usuarios.error)}{" "}
          <Button variante="secundario" onClick={() => usuarios.refetch()}>
            Reintentar
          </Button>
        </Alert>
      )}

      {usuarios.isSuccess && usuarios.data.length === 0 && (
        <p className="usuarios-estado">Todavía no hay usuarios en el club.</p>
      )}

      {usuarios.isSuccess && usuarios.data.length > 0 && (
        <Table titulo="Usuarios del club">
          <thead>
            <tr>
              <th scope="col">Nombre</th>
              <th scope="col">Correo</th>
              <th scope="col">Rol</th>
              <th scope="col">Estado</th>
              {HABILITAR_EDICION_USUARIOS && <th scope="col">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {usuarios.data.map((u) => (
              <tr key={u.id}>
                <td>{`${u.nombre} ${u.apellido}`.trim() || "—"}</td>
                <td>{u.email}</td>
                <td>
                  <Badge tono="info">{u.rol}</Badge>
                </td>
                <td>
                  <Badge tono={u.activo ? "ok" : "error"}>{u.activo ? "Activo" : "Inactivo"}</Badge>
                </td>
                {HABILITAR_EDICION_USUARIOS && (
                  <td>
                    {u.activo && u.id !== idPropio && (
                      <Button variante="peligro" onClick={() => setADesactivar(u)}>
                        Desactivar
                      </Button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Modal abierto={creando} titulo="Nuevo usuario" onCerrar={() => setCreando(false)}>
        {creando && (
          <FormularioUsuario
            onCancelar={() => setCreando(false)}
            onCreado={() => {
              setCreando(false);
              setAviso("Usuario creado.");
            }}
          />
        )}
      </Modal>

      <Modal
        abierto={aDesactivar !== null}
        titulo="Desactivar usuario"
        onCerrar={cerrarConfirmacion}
        acciones={
          <>
            <Button variante="fantasma" onClick={cerrarConfirmacion} disabled={actualizar.isPending}>
              Cancelar
            </Button>
            <Button variante="peligro" onClick={confirmarDesactivacion} disabled={actualizar.isPending}>
              {actualizar.isPending ? "Desactivando…" : "Desactivar"}
            </Button>
          </>
        }
      >
        {actualizar.isError && <Alert tono="error">{mensajeDeError(actualizar.error)}</Alert>}
        <p>
          {aDesactivar?.email} dejará de poder iniciar sesión. ¿Seguro que quieres desactivarlo?
        </p>
      </Modal>
    </main>
  );
}
