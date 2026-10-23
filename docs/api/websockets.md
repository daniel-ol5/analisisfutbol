# Contrato de WebSockets

OpenAPI no describe WebSockets, así que su contrato vive acá. Implementación:
`backend/app/partido/router.py`, `backend/app/core/ws.py` y
`backend/app/core/realtime.py`.

| Canal | Quién se conecta | Estado |
|---|---|---|
| `ws://<host>/api/partido/{partido_id}/vivo` | Panel web, app del DT, app del asistente | ✅ T-032 |
| `ws://<host>/api/partido/{partido_id}/ingesta` | Worker de visión / emisor simulado | ✅ T-033 |

En producción, con HTTPS, se usa `wss://`.

---

## Autenticación: primer mensaje

El navegador no permite enviar el header `Authorization` en un WebSocket, y un
token en la URL queda guardado en los logs de acceso. Por eso el servidor
**acepta la conexión y espera que el primer mensaje sea la autenticación**:

```json
{ "tipo": "auth", "token": "<access_token>" }
```

- `token` es el mismo `access_token` que devuelve `POST /api/seguridad/login`.
  El `refresh_token` **no** sirve.
- Hay **5 segundos** para enviarlo. Si no llega, se cierra con `4408`.
- El club se toma del token, nunca de lo que mande el cliente.
- `/ingesta` no acepta el token de un usuario: usa un **token de ingesta**
  (ver más abajo). Y `/vivo` no acepta un token de ingesta.

## Canal `/vivo`

### Flujo

```
cliente                                  servidor
   │── abre ws://…/api/partido/42/vivo ──▶│  accept
   │── {"tipo":"auth","token":"…"} ──────▶│  valida el token (≤ 5 s)
   │                                      │  verifica que el partido 42 sea del club
   │◀──────── {"tipo":"listo","partido":42}│
   │◀──────── mensajes difundidos ────────│  (5 por segundo durante el partido)
   │── {"tipo":"ping"} ──────────────────▶│
   │◀──────── {"tipo":"pong"} ────────────│
```

### Mensajes del servidor

| `tipo` | Cuándo | Contenido |
|---|---|---|
| `listo` | Tras autenticar y verificar el partido | `{"tipo": "listo", "partido": 42}` |
| `pong` | Respuesta a un `ping` | `{"tipo": "pong"}` |
| `posiciones` | Cada mensaje válido que publica el worker (5 por segundo) | `{"tipo": "posiciones", "datos": <MensajeWorker>}` |

### Mensajes del cliente

Después de autenticarse, el cliente solo escucha. Lo único que se atiende es
`{"tipo": "ping"}`, útil en el móvil para detectar una red caída. Cualquier
otro mensaje se ignora sin cerrar la conexión.

## Códigos de cierre

| Código | Significado | `reason` | ¿Reintentar? |
|---|---|---|---|
| `1000` | Cierre normal | — | No |
| `4400` | El primer mensaje no es JSON o no es `{"tipo": "auth"}` | `El primer mensaje debe ser …` | No, es un error del cliente |
| `4401` | Falta el token | `Falta el token de acceso` | Tras volver a iniciar sesión |
| `4401` | Token inválido, expirado o de refresco | `Token inválido o expirado` | Tras renovar el token |
| `4404` | El partido no existe **o es de otro club** | `Partido no encontrado` | No |
| `4408` | No llegó la autenticación en 5 s | `No se recibió la autenticación a tiempo` | Sí |
| `1006` | Conexión perdida (red) | — | Sí, con espera creciente |

`4404` es el mismo para "no existe" y "es de otro club" **a propósito**: si
fueran distintos, un usuario podría averiguar qué partidos tienen otros clubes
probando números (misma regla que `verificar_pertenencia` en `core/tenancy.py`).

Si el `partido_id` de la URL no es un número, FastAPI rechaza el handshake antes
de aceptarlo y el cliente solo ve un error de conexión.

## Canal `/ingesta`

