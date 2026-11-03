/** CU-04 · Gestionar usuarios y roles. Solo ADMIN (ver app/permisos.ts). */
import { useMemo, useState } from "react";

import { Alert, Badge, Button, Modal, Table } from "@/shared/ui";

import { FormularioEditarUsuario } from "../components/FormularioEditarUsuario";
import { FormularioUsuario } from "../components/FormularioUsuario";
import { HABILITAR_EDICION_USUARIOS } from "../config";
import { mensajeDeError } from "../errors";
import {
  useActualizarUsuario,
  useEliminarUsuario,
  useUsuario,
  useUsuarios,
} from "../hooks";
import { useSesion } from "../session";
import {
  DESCRIPCION_ROL,
  ETIQUETA_ROL,
  ROLES,
  type Rol,
  type Usuario,
} from "../types";

import "./usuarios.css";

const LISTA_VACIA: Usuario[] = [];

function obtenerIniciales(u: Usuario): string {
  const i1 = u.nombre.trim().charAt(0);
  const i2 = u.apellido.trim().charAt(0);
  const res = `${i1}${i2}`.toUpperCase();
  return res || u.email.slice(0, 2).toUpperCase();
}

function nombreMostrado(u: Usuario): string {
  const completo = `${u.nombre} ${u.apellido}`.trim();
  return completo || "Sin nombre asignado";
}

