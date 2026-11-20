/**
 * Cliente de notificaciones push Web (Firebase Cloud Messaging).
 *
 * Se activa únicamente cuando las variables `VITE_FIREBASE_*` están presentes
 * en el build y el navegador soporta Notification + ServiceWorker. En CI, tests
 * o desarrollo sin Firebase queda desactivado sin afectar la app.
 */
import { getApp, getApps, initializeApp } from "@firebase/app";
import {
  getMessaging,
  getToken,
  isSupported,
  onMessage,
  type Messaging,
} from "@firebase/messaging";

import { env } from "@/shared/config/env";

import { registrarDispositivoPush } from "./api";

const CLAVE_INSTALACION = "areatecnica.push-instalacion-id";

export interface NotificacionPushWeb {
  id: number;
  titulo: string;
  cuerpo: string;
  ruta?: string;
}

export function pushWebConfigurado(): boolean {
  const f = env.firebase;
  return Boolean(f.apiKey && f.appId && f.messagingSenderId && f.projectId && f.vapidKey);
}

export function pushWebDisponible(): boolean {
  return (
    pushWebConfigurado() &&
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator
  );
}

function obtenerInstalacionId(): string {
  try {
    const existente = localStorage.getItem(CLAVE_INSTALACION);
    if (existente) return existente;
    const nuevo =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(CLAVE_INSTALACION, nuevo);
    return nuevo;
  } catch {
    return `web-${Date.now()}`;
  }
}

async function obtenerMessaging(): Promise<Messaging | null> {
  if (!pushWebDisponible()) return null;
  if (!(await isSupported())) return null;
  const { apiKey, appId, messagingSenderId, projectId } = env.firebase;
  const app = getApps().length
    ? getApp()
    : initializeApp({ apiKey, appId, messagingSenderId, projectId });
  return getMessaging(app);
}

async function esperarSwActivo(reg: ServiceWorkerRegistration): Promise<ServiceWorkerRegistration> {
  if (reg.active) return reg;
  const sw = reg.installing ?? reg.waiting;
  if (!sw) return reg;
  await new Promise<void>((resolve) => {
    const alCambiar = () => {
      if (sw.state === "activated" || sw.state === "redundant") {
        sw.removeEventListener("statechange", alCambiar);
        resolve();
      }
    };
    sw.addEventListener("statechange", alCambiar);
  });
  return reg;
}

async function registrarServiceWorker(): Promise<ServiceWorkerRegistration> {
  const { apiKey, appId, messagingSenderId, projectId } = env.firebase;
  const qs = new URLSearchParams({ apiKey, appId, messagingSenderId, projectId });
  const reg = await navigator.serviceWorker.register(
    `/assets/firebase-messaging-sw.js?${qs.toString()}`,
    { scope: "/assets/" },
  );
  return esperarSwActivo(reg);
}

/**
 * Solicita permiso (si hace falta), obtiene el token FCM del navegador y lo
 * registra en el backend con plataforma "WEB".
 */
export async function activarPushWeb(pedirPermiso: boolean): Promise<NotificationPermission> {
  if (!pushWebDisponible()) return "denied";
  let permiso = Notification.permission;
  if (permiso === "default" && pedirPermiso) {
    permiso = await Notification.requestPermission();
  }
  if (permiso !== "granted") return permiso;

  const messaging = await obtenerMessaging();
  if (!messaging) return "denied";

  const registration = await registrarServiceWorker();
  const token = await getToken(messaging, {
    vapidKey: env.firebase.vapidKey,
    serviceWorkerRegistration: registration,
  });
  if (token) {
    await registrarDispositivoPush(obtenerInstalacionId(), token, "WEB");
  }
  return permiso;
}

/**
 * Escucha notificaciones mientras la pestaña está abierta (primer plano).
 * Devuelve una función para cancelar la suscripción.
 */
export async function suscribirMensajesPrimerPlano(
  alRecibir: (n: NotificacionPushWeb) => void,
): Promise<() => void> {
  const messaging = await obtenerMessaging();
  if (!messaging) return () => {};
  return onMessage(messaging, (payload) => {
    const titulo = payload.notification?.title ?? payload.data?.["titulo"] ?? "Área Técnica";
    const cuerpo = payload.notification?.body ?? payload.data?.["cuerpo"] ?? "";
    const ruta = payload.data?.["ruta"];
    alRecibir({ id: Date.now(), titulo, cuerpo, ruta });

    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      try {
        new Notification(titulo, { body: cuerpo, icon: "/favicon.svg" });
      } catch {
        // Algunos navegadores bloquean new Notification() si solo permiten SW.
      }
    }
  });
}
