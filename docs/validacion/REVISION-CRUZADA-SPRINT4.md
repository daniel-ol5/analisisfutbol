# Revisión cruzada de código — Sprint 4 (T-089)

Fecha de revisión: 18/11/2026  
Rama revisada: `Susana`  
Commit base: `300a65f` (`Merge pull request #40 from daniel-ol5/Susana`)

## Resultado ejecutivo

- No hay Pull Requests abiertos: GitHub muestra 0 abiertos y 40 cerrados.
- `Susana`, `origin/Susana` y `origin/main` apuntan al mismo commit. Las ramas remotas del
  equipo no tienen commits por delante de `main`, por lo que no se detectó código pendiente de
  integrar ni conflictos de ramas en esta revisión.
- No se encontraron TODO/FIXME de severidad crítica. Sí existen endpoints que responden 501 y
  pantallas marcadas como pendientes que impiden mostrar todo el flujo del Sprint 4 desde la UI.
- El contrato OpenAPI congelado está sincronizado con CI. La ejecución de Pull Request posterior
  a la corrección del contrato (`CI #97`) terminó correctamente.
- Alembic tiene una sola cabeza (`6d8f2a1c9b40`) y una base PostgreSQL 16 vacía pudo migrarse
  desde la revisión inicial hasta esa cabeza.
- Backend, web y Flutter pasan sus baterías de pruebas y builds. La ejecución de `main` en
  GitHub Actions (`CI #98`) también terminó correctamente sobre este mismo commit.

## Hallazgos

