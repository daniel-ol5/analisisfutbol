import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  activarPushWeb,
  pushWebDisponible,
  suscribirMensajesPrimerPlano,
  type NotificacionPushWeb,
} from "../webPush";

/**
 * Control en la barra superior para activar notificaciones push Web (FCM)
 * y mostrar avisos en primer plano cuando llega un evento del club.
 */
export function NotificacionesWeb({ usuarioId }: { usuarioId: number | undefined }) {
  const navigate = useNavigate();
  const disponible = pushWebDisponible();
  const [permiso, setPermiso] = useState<NotificationPermission>(() =>
    disponible ? Notification.permission : "denied",
  );
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<NotificacionPushWeb | null>(null);

  useEffect(() => {
    if (!disponible || !usuarioId) return;
    let cancelar: (() => void) | undefined;
    let activo = true;

    if (Notification.permission === "granted") {
      void activarPushWeb(false)
        .then((p) => {
          if (activo) setPermiso(p);
        })
        .catch(() => {});
    }

    void suscribirMensajesPrimerPlano((n) => {
      if (!activo) return;
      setAviso(n);
    })
      .then((unsub) => {
        if (activo) cancelar = unsub;
        else unsub();
      })
      .catch(() => {});

    return () => {
      activo = false;
      cancelar?.();
    };
  }, [disponible, usuarioId]);

  useEffect(() => {
    if (!aviso) return;
    const t = window.setTimeout(() => setAviso(null), 9000);
    return () => window.clearTimeout(t);
  }, [aviso]);

  if (!disponible || !usuarioId) return null;

  async function solicitar() {
    setOcupado(true);
    try {
      const p = await activarPushWeb(true);
      setPermiso(p);
    } catch {
      // Si el navegador bloquea el Service Worker o no hay red, no rompe la barra.
    } finally {
      setOcupado(false);
    }
  }

  return (
    <>
      {permiso === "default" && (
        <button
          type="button"
          className="ui-btn ui-btn--secundario layout-push-btn"
          onClick={() => void solicitar()}
          disabled={ocupado}
          title="Activar notificaciones push en este navegador"
        >
          {ocupado ? "Activando..." : "Activar alertas"}
        </button>
      )}
      {permiso === "granted" && (
        <span
          className="layout-push-estado"
          title="Notificaciones push activas en este navegador"
        >
          Alertas activas
        </span>
      )}
      {aviso && (
        <div className="layout-push-toast" role="status" aria-live="polite">
          <div className="layout-push-toast-texto">
            <strong>{aviso.titulo}</strong>
            {aviso.cuerpo && <p>{aviso.cuerpo}</p>}
          </div>
          <div className="layout-push-toast-acciones">
            {aviso.ruta && (
              <button
                type="button"
                className="ui-btn ui-btn--primario"
                onClick={() => {
                  const destino = aviso.ruta;
                  setAviso(null);
                  if (destino) navigate(destino);
                }}
              >
                Ver
              </button>
            )}
            <button
              type="button"
              className="ui-btn ui-btn--secundario"
              onClick={() => setAviso(null)}
              aria-label="Cerrar notificación"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </>
  );
}
