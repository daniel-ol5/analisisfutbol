/* Service Worker para notificaciones push de Firebase Cloud Messaging (Web). */
/* eslint-disable no-undef */
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

const params = new URL(self.location.href).searchParams;
const apiKey = params.get("apiKey");
const projectId = params.get("projectId");
const messagingSenderId = params.get("messagingSenderId");
const appId = params.get("appId");

if (apiKey && projectId && messagingSenderId && appId) {
  firebase.initializeApp({ apiKey, projectId, messagingSenderId, appId });
  const messaging = firebase.messaging();

  // Si el payload ya trae `notification`, Firebase SW la muestra automáticamente.
  // Solo mostramos manualmente cuando llega un mensaje solo de `data`.
  messaging.onBackgroundMessage((payload) => {
    if (payload.notification) return;
    const titulo = (payload.data && payload.data.titulo) || "Área Técnica";
    const cuerpo = (payload.data && payload.data.cuerpo) || "Nueva actualización del club";
    self.registration.showNotification(titulo, {
      body: cuerpo,
      icon: "/favicon.svg",
      data: payload.data || {},
    });
  });
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const ruta = data.ruta || (data.FCM_MSG && data.FCM_MSG.data && data.FCM_MSG.data.ruta) || "/";
  const destino = new URL(ruta, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
      for (const ventana of ventanas) {
        if ("focus" in ventana) {
          ventana.focus();
          if ("navigate" in ventana) return ventana.navigate(destino);
          return ventana;
        }
      }
      return self.clients.openWindow(destino);
    }),
  );
});
