# Notificaciones push (CU-53 / T-087)

El backend envia una notificacion FCM solamente cuando el motor persiste una
recomendacion de prioridad `CRITICA`. Las reglas ordinarias de prioridad
`ALTA`, `MEDIA` o `BAJA` no generan push. Con el catalogo actual, una expulsion
genera la recomendacion critica correspondiente; las alertas de amonestaciones
y fatiga no envian push mientras conserven una prioridad menor.

## Registro del dispositivo

La app autenticada registra o actualiza su instalacion con:

```http
POST /api/asistencia/dispositivos
Authorization: Bearer <token de acceso>
Content-Type: application/json

{
  "instalacion_id": "uuid-estable-generado-por-la-app",
  "token": "token-fcm",
  "plataforma": "ANDROID"
}
```

`plataforma` acepta `ANDROID`, `IOS` o `WEB`. El usuario y el club se obtienen
exclusivamente del token de acceso; no se aceptan identificadores de otro
usuario en el cuerpo. Repetir la solicitud es idempotente y permite rotar el
token FCM de la misma instalacion.

## Payload para Flutter (T-096)

FCM recibe una notificacion visible y los siguientes datos, todos como texto:

```json
{
  "tipo": "recomendacion_tactica",
  "recomendacion_id": "42",
  "partido_id": "10",
  "prioridad": "CRITICA",
  "ruta": "/asistencia?partido_id=10&recomendacion_id=42"
}
```

`ruta` es la de la web. La app movil (T-096) arma la suya con `partido_id` y
`recomendacion_id`: abre `/partidos/{partido_id}/recomendaciones` con esa
recomendacion resaltada, con la app abierta, en segundo plano o cerrada.

## App movil (T-096)

Codigo en `movil/lib/features/asistencia/push.dart`. Solo Android.

- **Sin `google-services.json` en el repositorio.** Firebase se configura con
  cuatro valores al compilar. Sin ellos el push queda apagado y el resto de la
  app funciona igual (CI, web y quien no tenga Firebase):

  ```sh
  flutter build apk --release \
    --dart-define=API_URL=https://<servidor>/api \
    --dart-define=FIREBASE_API_KEY=<apiKey> \
    --dart-define=FIREBASE_APP_ID=<appId de la app Android> \
    --dart-define=FIREBASE_MESSAGING_SENDER_ID=<senderId> \
    --dart-define=FIREBASE_PROJECT_ID=<projectId>
  ```

  Los cuatro valores salen de la consola de Firebase: *Configuracion del
  proyecto → General → Tus apps → app Android* (`com.areatecnica.areatecnica`).
- **Registro:** con sesion iniciada, la app pide permiso de notificaciones y
  registra el token en `POST /asistencia/dispositivos`; si Firebase rota el
  token, lo vuelve a registrar.
- **Token FCM clasico** (`getToken`/`onTokenRefresh`, marcados como deprecados
  en `firebase_messaging` 17): el backend envia con `MulticastMessage(tokens=...)`
  de Firebase Admin, que espera ese token y no el ID de instalacion de
  `register()`/`onRegistered`.
- **Con la app abierta**, Android no muestra la notificacion: la app muestra un
  aviso arriba con el boton "Ver".

La entrega real se prueba en dispositivos en T-097 (casos F1 a F5 de
`docs/validacion/PLAN-PRUEBAS-DISPOSITIVOS-T097.md`).

## Configuracion del servidor

Las credenciales no se guardan en el repositorio. Firebase Admin usa
Application Default Credentials (ADC). En el entorno del proceso se configura:

```text
FIREBASE_PUSH_HABILITADO=true
FIREBASE_PROJECT_ID=<id-del-proyecto>
GOOGLE_APPLICATION_CREDENTIALS=<ruta-privada-al-json>
```

En Docker, `FIREBASE_PUSH_HABILITADO` y `FIREBASE_PROJECT_ID` ya se transfieren
al contenedor. Si se usa un JSON local, debe montarse mediante una configuracion
privada/override y `GOOGLE_APPLICATION_CREDENTIALS` debe apuntar a esa ruta
dentro del contenedor. En Google Cloud puede usarse la identidad del servicio
sin distribuir un archivo JSON.

Sin `FIREBASE_PUSH_HABILITADO=true`, el motor sigue funcionando pero no intenta
enviar notificaciones. Los errores de FCM quedan registrados sin interrumpir la
ingesta. Un token que FCM reporte como no registrado o perteneciente a otro
proyecto queda inactivo hasta que la app lo actualice.

## Verificacion pendiente

Las pruebas automatizadas usan un proveedor simulado y cubren destinatarios,
aislamiento entre clubes, duplicados, tokens invalidos, errores y payload. La
entrega real debe comprobarse con un proyecto Firebase y dispositivos fisicos
cuando T-096 este integrada; esa prueba no requiere subir credenciales al repo.

