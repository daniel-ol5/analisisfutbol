import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useEffectEvent, useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { mensajeDeError } from "@/shared/lib/errors";
import { Alert, Badge, Button } from "@/shared/ui";
import { Icono } from "@/shared/ui/Icono";

import { AVISO_ALCANCE, CLAVE_PROGRESO } from "../constantes";
import { LARGO_MAX_PREGUNTA, MAX_HISTORIAL, obtenerProgreso, preguntar } from "../api";
import { consumirPreguntaInicial, guardarHistorial, leerHistorial } from "../estado";
import type { MensajeChat, MensajeHistorial, Progreso } from "../types";
import "../asistente.css";


let contador = 0;
function nuevoId() {
  contador += 1;
  return `m${Date.now()}-${contador}`;
}

function TuProgreso({ progreso }: { progreso: Progreso }) {
  const { siguiente } = progreso;
  const hechos = progreso.pasos.filter((p) => p.estado === "hecho").length;
  const total = progreso.pasos.filter((p) => p.disponible).length;
  return (
    <section className="asi-progreso" aria-labelledby="asi-progreso-titulo">
      <h3 id="asi-progreso-titulo">
        Tu progreso <span className="asi-progreso-cuenta">{`${hechos} de ${total}`}</span>
      </h3>
      <ol className="asi-pasos">
        {progreso.pasos.map((paso) => (
          <li
            key={paso.clave}
            className={`asi-paso asi-paso--${paso.disponible ? paso.estado : "no-disponible"}${
              siguiente?.clave === paso.clave ? " asi-paso--siguiente" : ""
            }`}
          >
            <span className="asi-paso-marca" aria-hidden="true">
              {paso.estado === "hecho" ? "✓" : ""}
            </span>
            <span className="asi-paso-titulo">{paso.titulo}</span>
            <span className="ui-solo-lectores">
              {paso.disponible ? (paso.estado === "hecho" ? " (hecho)" : " (pendiente)") : " (no disponible)"}
            </span>
          </li>
        ))}
      </ol>
      {siguiente ? (
        <div className="asi-siguiente">
          <p>
            <strong>Siguiente paso:</strong> {siguiente.titulo}
          </p>
          {siguiente.ruta ? (
            <Link className="ui-btn ui-btn--primario" to={siguiente.ruta}>
              Ir al siguiente paso
            </Link>
          ) : (
            siguiente.nota && <p className="asi-nota">{siguiente.nota}</p>
          )}
        </div>
      ) : (
        <p className="asi-nota">¡Completaste todos los pasos disponibles!</p>
      )}
    </section>
  );
}

interface Props {
  usuarioId: number | undefined;
  pantallaActual: string;
  preguntaInicial: string | null;
  onCerrar: () => void;
}

