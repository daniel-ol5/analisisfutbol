# Área Técnica

Sistema de análisis táctico de fútbol por visión computacional. Monitorea un
partido desde una cámara fija y entrega recomendaciones tácticas justificadas al
entrenador, en vivo y sobre partidos grabados.

Proyecto de Ingeniería de Software · Scrum · Equipo de 6.

---

## Arrancar en un comando

```bash
docker compose up --build
```

| Servicio | URL | Qué es |
|---|---|---|
| **API** | http://localhost:8000/api/docs | FastAPI con recarga en caliente |
| **Mock** | http://localhost:4010 | El contrato congelado, responde todo |
| PostgreSQL | localhost:5432 | usuario/clave/base: `areatecnica` |
| Redis | localhost:6379 | |

En el primer arranque se aplican las migraciones y se crea un club ficticio de
desarrollo. Se puede iniciar sesión con `admin@club-demo.example.com` y la clave
`Demo-Area-Tecnica-2026`. Para cambiarla sin editar archivos, define
`DEMO_ADMIN_PASSWORD` antes de levantar Compose. El seed solo funciona con
`APP_ENV=development` y no duplica registros en arranques posteriores.

Para comprobar y detener el entorno sin borrar los datos:

```bash
docker compose ps
docker compose logs --tail=100
docker compose down
```

`docker compose down` conserva el volumen de PostgreSQL; no uses `-v` si
quieres mantener los datos.

El **worker de visión no está en Docker**: corre fuera, en la máquina con GPU,
por los controladores de NVIDIA. Ver [vision/README.md](vision/README.md).

### Sin Docker

```bash
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

```bash
cd web
npm install
copy .env.example .env.local
npm run dev            # http://localhost:5173
```

```bash
cd movil
flutter pub get
flutter run --dart-define=API_URL=http://10.0.2.2:8000/api
```

`10.0.2.2` es el alias del emulador de Android hacia el localhost de tu máquina.
Para un dispositivo físico, usá la IP de tu red local. Para trabajar contra el
mock, cambiá el puerto a `4010`.

---

## El contrato de la API

[`docs/api/openapi.json`](docs/api/openapi.json) es el **contrato congelado**:
55 rutas, 71 operaciones y 84 esquemas cubriendo los 6 paquetes. De ahí sale el
mock, y del mock sale que Web y Móvil **nunca esperen al backend**.

Los endpoints que todavía no están implementados devuelven **501** con el caso
de uso, el sprint y el responsable:

```json
{ "detail": "CU-09 pendiente · Sprint 2 · responsable: Daniel" }
```

**Mientras tu caso de uso devuelva 501**, apuntá al mock en `web/.env.local`:

```
VITE_API_URL=http://127.0.0.1:4010/api
```

Cuando el backend lo implemente, volvés a la API real cambiando esa línea. Nada
más.

### Migraciones

El esquema lo gestiona Alembic, no la aplicación. Docker aplica las migraciones
pendientes al levantar el servicio `api`; sin Docker:

```bash
cd backend
alembic upgrade head                                   # aplicar
alembic revision --autogenerate -m "descripcion"       # crear una nueva
alembic downgrade -1                                   # revertir la ultima
```

Al agregar modelos a un paquete, importarlo en `alembic/env.py` para que
autogenerate los detecte.

### Emisor simulado (sin GPU)

Mientras el worker de visión no exista, `backend/scripts/emisor_simulado.py`
publica posiciones plausibles de 22 jugadores y el balón en
`/api/partido/{id}/ingesta`, a 5 mensajes por segundo. El panel en vivo de Web
y Móvil (`/api/partido/{id}/vivo`) las recibe como si vinieran de la cámara.
No necesita GPU, video ni nada fuera de `requirements.txt`.

1. Levantar la API (`docker compose up`, o `uvicorn` sin Docker).
2. Crear una cuenta, si no se tiene: en http://localhost:8000/api/docs, usar
   `POST /api/seguridad/registro`. Esa cuenta es ADMIN; también sirve una
   ANALISTA.
3. Correr el emisor:

```bash
cd backend
python scripts/emisor_simulado.py --partido 1 --email admin@miclub.com --password mi-clave
```

El emisor inicia sesión, pide el token de ingesta del partido y emite durante
60 s, mostrando el avance cada 5 s. Mientras tanto, abrir el panel en vivo del
partido 1 en Web o Móvil.

| Opción | Por defecto | Para qué |
|---|---|---|
| `--url` | `http://localhost:8000/api` | Otra máquina o puerto (en Windows, si tarda en conectar, probar `http://127.0.0.1:8000/api`) |
| `--partido` | *(obligatorio)* | Id del partido |
| `--duracion` | `60` | Segundos a emitir |
| `--frecuencia` | `5` | Mensajes por segundo |
| `--email` / `--password` | — | Cuenta ADMIN o ANALISTA del club |
| `--token` | — | Token de ingesta ya emitido, en vez de email y contraseña |
| `--largo` / `--ancho` | `105` / `68` | Medidas de la cancha en metros |
| `--semilla` | aleatoria | Repetir exactamente la misma simulación |
| `--inicio-t` | `0` | Empezar en otro minuto, p. ej. `2700` para el 2do tiempo |

