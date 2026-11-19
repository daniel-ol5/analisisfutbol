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

T-096 debe usar `ruta` al tocar la notificacion y aplicar el mismo comportamiento
cuando la app se encuentre en primer plano, segundo plano o cerrada. La pantalla
movil de recomendaciones aun debe ser implementada por Araceli.

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

