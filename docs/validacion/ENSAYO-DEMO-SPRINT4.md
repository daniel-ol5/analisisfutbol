# Ensayo del preparador de demostración — Sprint 4

Fecha: 19/11/2026  
Tarea: T-088  
Entorno: PostgreSQL 16 efímero, API local en `127.0.0.1:8001`, Firebase deshabilitado.

## Alcance

El ensayo se ejecutó sobre una base vacía exclusiva. No se usó ni modificó la base de desarrollo
habitual. Se probaron migraciones, seed, verificación de solo lectura, preparación automática,
WebSocket de ingesta, métricas y recomendaciones.

## Resultados

| Verificación | Resultado |
|---|---|
| Migraciones desde cero | Correcto, hasta `6d8f2a1c9b40` |
| Primer seed | Creó administrador y escenario deportivo |
| Segundo seed | Sin cambios; no duplicó registros |
| Datos | 1 competición, 1 equipo, 18 jugadores, 3 partidos y 1 alineación |
| Catálogo táctico | 12 reglas activas |
| Verificador antes de preparar | Correcto; avisó calibración y recomendaciones ausentes |
| Calibración sintética | Válida, error medio `0.0000 m` |
| Inicio del partido | Correcto, dirección `DER` |
| Evento crítico | Tarjeta roja ficticia registrada con UUID estable |
| Ingesta principal | 60 mensajes a 5 Hz durante 12 s; 0 rechazados |
| Recomendación | 1 activa de prioridad `CRITICA` |
| Segunda preparación | Mismo evento, 10 mensajes, 0 rechazados, siguió existiendo 1 recomendación |
| Ruff | Sin errores en `app`, `scripts` y pruebas modificadas |
| Pruebas focalizadas | 7 aprobadas en `tests/test_seed_dev.py` |

La segunda preparación confirma idempotencia del evento y que el cooldown evita duplicar la
recomendación crítica dentro del mismo período.

## Incidencia encontrada durante el ensayo

La primera ejecución intentó registrar una tarjeta propia sin `jugador_id` y la API respondió 422,
como exige el contrato. El preparador se corrigió para elegir automáticamente un titular de la
alineación. La repetición completó el flujo sin intervención manual.

## No verificado en este ensayo

- renderizado visual completo en navegador y emulador;
- recepción FCM en dispositivo físico;
- worker GPU, YOLO11, ByteTrack y cámara real;
- endpoints 501 documentados por T-089;
- despliegue o recursos AWS;
- aceptación del Product Owner.

## Conclusión

La preparación técnica local de la demo es repetible y no requiere corregir datos manualmente. El
recorrido debe limitarse a funciones terminadas y declarar las pantallas/endpoints pendientes. Este
ensayo no sustituye la prueba física de cancha de T-106.

