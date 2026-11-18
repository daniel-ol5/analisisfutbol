# Calibración dinámica: validación local del 17/11/2026

## Cambios implementados

- Configuración automática sin homografía ficticia ni marcado inicial obligatorio.
- Referencia manual vinculada a video, PTS, índice y resolución; inclusión del
  cuadro de anclaje aunque no coincida con el stride de inferencia.
- Reconocimiento con checkpoint público de cancha, validación contra rectas y
  círculo observado y rechazo de geometría insuficiente.
- Seguimiento proyectivo con comprobación de flujo óptico de ida y vuelta,
  exclusión de objetos y controles de distribución espacial.
- Recuperación contra imágenes calibradas con correspondencias SIFT distribuidas.
  Esta recuperación presupone cámara en punto fijo con paneo/zoom. No valida
  una cámara que se traslada físicamente por el estadio.
- Estados de referencia, caducidad de propagación y conservación de detecciones
  en píxeles cuando no se pueden emitir metros.
- Líneas estimadas y detecciones inspeccionables sobre la grabación; región
  visible publicada para el plano.
- Pantalla simplificada; retirada del autocompletado sintético y de inferencia
  pesada en el endpoint de calibración de la API.
- Migración aditiva `a9d8c1e7f302`, aplicada a PostgreSQL local.
- Corrección de cierre de ingesta: registro de tracks antes de posiciones,
  vaciado protegido frente a cancelación y vaciado al finalizar el partido.

## Prueba integral con modelos reales

Se ejecutó `evaluacion.prueba_integral_local` sobre
`almacen/prueba-integral-10s.mp4`, en CPU, con YOLO11n COCO a 640 y modelo de
cancha. Se creó una base SQLite y un club exclusivamente para el ensayo. La
base del usuario no recibió cuentas ni datos de estas pruebas.

| Resultado | Evidencia |
|---|---|
| Grabación completa | Estado PROCESADO; 50 muestras recibidas por la API |
| Referencia en grabación | 50 muestras con referencia disponible |
| Directo simulado | 16 muestras recibidas por el suscriptor WebSocket de la API |
| Referencia en directo | 16 muestras con referencia disponible |
| Persistencia | 130 posiciones en grabación y 28 en directo |
| Duración del ensayo combinado | Aproximadamente 43.9 s, incluyendo procesamiento en CPU |

Archivo de resultados: `almacen/prueba-integral-aislada-02/informe.json`.
Se usaron HTTP y WebSocket ASGI en proceso, con rutas, autorización y persistencia
reales. No representa una medición de red física, GPU o cámara de captura.
La cantidad de posiciones es baja con COCO a 640: no acredita cobertura completa
de jugadores ni calidad de detección de balón.

La primera ejecución descubrió que cerrar el canal podía cancelar el guardado
del último lote. Tras corregirlo, ambos partidos conservaron posiciones.

## Video completo y movimiento

Se evaluó geometría sobre los aproximadamente 152.3 s del video Bayern–PSG
original, con stride 6 y CPU. El ensayo final generó 763 muestras: 116 con
reanclaje en ese cuadro y 647 en seguimiento. La duración fue aproximadamente
197.3 s mientras se ejecutaban otras comprobaciones locales. No mide el coste
de YOLO de personas ni demuestra tiempo real en esta laptop.

Resultados y capturas superpuestas:
`almacen/calibracion-movil-ensayo-04/`. No se equipara el porcentaje de muestras
que superaron controles internos con la precisión real de sus posiciones.

Las inspecciones visuales detectaron y permitieron corregir dos problemas:
atracción hacia líneas del área técnica y extrapolación desde correspondencias
concentradas. Se incorporaron correspondencias de rectas, comprobación del
círculo y una cobertura mínima más amplia en la recuperación visual.

## Precisión: límite que permanece abierto

En una comprobación manual orientativa del cuadro cercano a 18 s, cinco
referencias conocidas proyectadas desde una referencia anterior dieron un
error medio aproximado de 1.43 m y máximo aproximado de 4.61 m, con el peor
resultado en una esquina lejana. Las posiciones de control fueron marcadas
manualmente y se asumió cancha de 105 × 68 m. No son un conjunto de verdad
terreno certificado ni una evaluación representativa de todos los cuadros.

Esto impide afirmar precisión táctica uniforme, exactitud de velocidades o
validez de reglas cerca de límites observados con mala geometría. Se deben
anotar controles repartidos por zonas y tiempos y medir su error antes de
aceptar recomendaciones basadas en distancias. Las reglas del Sprint 4 no se
consideran implementadas o validadas por este rediseño.

Una banda fuera de cámara queda no observada. Un balón aéreo no se puede
localizar exactamente sobre el suelo mediante la homografía del terreno.

## Pruebas de software e interfaz

- Batería completa de backend: pasó tras el cambio de contratos y migración.
- Tras corregir el cierre de directo: pasaron pruebas de control de partido,
  persistencia y nuevos casos de calibración móvil.
- Batería de visión: pasó, incluidos perspectiva, cambio de resolución,
  referencia futura, caducidad y recuperación/rechazo de escenas visuales.
- Web: 84 pruebas pasaron y se compiló para producción.
- Chrome sin interfaz: guardado automático sin puntos, marcado manual de ocho
  referencias, escritorio y móvil sin errores JavaScript ni desborde horizontal.
  En esta comprobación visual se simuló la API; no se confunde con la prueba
  integral con modelos reales.

Capturas: `almacen/calibracion-desktop.png` y
`almacen/calibracion-mobile.png`; resumen `almacen/qa-calibracion.json`.

## Aceptación pendiente

1. Ejecutar el cuaderno actualizado sobre la T4 y medir el pipeline completo.
2. Comprobar fuente de cámara física y transporte hacia el worker remoto.
3. Medir error geométrico con controles independientes en varios encuadres.
4. Realizar dos horas continuas en el entorno de presentación.
5. Completar aislamiento de distintas ejecuciones de análisis y validar reglas
   tácticas con cobertura suficiente. Para los ensayos actuales se usan
   partidos nuevos y separados.

No se realizaron commits ni push.