/** Panel lateral del asistente: «Tu progreso» y el chat de dudas de uso. */
export function PanelAsistente({ usuarioId, pantallaActual, preguntaInicial, onCerrar }: Props) {
  const idTitulo = useId();
  const idCampo = useId();
  const [mensajes, setMensajes] = useState<MensajeChat[]>(() => leerHistorial(usuarioId));
  const [texto, setTexto] = useState("");
  const finChat = useRef<HTMLDivElement>(null);
  const progreso = useQuery({ queryKey: CLAVE_PROGRESO, queryFn: obtenerProgreso, staleTime: 0 });
  const envio = useMutation({
    mutationFn: preguntar,
    onMutate: ({ pregunta }) =>
      setMensajes((previos) => [...previos, { id: nuevoId(), rol: "usuario", texto: pregunta }]),
    onSuccess: (r) =>
      setMensajes((previos) => [
        ...previos,
        { id: nuevoId(), rol: "asistente", texto: r.respuesta, acciones: r.acciones },
      ]),
  });
  const chatActivo = progreso.data?.asistente_activo !== false;

  useEffect(() => {
    guardarHistorial(usuarioId, mensajes);
    finChat.current?.scrollIntoView?.({ block: "end" });
  }, [usuarioId, mensajes]);

  /** Envía la pregunta con los últimos mensajes como historial. */
  function enviar(pregunta: string): boolean {
    const limpia = pregunta.trim();
    if (!limpia || envio.isPending) return false;
    const historial: MensajeHistorial[] = mensajes
      .slice(-MAX_HISTORIAL)
      .map(({ rol, texto: t }) => ({ rol, texto: t }));
    envio.mutate({ pregunta: limpia, pantalla_actual: pantallaActual, plataforma: "web", historial });
    return true;
  }

  function enviarTexto() {
    if (enviar(texto)) setTexto("");
  }

  // «¿Cómo se usa esto?»: la pregunta llega con el panel y se envía una sola vez.
  const enviarInicial = useEffectEvent((pregunta: string) => enviar(pregunta));
  useEffect(() => {
    if (!preguntaInicial) return;
    consumirPreguntaInicial();
    enviarInicial(preguntaInicial);
  }, [preguntaInicial]);

  function alEnviar(evento: FormEvent) {
    evento.preventDefault();
    enviarTexto();
  }

  return (
    <aside className="asi-panel" role="dialog" aria-modal="false" aria-labelledby={idTitulo}>
      <header className="asi-cabecera">
        <h2 id={idTitulo}>Asistente</h2>
        <button type="button" className="asi-cerrar" onClick={onCerrar} aria-label="Cerrar asistente">
          <Icono nombre="cerrar" />
        </button>
      </header>

      <div className="asi-cuerpo">
        {progreso.isPending && <p className="asi-nota">Cargando tu progreso…</p>}
        {progreso.isError && (
          <Alert tono="error">No pudimos cargar tu progreso. {mensajeDeError(progreso.error)}</Alert>
        )}
        {progreso.data && <TuProgreso progreso={progreso.data} />}

        <section className="asi-chat" aria-label="Chat con el asistente">
          <p className="asi-aviso">
            <Badge tono="info">IA</Badge> {AVISO_ALCANCE}
          </p>
          <div className="asi-mensajes" aria-live="polite">
            {mensajes.length === 0 && (
              <p className="asi-nota">
                Pregúntame, por ejemplo, «¿cuál es mi siguiente paso?» o «¿por qué hay que
                calibrar la cámara?».
              </p>
            )}
            {mensajes.map((m) => (
              <div key={m.id} className={`asi-mensaje asi-mensaje--${m.rol}`}>
                <p>{m.texto}</p>
                {m.acciones && m.acciones.length > 0 && (
                  <div className="asi-acciones">
                    {m.acciones.map((a) => (
                      <Link key={`${a.ruta}-${a.texto}`} className="ui-btn ui-btn--secundario" to={a.ruta}>
                        {a.texto}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {envio.isPending && (
              <p className="asi-escribiendo" role="status">
                El asistente está escribiendo…
              </p>
            )}
            {envio.isError && (
              <Alert tono="aviso" titulo="No pudimos responder">
                {mensajeDeError(envio.error)}
              </Alert>
            )}
            <div ref={finChat} />
          </div>

          {chatActivo ? (
            <form className="asi-formulario" onSubmit={alEnviar}>
              <label htmlFor={idCampo} className="ui-solo-lectores">
                Tu pregunta
              </label>
              <textarea
                id={idCampo}
                className="asi-campo"
                rows={2}
                maxLength={LARGO_MAX_PREGUNTA}
                placeholder="Escribe tu duda sobre Área Técnica"
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    enviarTexto();
                  }
                }}
              />
              <div className="asi-formulario-pie">
                <span className="asi-contador">{`${texto.length}/${LARGO_MAX_PREGUNTA}`}</span>
                <Button type="submit" disabled={!texto.trim() || envio.isPending}>
                  Enviar
                </Button>
              </div>
            </form>
          ) : (
            <Alert tono="aviso">
              El chat no está disponible en este momento. Puedes seguir los pasos de «Tu progreso».
            </Alert>
          )}
        </section>
      </div>
    </aside>
  );
}