Lo usa el worker de visión para publicar las posiciones del partido en metros.
`backend/scripts/emisor_simulado.py` es el cliente de referencia: implementa
este canal completo y sirve para probar sin el worker (ver el README). Todo lo válido se difunde al canal `/vivo`
del mismo partido y se guarda por lotes.

### Token de ingesta

El worker no inicia sesión como una persona: el access token dura 15 minutos y
un partido, 90. Un ADMIN o un ANALISTA pide un token válido para **un solo
partido** y por **4 horas**:

```http
POST /api/partido/42/token-ingesta
Authorization: Bearer <access_token de ADMIN o ANALISTA>
```

```json
{ "token": "eyJ…", "partido_id": 42, "expira_en": "2026-10-18T23:15:00Z" }
```

| Respuesta | Cuándo |
|---|---|
| `201` | Token emitido |
| `401` | Sin token, o token inválido o expirado |
| `403` | El rol no es ADMIN ni ANALISTA |
| `404` | El partido no existe o es de otro club |

Si el token se filtra, solo sirve para publicar en ese partido y hasta que
expire. No se puede revocar antes (no hay lista negra todavía).

### Flujo

```
worker                                   servidor
   │── abre ws://…/api/partido/42/ingesta ─▶│  accept
   │── {"tipo":"auth","token":"<ingesta>"} ─▶│  token de ingesta del partido 42 (≤ 5 s)
   │◀───────── {"tipo":"listo","partido":42}│
   │── MensajeWorker ───────────────────────▶│  válido: se difunde a /vivo y se guarda
   │── MensajeWorker ───────────────────────▶│  (sin respuesta: a 5 Hz sería ruido)
   │── {basura} ────────────────────────────▶│
   │◀──── {"tipo":"error","detalle":[…],…} ──│  inválido: se avisa y se sigue
```

### Mensaje del worker: `MensajeWorker`

Es el schema `MensajeWorker` de `docs/api/openapi.json`
(`backend/app/partido/schemas.py`). Se envía **sin** campo `tipo`:

```json
{
  "partido": 42,
  "t": 1873.4,
  "jugadores": [
    {"tid": 7,  "equipo": "LOCAL",     "x": 52.3, "y": 31.8, "conf": 0.91},
    {"tid": 12, "equipo": "VISITANTE", "x": 61.0, "y": 44.2, "conf": 0.88}
  ],
  "balon": {"tid": 0, "equipo": "DESCONOCIDO", "x": 55.1, "y": 33.0, "conf": 0.62},
  "calidad": {"worker_conectado": true, "fps": 5.0, "jugadores_detectados": 21,
              "balon_visible": true, "retraso_s": 0.4, "degradado": false}
}
```

| Campo | Regla |
|---|---|
| `partido` | Debe coincidir con el de la URL |
| `t` | Segundos desde el inicio del partido |
| `x`, `y` | Metros sobre el largo y el ancho de la cancha |
| `conf` | Entre 0 y 1 |
| `equipo` | `LOCAL`, `VISITANTE`, `ARBITRO` o `DESCONOCIDO` |
| `balon` | Opcional (`null` si no se ve) |

### Respuesta a un mensaje inválido

```json
{
  "tipo": "error",
  "invalidos_seguidos": 1,
  "detalle": [
    {"type": "less_than_equal", "loc": ["jugadores", 0, "conf"], "msg": "Input should be less than or equal to 1"},
    {"type": "missing", "loc": ["calidad"], "msg": "Field required"}
  ]
}
```

`detalle` es la lista de errores de Pydantic (`type`, `loc`, `msg`, y a veces
`ctx`). Además de los de Pydantic, hay dos tipos propios:

| `type` | Cuándo |
|---|---|
| `partido_distinto` | `partido` del mensaje distinto del de la URL |
| `binario` | Llegó un frame binario en vez de texto JSON |

La conexión **sigue abierta**: un fotograma corrupto no tumba al worker. Pero
con **50 inválidos seguidos** (`MAX_INVALIDOS_SEGUIDOS` en
`app/partido/router.py`) se cierra con `4400`. Un mensaje válido reinicia la
cuenta.

### Persistencia

