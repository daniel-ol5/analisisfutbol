# Área Técnica

Sistema de análisis táctico de fútbol por visión computacional. Monitorea un partido
desde una cámara fija y entrega recomendaciones tácticas justificadas al entrenador,
en vivo y sobre partidos grabados.

Proyecto de la materia Ingeniería de Software · Marco de trabajo Scrum · Equipo de 6.

---

## Estructura

```
Deportivo/
├─ vision/     Worker de visión — YOLO, ByteTrack, homografía (corre junto a la cámara)
├─ backend/    Django + DRF + Channels — API, WebSockets, motor de reglas
├─ web/        React + TypeScript + Vite — panel del DT y calibración
├─ movil/      Flutter — app del DT y del asistente de campo
└─ docs/       Actas, ADRs y diagramas
```

> El worker de `vision/` se despliega en la máquina con GPU que va a la cancha.
> El video **nunca** sale de ahí: solo viajan coordenadas al servidor por WebSocket.

---

## Requisitos

| | |
|---|---|
| Python | 3.11+ |
| Node | 20+ |
| Docker | Docker Desktop con Compose |
| GPU | NVIDIA (GTX 1650 / RTX 3050 mínimo) — **solo** para `vision/` |

El backend, la web y el móvil no necesitan GPU.

---

## Puesta en marcha

Pendiente — se completa con `Pb-05` (entorno reproducible) en el Sprint 1.

```bash
# objetivo del Sprint 1:
docker compose up
```

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
fix(backend): corregir filtro de aislamiento por club
docs(adr): ADR-001 decisiones de montaje de cámara
```

**Pull Requests.** Obligatorios, con al menos una aprobación de alguien distinto al
autor y la integración continua en verde. Nadie mergea su propio PR.

**Regla de las 24 h.** Un PR abierto se revisa en menos de un día: uno estancado
bloquea a otra persona.

---

## Documentación del proyecto

| Documento | Contenido |
|---|---|
| Sprint 0 | Equipo, objetivo, infraestructura, prácticas, modelos y criterios de calidad |
| Product Backlog | 50 requerimientos en formatos F3 y F4 |
| Casos de uso | 58 casos de uso en 6 paquetes |

Los ADRs de decisiones técnicas van en `docs/adr/`.

---

## Nunca al repositorio

- **Pesos de modelos** (`.pt`, `.onnx`) — van a almacenamiento de objetos versionados
- **Video de partidos** — un partido completo son varios GB
- **Secretos** (`.env`, claves, tokens) — se gestionan en el proveedor de despliegue

Si alguno entra al historial, queda ahí para siempre aunque se borre después.