| ID | Problema detectado | Archivo(s) | Severidad | Responsable | Corrección propuesta | Estado | Evidencia |
|---|---|---|---|---|---|---|---|
| RC-01 | La sección **Asistencia y Reportes** sigue siendo un marcador `Pendiente` tanto en web como en Flutter. No permite ver recomendaciones priorizadas, alertas, informes ni el resultado de tocar una notificación push. | `web/src/features/asistencia/pages/AsistenciaPage.tsx`; `web/src/features/asistencia/api.ts`; `movil/lib/features/asistencia/pagina.dart`; `movil/lib/features/asistencia/api.dart` | Alto | Alejandra (CU-50/CU-51 web) y Araceli (T-096 Flutter) | Implementar consumidores del contrato existente, navegación por `partido_id` y `recomendacion_id`, y estados de carga/error. Reutilizar `GET /asistencia/partidos/{id}/recomendaciones` y el payload documentado de T-087. | Abierto | La web solo llama a `/asistencia/ping`; Flutter solo define `ping()` y ambas páginas renderizan `Pendiente`. |
| RC-02 | El catálogo de reglas solo puede listarse. Crear, editar/activar/desactivar y probar reglas devuelve 501, por lo que no puede prepararse el escenario de reglas desde la aplicación. | `backend/app/asistencia/router.py:39`; `backend/app/asistencia/router.py:46`; `backend/app/asistencia/router.py:53` | Alto | Araceli (CU-54) | Implementar servicios con aislamiento por club, validación del DSL y pruebas de creación, edición y simulación. | Abierto | Tres rutas terminan en `pendiente("CU-54", "Sprint 4", "Araceli")`. |
| RC-03 | Valorar recomendaciones y consultar alertas de fatiga/riesgo de expulsión devuelve 501. Esto deja incompleto el flujo interactivo posterior a una recomendación. | `backend/app/asistencia/router.py:72`; `backend/app/asistencia/router.py:79` | Alto | Alejandra (CU-51) y Araceli (CU-52) | Implementar transición de estados/valoración y reglas de alertas; conservar aislamiento por club y la excepción de jugadores con menos de 15 minutos. | Abierto | Ambas rutas llaman a `pendiente()`; no hay consumidores web o Flutter. |
| RC-04 | Generación/consulta de informes, exportación CSV y comparativa de temporada devuelven 501. La parte de resultados post-partido anunciada en la interfaz no es demostrable. | `backend/app/asistencia/router.py:99`; `backend/app/asistencia/router.py:107`; `backend/app/asistencia/router.py:114`; `backend/app/analisis/router.py:215` | Alto | Jhon (CU-55, CU-56 y CU-57) | Implementar proceso de informe, descarga/estado, exportación y comparativa; añadir pruebas multi-club y contratos de archivo. | Abierto | Las cuatro rutas llaman a `pendiente()` y el inicio web anuncia informes/comparativas. |
| RC-05 | Persisten dos endpoints 501 de Sprint 3: posiciones por rango y eventos derivados. No están consumidos por las UIs actuales, pero limitan replay, mapas y consulta detallada de eventos. | `backend/app/partido/router.py:177`; `backend/app/analisis/router.py:206` | Medio | Daniel (CU-41) y Alejandra (CU-42) | Conectar los servicios/persistencia ya existentes o retirar temporalmente las rutas de la demo; añadir pruebas de pertenencia al club y rangos. | Abierto | `pendiente("CU-41"...)` y `pendiente("CU-42"...)`; búsqueda de consumidores sin coincidencias en web/Flutter. |
| RC-06 | El reloj persiste `descuento_1_min` y `descuento_2_min`, pero `EstadoEnVivo` no los expone. Web conserva el valor únicamente en memoria y lo pierde al recargar; Flutter también documenta la ausencia. | `backend/app/partido/models.py:51`; `backend/app/partido/schemas.py:48`; `web/src/features/partido/types.ts:34`; `web/src/features/partido/pages/PartidoPage.tsx:119`; `movil/lib/features/partido/modelos.dart:80` | Medio | Responsable de CU-30/CU-31 (por confirmar con el equipo) | Agregar ambos campos al esquema y constructor, actualizar OpenAPI y consumidores, y probar recarga/reconexión durante descuento. Coordinar el cambio de contrato antes de implementarlo. | Abierto | Las columnas existen en base, pero no aparecen en `EstadoEnVivo` ni en el OpenAPI congelado. |
| RC-07 | Oxlint reporta advertencias de React: lectura de `ref` durante render, uso de `Date` impuro durante render, actualizaciones de estado síncronas en efectos y archivos que mezclan componentes con utilidades. Pueden causar renders obsoletos o innecesarios, aunque no bloquean el build. | `web/src/features/deportivo/components/CanchaTactica.tsx:205`; `PartidosView.tsx:48`; otros componentes de `deportivo`, `analisis` y `vision` informados por Oxlint | Medio | Equipo web / autores de cada feature | Resolver primero `react(refs)` y `react(purity)`; después separar utilidades y derivar estado en render o eventos donde corresponda. | Abierto | `npm run lint` finaliza con código 0 y 12 advertencias de código fuente. CI añade advertencias equivalentes. |
| RC-08 | El bundle principal web minificado supera el umbral recomendado de Vite. | `web/src/app/router.tsx` y grafo de imports de la aplicación | Bajo | Equipo web | Cargar páginas pesadas con `lazy()`/imports dinámicos y dividir por feature. | Abierto | Build: `index-*.js` de 684,01 kB; Vite advierte por chunks mayores de 500 kB. |
| RC-09 | El workflow usa acciones basadas en Node 20 y `setup-java@v4`, versiones marcadas como obsoletas por GitHub. | `.github/workflows/ci.yml` | Bajo | Responsable de CI/infraestructura | Actualizar acciones a versiones compatibles (`setup-java@v5` y versiones vigentes del resto), en un cambio separado y revisado. | Abierto | GitHub Actions muestra advertencias de deprecación; no afectan el resultado actual. |
| RC-10 | La batería backend presenta advertencias de compatibilidad futura: alcance de fixtures async sin definir, alias interno de pytest usado por AnyIO y constante HTTP 422 obsoleta. | Configuración de pytest; entorno AnyIO; `backend/app/partido/router.py:170` | Bajo | Equipo backend | Definir explícitamente `asyncio_default_fixture_loop_scope`, actualizar dependencias compatibles y reemplazar `HTTP_422_UNPROCESSABLE_ENTITY` por `HTTP_422_UNPROCESSABLE_CONTENT`. | Abierto | 835 pruebas pasan; pytest captura 4 advertencias y muestra además la advertencia de configuración de `pytest-asyncio`. |