Las posiciones se insertan **por lotes de 25 mensajes** (5 s, unas 575 filas)
con un único INSERT masivo, y lo pendiente se guarda al desconectarse el
worker. Si la base falla, se pierde ese lote pero la difusión en vivo sigue.

> ⚠️ **Provisorio:** la tabla `posicion` todavía no existe (necesita la tabla
> `partido`, T-047). Hasta entonces las posiciones **se difunden pero no se
> guardan**. Se activa cambiando `MODELO_POSICION` en
> `app/partido/service.py`.

### Códigos de cierre de `/ingesta`

Los mismos de la tabla general, con estos matices:

| Código | En `/ingesta` |
|---|---|
| `4400` | Además: 50 mensajes inválidos seguidos |
| `4401` | Token de usuario en vez de token de ingesta, o token inválido o expirado |
| `4404` | El token es de otro partido, o el partido no existe o es de otro club |

---

## Ejemplo de cliente (JavaScript)

Sirve tal cual en la web (React) y en cualquier entorno con `WebSocket` estándar.
En Flutter el protocolo es el mismo con `web_socket_channel`: enviar el `auth`
como primer mensaje y leer `closeCode` / `closeReason` al cerrarse.

```js
const NO_REINTENTAR = new Set([1000, 4400, 4401, 4404]);

export function escucharPartido({ baseUrl, partidoId, obtenerToken, onMensaje, onCierre }) {
  let ws;
  let intento = 0;
  let cerradoAMano = false;
  let latido;

  function abrir() {
    // baseUrl: "ws://localhost:8000/api"  (o "wss://…" en producción)
    ws = new WebSocket(`${baseUrl}/partido/${partidoId}/vivo`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ tipo: "auth", token: obtenerToken() }));
    };

    ws.onmessage = (evento) => {
      const mensaje = JSON.parse(evento.data);
      if (mensaje.tipo === "listo") {
        intento = 0;
        latido = setInterval(() => ws.send(JSON.stringify({ tipo: "ping" })), 20_000);
        return;
      }
      if (mensaje.tipo === "pong") return;
      onMensaje(mensaje);
    };

    ws.onclose = (evento) => {
      clearInterval(latido);
      onCierre?.(evento.code, evento.reason);
      if (cerradoAMano || NO_REINTENTAR.has(evento.code)) return;
      // 1006 (red) o 4408 (timeout): reintento con espera creciente, máx. 30 s
      const espera = Math.min(30_000, 1_000 * 2 ** intento++);
      setTimeout(abrir, espera);
    };
  }

  abrir();
  return () => { cerradoAMano = true; ws.close(1000); };
}
```

Uso:

```js
const dejarDeEscuchar = escucharPartido({
  baseUrl: "ws://localhost:8000/api",
  partidoId: 42,
  obtenerToken: () => sesion.accessToken,
  onMensaje: (m) => {
    if (m.tipo === "posiciones") dibujar(m.datos.jugadores, m.datos.balon, m.datos.calidad);
  },
  onCierre: (code, reason) => {
    if (code === 4401) irAlLogin();
    if (code === 4404) mostrar("Ese partido no existe");
  },
});
```

---

## Notas de implementación

- **Canales aislados por club.** El canal interno es
  `club:{club_id}:partido:{partido_id}`, con el club tomado del token. Aunque la
  verificación del partido fallara, dos clubes nunca comparten canal.
- **Mientras no exista la tabla `partido`** (T-047), el backend acepta cualquier
  `partido_id` (`PartidosSinTabla` en `app/partido/service.py`) y el aislamiento
  lo garantiza el canal por club. Cuando exista, se activa la verificación real
  cambiando `MODELO_PARTIDO` en ese mismo archivo, y empieza a responder `4404`.
- **Un solo proceso por ahora.** El Hub vive en memoria (`HubMemoria`). Para
  escalar a varias instancias se implementa la misma interfaz `Hub` sobre Redis
  pub/sub y se cambia solo `obtener_hub()` en `app/core/realtime.py`.
- Un cliente que tarda más de 2 s en recibir un mensaje se desconecta del canal,
  para no frenar a los demás.
