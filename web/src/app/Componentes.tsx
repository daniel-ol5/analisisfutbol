/**
 * Catálogo de componentes base (solo en desarrollo). Muestra cada uno en tema
 * oscuro y claro a la vez: es la documentación del sistema de diseño.
 */
import { useState } from "react";

import { Alert, Badge, Button, Input, Modal, Select, Table } from "@/shared/ui";

import "./componentes.css";

type Tema = "dark" | "light";

function Muestra({ tema }: { tema: Tema }) {
  const [modal, setModal] = useState(false);

  return (
    <section className="muestra" data-theme={tema} aria-label={`Tema ${tema === "dark" ? "oscuro" : "claro"}`}>
      <p className="kicker">Tema {tema === "dark" ? "oscuro" : "claro"}</p>

      <h3>Botones</h3>
      <div className="muestra-fila">
        <Button>Primario</Button>
        <Button variante="secundario">Secundario</Button>
        <Button variante="peligro">Peligro</Button>
        <Button variante="fantasma">Fantasma</Button>
        <Button disabled>Deshabilitado</Button>
      </div>

      <h3>Campos</h3>
      <Input etiqueta="Correo electrónico" type="email" placeholder="persona@club.com" ayuda="Usa tu correo del club." />
      <Input etiqueta="Contraseña" type="password" defaultValue="abc" error="Debe tener al menos 8 caracteres." />
      <Select etiqueta="Rol" defaultValue="ASISTENTE">
        <option value="ADMIN">ADMIN</option>
        <option value="DT">DT</option>
        <option value="ANALISTA">ANALISTA</option>
        <option value="ASISTENTE">ASISTENTE</option>
      </Select>

      <h3>Badges</h3>
      <div className="muestra-fila">
        <Badge>Neutro</Badge>
        <Badge tono="ok">Activo</Badge>
        <Badge tono="aviso">Pendiente</Badge>
        <Badge tono="info">Info</Badge>
        <Badge tono="error">Desactivado</Badge>
      </div>

      <h3>Alertas</h3>
      <Alert tono="ok" titulo="Guardado">Los cambios se aplicaron.</Alert>
      <Alert tono="aviso" titulo="Atención">Esta acción cerrará otras sesiones.</Alert>
      <Alert tono="info">Mensaje informativo.</Alert>
      <Alert tono="error" titulo="Error">Ese email ya tiene una cuenta.</Alert>

      <h3>Tabla</h3>
      <Table titulo={`Ejemplo de tabla (${tema})`}>
        <thead>
          <tr>
            <th scope="col">Nombre</th>
            <th scope="col">Rol</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Ana Pérez</td>
            <td>ADMIN</td>
            <td><Badge tono="ok">Activo</Badge></td>
          </tr>
          <tr>
            <td>Luis Gómez</td>
            <td>ASISTENTE</td>
            <td><Badge tono="error">Inactivo</Badge></td>
          </tr>
        </tbody>
      </Table>

      <h3>Modal</h3>
      <Button variante="secundario" onClick={() => setModal(true)}>
        Abrir modal
      </Button>
      <Modal
        abierto={modal}
        titulo="Confirmar acción"
        onCerrar={() => setModal(false)}
        acciones={
          <>
            <Button variante="fantasma" onClick={() => setModal(false)}>Cancelar</Button>
            <Button onClick={() => setModal(false)}>Aceptar</Button>
          </>
        }
      >
        <p>Se cierra con Esc, con el fondo o con los botones.</p>
      </Modal>
    </section>
  );
}

export function Componentes() {
  return (
    <main className="componentes">
      <p className="kicker">Sistema de diseño</p>
      <h1>Componentes</h1>
      <p className="dek">Cada componente en tema oscuro (predeterminado) y claro.</p>
      <div className="muestras">
        <Muestra tema="dark" />
        <Muestra tema="light" />
      </div>
    </main>
  );
}