## Compatibilidad y contratos

### Backend ↔ web

- Los clientes existentes de partido, deportivo, visión y análisis usan el prefijo `/api` mediante
  el cliente compartido y coinciden con las rutas del contrato.
- La sección de asistencia no consume todavía los endpoints reales; por eso no existe una
  incompatibilidad de tipos en build, pero sí una integración funcional pendiente (RC-01).
- El estado del descuento tiene una incompatibilidad de capacidad: el dato se guarda en base pero
  no forma parte del DTO compartido (RC-06).

### Backend ↔ Flutter

- Las rutas implementadas de agenda, alineación, partido y análisis compilan y sus pruebas pasan.
- La recepción/registro de push de T-096 no está integrada en Flutter: el backend de T-087 está
  preparado, pero no hay registro FCM ni navegación desde notificación en el cliente (RC-01).
- El payload backend de T-087 contiene `recomendacion_id`, `partido_id`, `prioridad` y `ruta`, por
  lo que el contrato necesario para esa integración ya está definido.

### OpenAPI

- `docs/api/openapi.json` está versionado y sin cambios locales.
- `CI #97` validó el contrato después del commit `8ac1ebd`.
- No se regeneró con el Python local porque las versiones locales de FastAPI/Pydantic difieren de
  las de CI y pueden producir cambios de serialización que no representan cambios del contrato.

## Migraciones

- `python -m alembic heads`: una sola cabeza, `6d8f2a1c9b40`.
- `python -m alembic upgrade head`: correcto sobre PostgreSQL 16 vacío.
- `python -m alembic current`: `6d8f2a1c9b40 (head)`.
- La prueba usó exclusivamente `db_test`, una base efímera sin volumen; no se modificó la base de
  desarrollo del usuario.

## Verificaciones ejecutadas

| Área | Comando/verificación | Resultado |
|---|---|---|
| Git | `git status --short --branch` y `git diff --check` | Rama limpia antes del informe; sin errores de espacios. |
| Ramas | `git rev-list --left-right --count origin/main...origin/<rama>` | Alex, Jhon, Alejandra, Araceli y Daniel: 0 commits por delante de `main`. |
| PR | Consulta del listado de Pull Requests en GitHub | 0 abiertos; 40 cerrados. |
| CI | GitHub Actions, PR #40 (`CI #97`) y `main` (`CI #98`) | Ambas ejecuciones completadas correctamente. |
| Backend | `python -m ruff check app scripts tests` | Correcto, sin errores. |
| Backend | `python -m pytest` | 835 aprobadas, 37 omitidas, 4 advertencias; 13 min 23 s. |
| Migraciones | `alembic heads`, `upgrade head`, `current` contra PostgreSQL 16 vacío | Correcto; una cabeza. |
| Web | `npm run lint` | Correcto con 12 advertencias no bloqueantes. |
| Web | `npm test` | 6 archivos y 106 pruebas aprobadas. |
| Web | `npm run build` | Correcto; advertencia de chunk de 684,01 kB. |
| Flutter | `flutter analyze` | Sin observaciones. |
| Flutter | `flutter test` | 111 pruebas aprobadas. |
| Flutter | `flutter build web --release` | Correcto. |

## Evaluación del criterio de aceptación de T-089

- **Pull Requests abiertos:** cumplido, no hay PRs abiertos.
- **TODOs críticos:** cumplido, no se detectaron TODO/FIXME críticos.
- **Conflictos pendientes:** no detectados; ramas remotas sin commits por delante de `main`.
- **Problemas de integración:** documentados en RC-01 a RC-10.
- **Cambios en módulos ajenos:** ninguno; esta tarea solo agrega el presente informe.

T-089 puede cerrarse como revisión realizada, pero los hallazgos altos RC-01 a RC-04 deben
resolverse o excluirse explícitamente del recorrido antes de afirmar que la demostración T-088
es completa de extremo a extremo.
