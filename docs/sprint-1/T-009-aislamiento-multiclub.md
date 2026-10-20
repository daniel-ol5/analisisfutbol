# T-009 — Aislamiento multi-club

## Regla central

Los recursos privados se consultan mediante `app/core/tenancy.py`:

- `del_club(Modelo, usuario)` construye consultas limitadas al club de la
  identidad autenticada.
- `verificar_pertenencia(objeto, usuario)` devuelve 404 tanto para recursos
  inexistentes como para recursos de otro club.

El `club_id` de una creación se deriva de la identidad autenticada. No se
acepta como dato de entrada elegido por el cliente.

## Endpoints implementados auditados

| Endpoint | Aislamiento |
|---|---|
| `GET /api/seguridad/yo` | Busca por usuario y club mediante `del_club`; responde 404 si no coincide. |
| `GET /api/seguridad/usuarios` | Lista mediante `del_club`; requiere rol `ADMIN`. |
| `POST /api/seguridad/usuarios` | Fuerza el club de la identidad autenticada; requiere rol `ADMIN`. |
| `POST /api/seguridad/logout` | No consulta recursos persistidos. |
| `WS /api/partido/{id}/vivo` | Usa el repositorio de partidos y canales con `club_id`. |
| `POST /api/partido/{id}/token-ingesta` | Verifica el partido antes de emitir un token ligado al club y partido. |
| `WS /api/partido/{id}/ingesta` | Verifica token, partido y club; publica en un canal ligado al club. |

`registro` y `login` son públicos y anteriores a la obtención de una identidad
de club. Sus búsquedas por email son globales porque el email tiene una
restricción única global y no se conoce un club autenticado en esos flujos.

## Endpoints pendientes

Los routers de `deportivo`, `vision`, `analisis`, `asistencia` y la mayor parte
de `partido` responden 501. No acceden aún a datos y deberán auditarse al ser
implementados.

La tabla real de partidos también está pendiente. Mientras no exista,
`PartidosSinTabla` no puede validar propiedad persistida; mantiene separados
los flujos en vivo con canales `club:{club_id}:partido:{partido_id}`. Cuando se
incorpore el modelo, `PartidosEnTabla` activa la verificación centralizada sin
cambiar los endpoints.