export function UsuariosPage() {
  const usuarios = useUsuarios();
  const actualizar = useActualizarUsuario();
  const eliminar = useEliminarUsuario();
  const idPropio = useSesion()?.usuario.id;

  // Estados de modales
  const [creando, setCreando] = useState(false);
  const [enDetalle, setEnDetalle] = useState<Usuario | null>(null);
  const [enEdicion, setEnEdicion] = useState<Usuario | null>(null);
  const [aDarDeBaja, setADarDeBaja] = useState<Usuario | null>(null);
  const [aReactivar, setAReactivar] = useState<Usuario | null>(null);

  // Filtros de búsqueda
  const [busqueda, setBusqueda] = useState("");
  const [filtroRol, setFiltroRol] = useState<string>("TODOS");
  const [filtroEstado, setFiltroEstado] = useState<string>("TODOS");

  const [aviso, setAviso] = useState<string | null>(null);

  // Consulta en vivo para el modal de visualización de datos (GET /seguridad/usuarios/{id})
  const detalleQuery = useUsuario(enDetalle?.id ?? null);
  const usuarioDetalle = detalleQuery.data ?? enDetalle;

  const lista = usuarios.data ?? LISTA_VACIA;

  const estadisticas = useMemo(() => {
    const total = lista.length;
    const activos = lista.filter((u) => u.activo).length;
    const inactivos = total - activos;
    const admins = lista.filter((u) => u.rol === "ADMIN").length;
    return { total, activos, inactivos, admins };
  }, [lista]);

  const usuariosFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return lista.filter((u) => {
      if (filtroRol !== "TODOS" && u.rol !== filtroRol) return false;
      if (filtroEstado === "ACTIVOS" && !u.activo) return false;
      if (filtroEstado === "INACTIVOS" && u.activo) return false;
      if (!q) return true;
      const texto = `${u.nombre} ${u.apellido} ${u.email} ${u.rol}`.toLowerCase();
      return texto.includes(q);
    });
  }, [lista, busqueda, filtroRol, filtroEstado]);

  function cerrarBaja() {
    setADarDeBaja(null);
    eliminar.reset();
  }

  function confirmarBaja() {
    if (!aDarDeBaja) return;
    eliminar.mutate(aDarDeBaja.id, {
      onSuccess: () => {
        setAviso(`Se dio de baja la cuenta de ${aDarDeBaja.email}.`);
        if (enDetalle?.id === aDarDeBaja.id) setEnDetalle(null);
        cerrarBaja();
      },
    });
  }

  function cerrarReactivacion() {
    setAReactivar(null);
    actualizar.reset();
  }

  function confirmarReactivacion() {
    if (!aReactivar) return;
    actualizar.mutate(
      { id: aReactivar.id, cambios: { activo: true } },
      {
        onSuccess: () => {
          setAviso(`Cuenta de ${aReactivar.email} reactivada correctamente.`);
          if (enDetalle?.id === aReactivar.id) {
            setEnDetalle({ ...aReactivar, activo: true });
          }
          cerrarReactivacion();
        },
      }
    );
  }

  return (
    <main className="usuarios">
      {/* Cabecera de página */}
      <header className="usuarios-cabecera">
        <div>
          <p className="kicker">Paquete P1 · CU-04</p>
          <h1>Gestión de Usuarios y Roles</h1>
          <p className="usuarios-subtitulo">
            Administra los integrantes del cuerpo técnico, asigna permisos por rol y controla el acceso al club.
          </p>
        </div>
        <Button
          onClick={() => {
            setAviso(null);
            setCreando(true);
          }}
        >
          + Nuevo usuario
        </Button>
      </header>

      {aviso && <Alert tono="ok">{aviso}</Alert>}

      {/* Resumen de métricas del club */}
      {usuarios.isSuccess && lista.length > 0 && (
        <section className="usuarios-kpis" aria-label="Resumen de cuentas">
          <div className="usuarios-kpi">
            <span className="usuarios-kpi-label">Total del Club</span>
            <strong className="usuarios-kpi-valor">{estadisticas.total}</strong>
            <span className="usuarios-kpi-meta">Integrantes registrados</span>
          </div>
          <div className="usuarios-kpi">
            <span className="usuarios-kpi-label">Cuentas Activas</span>
            <strong className="usuarios-kpi-valor ok">{estadisticas.activos}</strong>
            <span className="usuarios-kpi-meta">Con acceso habilitado</span>
          </div>
          <div className="usuarios-kpi">
            <span className="usuarios-kpi-label">Bajas / Inactivos</span>
            <strong className="usuarios-kpi-valor warn">{estadisticas.inactivos}</strong>
            <span className="usuarios-kpi-meta">Acceso suspendido</span>
          </div>
          <div className="usuarios-kpi">
            <span className="usuarios-kpi-label">Administradores</span>
            <strong className="usuarios-kpi-valor">{estadisticas.admins}</strong>
            <span className="usuarios-kpi-meta">Control del club</span>
          </div>
        </section>
      )}

      {/* Barra de búsqueda y filtros */}
      {usuarios.isSuccess && lista.length > 0 && (
        <section className="usuarios-filtros" aria-label="Filtros de usuarios">
          <div className="usuarios-busqueda-wrap">
            <input
              type="search"
              className="usuarios-busqueda-input"
              placeholder="Buscar por nombre, apellido o correo electrónico…"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              aria-label="Buscar usuarios"
            />
          </div>
          <div className="usuarios-selectores">
            <select
              className="usuarios-filtro-select"
              value={filtroRol}
              onChange={(e) => setFiltroRol(e.target.value)}
              aria-label="Filtrar por rol"
            >
              <option value="TODOS">Todos los roles</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r} — {ETIQUETA_ROL[r]}
                </option>
              ))}
            </select>
            <select
              className="usuarios-filtro-select"
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
              aria-label="Filtrar por estado"
            >
              <option value="TODOS">Todos los estados</option>
              <option value="ACTIVOS">Solo activos</option>
              <option value="INACTIVOS">Solo dados de baja</option>
            </select>
          </div>
        </section>
      )}

      {usuarios.isPending && <p className="usuarios-estado">Cargando usuarios del club…</p>}

      {usuarios.isError && (
        <Alert tono="error" titulo="No se pudo cargar el listado">
          {mensajeDeError(usuarios.error)}{" "}
          <Button variante="secundario" onClick={() => usuarios.refetch()}>
            Reintentar
          </Button>
        </Alert>
      )}

      {usuarios.isSuccess && lista.length === 0 && (
        <div className="usuarios-vacio">
          <p className="usuarios-estado">Todavía no hay usuarios registrados en el club.</p>
        </div>
      )}

      {usuarios.isSuccess && lista.length > 0 && usuariosFiltrados.length === 0 && (
        <div className="usuarios-vacio">
          <p className="usuarios-estado">
            Ningún usuario coincide con los filtros seleccionados.
          </p>
          <Button
            variante="secundario"
            onClick={() => {
              setBusqueda("");
              setFiltroRol("TODOS");
              setFiltroEstado("TODOS");
            }}
          >
            Limpiar filtros
          </Button>
        </div>
      )}

      {usuarios.isSuccess && usuariosFiltrados.length > 0 && (
        <Table titulo={`Usuarios del club (${usuariosFiltrados.length})`}>
          <thead>
            <tr>
              <th scope="col">Integrante</th>
              <th scope="col">Correo electrónico</th>
              <th scope="col">Rol asignado</th>
              <th scope="col">Estado</th>
              {HABILITAR_EDICION_USUARIOS && <th scope="col">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {usuariosFiltrados.map((u) => {
              const esPropio = u.id === idPropio;
              return (
                <tr key={u.id} className={!u.activo ? "usuarios-fila-inactiva" : undefined}>
                  <td>
                    <div className="usuarios-celda-identidad">
                      <span
                        className={`usuarios-avatar${!u.activo ? " inactivo" : ""}`}
                        aria-hidden="true"
                      >
                        {obtenerIniciales(u)}
                      </span>
                      <div className="usuarios-celda-textos">
                        <div className="usuarios-celda-nombre-linea">
                          <button
                            type="button"
                            className="usuarios-nombre-link"
                            onClick={() => setEnDetalle(u)}
                          >
                            {`${u.nombre} ${u.apellido}`.trim() || "—"}
                          </button>
                          {esPropio && (
                            <span className="usuarios-chip-propio" title="Tu cuenta actual">
                              Tú
                            </span>
                          )}
                        </div>
                        <span className="usuarios-celda-id">ID #{u.id}</span>
                      </div>
                    </div>
                  </td>
                  <td className="usuarios-celda-email">{u.email}</td>
                  <td>
                    <div className="usuarios-celda-rol">
                      <Badge tono="info">{u.rol}</Badge>
                      <span className="usuarios-rol-desc">{ETIQUETA_ROL[u.rol]}</span>
                    </div>
                  </td>
                  <td>
                    <Badge tono={u.activo ? "ok" : "error"}>
                      {u.activo ? "Activo" : "Inactivo"}
                    </Badge>
                  </td>
                  {HABILITAR_EDICION_USUARIOS && (
                    <td>
                      <div className="usuarios-acciones-fila">
                        <Button
                          variante="secundario"
                          onClick={() => setEnDetalle(u)}
                        >
                          Ver datos
                        </Button>
                        <Button
                          variante="secundario"
                          onClick={() => {
                            setAviso(null);
                            setEnEdicion(u);
                          }}
                        >
                          Editar
                        </Button>
                        {!esPropio &&
                          (u.activo ? (
                            <Button
                              variante="peligro"
                              onClick={() => {
                                setAviso(null);
                                setADarDeBaja(u);
                              }}
                            >
                              Dar de baja
                            </Button>
                          ) : (
                            <Button
                              variante="secundario"
                              onClick={() => {
                                setAviso(null);
                                setAReactivar(u);
                              }}
                            >
                              Reactivar
                            </Button>
                          ))}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}

      {/* 1. Modal de Alta de Usuario */}
      <Modal
        abierto={creando}
        titulo="Nuevo usuario del club"
        onCerrar={() => setCreando(false)}
      >
        {creando && (
          <FormularioUsuario
            onCancelar={() => setCreando(false)}
            onCreado={() => {
              setCreando(false);
              setAviso("Usuario creado exitosamente.");
            }}
          />
        )}
      </Modal>

      {/* 2. Modal de Visualización de Datos del Usuario */}
      <Modal
        abierto={enDetalle !== null}
        titulo="Ficha de usuario"
        onCerrar={() => setEnDetalle(null)}
        acciones={
          usuarioDetalle ? (
            <>
              <Button variante="fantasma" onClick={() => setEnDetalle(null)}>
                Cerrar
              </Button>
              <Button
                variante="secundario"
                onClick={() => {
                  const target = usuarioDetalle;
                  setEnDetalle(null);
                  setEnEdicion(target);
                }}
              >
                Editar datos
              </Button>
              {usuarioDetalle.id !== idPropio &&
                (usuarioDetalle.activo ? (
                  <Button
                    variante="peligro"
                    onClick={() => {
                      const target = usuarioDetalle;
                      setEnDetalle(null);
                      setADarDeBaja(target);
                    }}
                  >
                    Dar de baja
                  </Button>
                ) : (
                  <Button
                    onClick={() => {
                      const target = usuarioDetalle;
                      setEnDetalle(null);
                      setAReactivar(target);
                    }}
                  >
                    Reactivar cuenta
                  </Button>
                ))}
            </>
          ) : undefined
        }
      >
        {usuarioDetalle && (
          <div className="usuarios-ficha">
            <div className="usuarios-ficha-cabecera">
              <span className="usuarios-ficha-avatar" aria-hidden="true">
                {obtenerIniciales(usuarioDetalle)}
              </span>
              <div className="usuarios-ficha-titulos">
                <h3 className="usuarios-ficha-nombre">
                  {nombreMostrado(usuarioDetalle)}
                </h3>
                <p className="usuarios-ficha-correo">{usuarioDetalle.email}</p>
                <div className="usuarios-ficha-badges">
                  <Badge tono="info">
                    {usuarioDetalle.rol} · {ETIQUETA_ROL[usuarioDetalle.rol as Rol]}
                  </Badge>
                  <Badge tono={usuarioDetalle.activo ? "ok" : "error"}>
                    {usuarioDetalle.activo ? "Cuenta Activa" : "Cuenta Inactiva"}
                  </Badge>
                </div>
              </div>
            </div>

            <dl className="usuarios-ficha-grid">
              <div className="usuarios-ficha-item">
                <dt>ID de Usuario</dt>
                <dd>#{usuarioDetalle.id}</dd>
              </div>
              <div className="usuarios-ficha-item">
                <dt>ID de Club</dt>
                <dd>Club #{usuarioDetalle.club_id}</dd>
              </div>
              <div className="usuarios-ficha-item">
                <dt>Nombre</dt>
                <dd>{usuarioDetalle.nombre || "No especificado"}</dd>
              </div>
              <div className="usuarios-ficha-item">
                <dt>Apellido</dt>
                <dd>{usuarioDetalle.apellido || "No especificado"}</dd>
              </div>
            </dl>

            <div className="usuarios-ficha-permisos">
              <span className="usuarios-ficha-permisos-titulo">
                Alcance del rol ({ETIQUETA_ROL[usuarioDetalle.rol as Rol]})
              </span>
              <p className="usuarios-ficha-permisos-desc">
                {DESCRIPCION_ROL[usuarioDetalle.rol as Rol]}
              </p>
            </div>
          </div>
        )}
      </Modal>

      {/* 3. Modal de Edición de Usuario */}
      <Modal
        abierto={enEdicion !== null}
        titulo={
          enEdicion
            ? `Editar usuario: ${nombreMostrado(enEdicion)}`
            : "Editar usuario"
        }
        onCerrar={() => setEnEdicion(null)}
      >
        {enEdicion && (
          <FormularioEditarUsuario
            key={`${enEdicion.id}-${enEdicion.nombre}-${enEdicion.apellido}-${enEdicion.rol}-${enEdicion.activo}`}
            usuario={enEdicion}
            esCuentaPropia={enEdicion.id === idPropio}
            onCancelar={() => setEnEdicion(null)}
            onActualizado={(actualizado) => {
              setEnEdicion(null);
              setAviso(`Datos de ${actualizado.email} actualizados correctamente.`);
            }}
          />
        )}
      </Modal>

      {/* 4. Modal de Confirmación de Baja / Eliminación lógica */}
      <Modal
        abierto={aDarDeBaja !== null}
        titulo="Dar de baja usuario"
        onCerrar={cerrarBaja}
        acciones={
          <>
            <Button
              variante="fantasma"
              onClick={cerrarBaja}
              disabled={eliminar.isPending}
            >
              Cancelar
            </Button>
            <Button
              variante="peligro"
              onClick={confirmarBaja}
              disabled={eliminar.isPending}
            >
              {eliminar.isPending ? "Procesando baja…" : "Confirmar baja"}
            </Button>
          </>
        }
      >
        {eliminar.isError && (
          <Alert tono="error">{mensajeDeError(eliminar.error)}</Alert>
        )}
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          El usuario <strong>{aDarDeBaja?.email}</strong> ({aDarDeBaja && nombreMostrado(aDarDeBaja)}) quedará
          inactivo y no podrá iniciar sesión en la plataforma web ni en la aplicación móvil.
          Sus registros históricos en el club se conservarán.
        </p>
      </Modal>

      {/* 5. Modal de Confirmación de Reactivación */}
      <Modal
        abierto={aReactivar !== null}
        titulo="Reactivar cuenta de usuario"
        onCerrar={cerrarReactivacion}
        acciones={
          <>
            <Button
              variante="fantasma"
              onClick={cerrarReactivacion}
              disabled={actualizar.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={confirmarReactivacion}
              disabled={actualizar.isPending}
            >
              {actualizar.isPending ? "Reactivando…" : "Reactivar acceso"}
            </Button>
          </>
        }
      >
        {actualizar.isError && (
          <Alert tono="error">{mensajeDeError(actualizar.error)}</Alert>
        )}
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          ¿Deseas restaurar el acceso de <strong>{aReactivar?.email}</strong> con el rol{" "}
          <strong>{aReactivar && ETIQUETA_ROL[aReactivar.rol]}</strong>?
        </p>
      </Modal>
    </main>
  );
}
