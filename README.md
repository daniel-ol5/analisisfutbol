# Área Técnica

Sistema de análisis táctico de fútbol por visión computacional. Monitorea un
partido desde una cámara fija y entrega recomendaciones tácticas justificadas al
entrenador, en vivo y sobre partidos grabados.

Proyecto de Ingeniería de Software · Marco de trabajo Scrum · Equipo de 6.

---

## Estructura

```
Deportivo/
├─ vision/     Worker de visión — YOLO, ByteTrack, homografía (necesita GPU)
├─ backend/    FastAPI — API, WebSockets, motor de reglas
├─ web/        React + TypeScript + Vite — panel del DT y calibración
├─ movil/      Flutter — app del DT y del asistente (pendiente)
└─ docs/       Actas, ADRs y diagramas
```

El `backend` y la `web` están organizados en **seis paquetes** que espejan el
modelo de casos de uso:

| Paquete | Casos de uso | Contenido |
|---|---|---|
| `seguridad` | CU-01 … CU-08 | Acceso, usuarios, roles, auditoría |
| `deportivo` | CU-09 … CU-17 | Equipos, plantel, partidos, alineaciones |
| `vision` | CU-18 … CU-29 | Calibración, modelos, video grabado |
| `partido` | CU-30 … CU-39 | Captura en vivo, eventos manuales |
| `analisis` | CU-40 … CU-48 | Métricas y visualizaciones |
| `asistencia` | CU-49 … CU-58 | Reglas, recomendaciones, informes |

---

## Puesta en marcha

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows
pip install -r requirements.txt
copy .env.example .env             # y generar una SECRET_KEY propia
uvicorn app.main:app --reload
```

API en `http://127.0.0.1:8000` · documentación en `http://127.0.0.1:8000/api/docs`

Por defecto usa SQLite, así que **no hace falta Docker ni PostgreSQL** para
levantarlo. Para Postgres, cambiar `DATABASE_URL` en `.env`.

### Web

```bash
cd web
npm install
copy .env.example .env.local
npm run dev
```

Aplicación en `http://localhost:5173`

### Pruebas

```bash
cd backend && venv\Scripts\python -m pytest
cd web && npm run build
```

---

## Convenciones

**Importaciones en la web.** Siempre con el alias `@/`, nunca rutas relativas
largas:

```ts
import { api } from "@/shared/api/client";   // así
import { api } from "../../shared/api/client";  // no
```

**Una feature no importa de otra feature.** Si `analisis` necesita algo de
`partido`, ese algo sube a `shared/`. Sin esa regla, para el Sprint 3 todo
importa de todo.

**En el backend, `router.py` no toca la base de datos y `service.py` no conoce
FastAPI.** El router traduce HTTP a llamadas de servicio y nada más. Así el
motor de reglas se prueba sin levantar el servidor.

**Toda consulta filtrada por club pasa por `core/tenancy.py`.** Repetir el
filtro a mano en cada endpoint es exactamente como se filtran datos entre clubes
sin querer (`Pb-03`).

---

## Cómo trabajamos

**Ramas.** `main` está protegida. Una rama por historia:

```
feat/Pb-21-calibracion-camara
fix/Pb-28-latencia-panel
```

**Commits.** Formato convencional:

```
feat(vision): proyectar detecciones al plano de cancha
fix(seguridad): corregir filtro de aislamiento por club
docs(adr): ADR-001 decisiones de montaje de cámara
```

**Pull Requests.** Obligatorios, con al menos una aprobación de alguien distinto
al autor y la integración continua en verde. Nadie mergea su propio PR.

**Regla de las 24 h.** Un PR abierto se revisa en menos de un día: uno estancado
bloquea a otra persona.

---

## Nunca al repositorio

- **Pesos de modelos** (`.pt`, `.onnx`) — van a almacenamiento de objetos versionados
- **Video de partidos** — un partido completo son varios GB
- **Secretos** (`.env`, claves, tokens) — se gestionan en el proveedor de despliegue

Si alguno entra al historial, queda ahí para siempre aunque se borre después.

---

## Estado

Esqueleto del Sprint 1. Implementado:

- Registro de club, login y control de acceso por rol (`CU-01`, `CU-02`, `CU-04`)
- Aislamiento entre clubes con prueba automatizada (`Pb-03`)
- Los seis paquetes montados, con la documentación de la API agrupada por paquete
- Web conectada al backend, con las seis secciones enrutadas

Pendiente: todo lo demás del backlog.