Simula un 4-4-2 (local) contra un 4-3-3 (visitante). Los equipos basculan hacia
el balón, el que tiene la pelota se adelanta, el más cercano presiona, y hay
pases, pérdidas y remates. Las velocidades son humanas (máximo 8 m/s), con
unos 11 km por jugador cada 90 minutos.

> Mientras no exista la tabla `partido` (T-047), cualquier número de partido
> sirve, y las posiciones se ven en vivo pero no se guardan.

### Si cambiás un router o un schema

```bash
cd backend
python scripts/exportar_openapi.py
```

y commiteá `docs/api/openapi.json` junto al cambio. **La CI verifica que esté al
día** y falla el PR si no lo está. Un cambio al contrato se avisa a las dos
parejas antes de mergear.

---

## Estructura

```
Deportivo/
├─ vision/     Worker de visión — YOLO, ByteTrack, homografía (necesita GPU)
├─ backend/    FastAPI — los 6 paquetes
├─ web/        React + TypeScript + Vite — las 6 features
├─ movil/      Flutter — las 6 features
└─ docs/
   ├─ api/openapi.json            contrato congelado
   ├─ diagramas/                  modelo de datos en PlantUML
   ├─ adr/                        decisiones de arquitectura
   └─ Sprint-Planning-*.xlsx      108 tareas en 4 sprints
```

Backend y Web están organizados en los **mismos 6 paquetes** del modelo de casos
de uso:

| Paquete | Casos de uso | Contenido |
|---|---|---|
| `seguridad` | CU-01 … CU-08 | Acceso, usuarios, roles, auditoría |
| `deportivo` | CU-09 … CU-17 | Equipos, plantel, partidos, alineaciones |
| `vision` | CU-18 … CU-29 | Calibración, modelos, video grabado |
| `partido` | CU-30 … CU-39 | Captura en vivo, eventos manuales |
| `analisis` | CU-40 … CU-48 | Métricas y visualizaciones |
| `asistencia` | CU-49 … CU-58 | Reglas, recomendaciones, informes |

---

## Convenciones

**Backend — las capas de cada paquete.** `router.py` traduce HTTP a llamadas de
servicio y **no toca la base de datos**; `service.py` tiene la lógica y **no
conoce FastAPI**. Así el motor de reglas se prueba sin levantar el servidor.

**Toda consulta filtrada por club pasa por `core/tenancy.py`.** Repetir el filtro
a mano en cada endpoint es exactamente como se filtran datos entre clubes sin
querer (`Pb-03`).

**Web — importaciones siempre con el alias `@/`**, nunca rutas relativas largas:

```ts
import { api } from "@/shared/api/client";      // así
import { api } from "../../shared/api/client";  // no
```

**Una feature no importa de otra feature.** Si `analisis` necesita algo de
`partido`, ese algo sube a `shared/`.

---

## Cómo trabajamos

**Ramas.** `main` protegida. Una por historia: `feat/Pb-21-calibracion-camara`.

**Commits.** `feat(vision): proyectar detecciones al plano de cancha`

**Pull Requests.** Obligatorios, con una aprobación de alguien distinto al autor
y la CI en verde. Nadie mergea su propio PR. Un PR abierto se revisa en menos de
24 h: uno estancado bloquea a otra persona.

### Antes de abrir el PR

```bash
cd backend && python -m ruff check app tests && python -m pytest
cd web && npm run lint && npm run build
cd movil && flutter analyze
```

---

## Nunca al repositorio

- **Pesos de modelos** (`.pt`, `.onnx`) — van a almacenamiento de objetos
- **Video de partidos** — un partido completo son varios GB
- **Secretos** (`.env`, claves, tokens) — se gestionan en el proveedor

Si alguno entra al historial, queda ahí para siempre aunque se borre después.

---

## Estado

**Implementado**

- Registro de club, login, logout y control de acceso por rol (`CU-01`…`CU-04`)
- Aislamiento entre clubes con prueba automatizada (`Pb-03`)
- Contrato OpenAPI completo de los 6 paquetes + mock server
- Docker Compose, CI con lint, pruebas, verificación del contrato y de diagramas
- Web conectada al backend, con las 6 secciones enrutadas

- Migraciones con Alembic, con downgrade probado
- App Flutter con las 6 features enrutadas y conexión al backend

**Pendiente**

- Modelos de datos de 5 de los 6 paquetes (`deportivo`, `vision`, `partido`,
  `analisis`, `asistencia`) — están diseñados en
  [docs/diagramas/modelo-datos.puml](docs/diagramas/modelo-datos.puml)
- Worker de visión — ver [vision/README.md](vision/README.md)
- Pasar el token a `flutter_secure_storage`: hoy usa SharedPreferences, que no cifra
