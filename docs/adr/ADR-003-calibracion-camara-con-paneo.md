# ADR 003: Calibración para una cámara con paneo, inclinación y zoom

- Fecha: 16/11/2026.
- Estado: implementación y pruebas locales realizadas; aceptación de GPU, cámara real y precisión pendiente.
- Alcance: grabación y directo desde una cámara táctica situada en una tribuna.
- Prioridad: resolver geometría y recuperación antes de aceptar recomendaciones
  que dependan de posiciones, distancias o zonas de la cancha.

## Problema observado

El primer encuadre Bayern–PSG no muestra ocho referencias de la plantilla
guiada. Recortar otro tramo permite probar el circuito actual, pero no resuelve
el movimiento de cámara durante el partido completo.

Una homografía relaciona la imagen con el plano del suelo en un encuadre
concreto. Cuando cambia la orientación o el zoom, debe actualizarse. Una
cámara que panea tampoco observa toda la cancha al mismo tiempo.

## Situación comprobada antes del rediseño

| Pieza | Situación |
|---|---|
| `web/src/features/vision/calibracion.ts` | Plantilla de 14 referencias; mínimo manual de ocho pares. No incluye cruces del círculo central ni área chica. |
| `backend/app/vision/models.py` | Calibración única por club y partido; no vincula la referencia con el cuadro y la fuente de video que la originaron. |
| `vision/seguimiento/gmc.py` | Flujo óptico y transformación afín parcial. Sus límites de desplazamiento son constantes en píxeles por cuadro; el tiempo entre cuadros puede variar. |
| `vision/calibracion/dinamica.py` | Propaga la homografía y admite reanclaje mediante un estimador de 32 puntos, cuyo orden de etiquetas requiere verificación. |
| `vision/procesamiento/mensajes.py` | Solo crea el estimador absoluto si encuentra `vision/pesos/yolo_cancha_keypoints.pt`; ese archivo y su carpeta no están presentes. Declara pérdida de referencia y publica campo visible. |
| `web/src/features/vision/pages/CalibracionPage.tsx` | «Autocompletar 8 puntos válidos» genera coordenadas sintéticas a partir del tamaño de imagen. No detecta líneas en la fotografía. |
| Detección automática en la API | Invoca código de visión desde el backend. La inferencia pesada debe quedar en el worker que tenga los modelos y el dispositivo adecuado. |

La compensación relativa actual no acredita precisión durante paneos prolongados
ni permite recuperar automáticamente la geometría si se pierde la referencia
y no hay un estimador absoluto disponible.

## Decisión propuesta

Mantener YOLO para detección de personas y balón, con una rama independiente
para reconocer la cancha. Ambas alimentan el mismo pipeline de grabación y
directo. El motor de calibración combina:

1. **Referencia absoluta:** líneas e intersecciones identificadas de la cancha,
   sus dimensiones y orientación. Emplear un modelo preentrenado evaluado antes
   de incorporarlo; el marcado manual conserva su función de ayuda y respaldo.
2. **Seguimiento entre cuadros:** correspondencias del terreno para actualizar
   una transformación proyectiva, excluyendo jugadores y regiones ajenas al
   campo. La máscara debe incluir las líneas blancas, no solo píxeles verdes.
3. **Verificación y recuperación:** volver a reconocer marcas periódicamente o
   al detectar deriva, corte, salto temporal, zoom brusco o mala calidad.
4. **Visibilidad:** asociar cada muestra con la zona del terreno efectivamente
   observada en ese momento.

No sustituir la estimación actual por una homografía sin controles: sus grados
de libertad adicionales pueden ajustar correspondencias erróneas. Exigir
consistencia temporal, distribución espacial e inliers suficientes, además de
error de reproyección y comprobaciones de geometría.

## Estados y datos

| Estado | Comportamiento propuesto |
|---|---|
| Sin referencia | Mantener detecciones en píxeles; no producir posiciones métricas. Intentar reconocimiento absoluto. |
| Referencia verificada | Proyectar puntos de apoyo de jugadores y registrar la evidencia de verificación. |
| Seguimiento temporal | Propagar una referencia reciente mientras supera las comprobaciones; informar su antigüedad. |
| Referencia perdida | Suspender proyección métrica y reglas dependientes de ella; intentar recuperación sin reutilizar una matriz antigua como si fuera válida. |

Un anclaje debe identificar fuente, resolución, cuadro/PTS, dimensiones del
campo, orientación, versión del método/modelo y evidencia de validación. La
matriz inicial de un partido no basta para distinguir diferentes videos o
posiciones de cámara. La evolución temporal debe pertenecer a la ejecución de
procesamiento, con su identificador, para no mezclar reintentos.

La salida de calidad debe incluir estado, PTS del último anclaje absoluto,
cantidad y distribución de correspondencias, error disponible y polígono
visible. Los umbrales y el tiempo admisible sin referencia se establecerán con
ensayos; no se presentan como medidos todavía.

El sistema de coordenadas será único: origen en la esquina inferior izquierda
del plano mostrado, X a lo largo e Y hacia la banda opuesta. Cada adaptador de
modelo convertirá explícitamente sus etiquetas a esa convención. No basta con
que un checkpoint entregue exactamente 32 puntos.

## Cambios en la experiencia de calibración

- Trabajar sobre el video o la fuente seleccionada, con tiempo y resolución
  visibles, en lugar de una imagen independiente sin vínculo con la fuente.
- Mostrar las líneas estimadas superpuestas al video para inspeccionar paneos
  y zoom, junto al estado de referencia y la región observada en el plano.
- Ampliar referencias manuales con cruces del círculo, área chica y puntos
  identificables sobre el suelo; permitir omitir los no visibles.
- Retirar del flujo real el autocompletado sintético y presentar claramente la
  disponibilidad efectiva del modelo automático.
- Guardar una referencia manual en el cuadro donde se marcó. En directo, al
  congelar un cuadro para marcar, conservar su identidad y reconectar la
  geometría con el flujo actual mediante seguimiento comprobado o un nuevo
  anclaje. No aplicar a ciegas la matriz del cuadro congelado al presente.

El mínimo actual de ocho pares es una política de validación manual, no la
exigencia de ver ocho esquinas en cada imagen del video. Cambiarla requiere un
evaluador que distinga ajuste geométrico de validación independiente. No se
reducirá a cinco para superar el bloqueo ni se inventarán referencias.

## Orden de trabajo

1. **Evaluar referencia absoluta en Colab.** Seleccionar cuadros del inicio,
   centro, ambos extremos, paneos y posibles cambios de plano del video
   completo. Probar primero la cadena de segmentación/calibración de
   TVCalib/SoccerNet. Comprobar disponibilidad real del checkpoint,
   compatibilidad del entorno, orientación, alineación de líneas y coste por
   imagen. No entrenar desde cero para desbloquear esta entrega.
2. **Implementar el motor compartido.** Adaptador del método elegido,
   seguimiento proyectivo del terreno, estados, control de deriva y
   recuperación. Usar PTS y resolución al evaluar movimiento; preservar
   detecciones en píxeles cuando no haya referencia métrica.
3. **Vincular calibración con fuente y ejecución.** Actualizar contratos,
   persistencia y pantalla. La API coordina los trabajos; el worker ejecuta
   los modelos. Conservar compatibilidad con el marcado manual existente
   mientras se valida el nuevo método.
4. **Evaluar ambos modos.** El modo de directo debe ser causal: sin mirar
   cuadros futuros ni usar una calibración posterior como si ya existiera al
   comienzo. En grabación puede existir una preparación adicional, identificada
   como tal, sin confundir su rendimiento con tiempo real.
5. **Comprobar recomendaciones y estabilidad.** Aplicar condiciones de calidad
   y cobertura antes de activar reglas; después ensayar conexión GPU–API–web y
   una sesión sostenida de dos horas en el entorno elegido para la defensa.

TVCalib es un candidato, no una dependencia seleccionada definitivamente.
Su optimización por imagen puede condicionar la frecuencia de reanclaje.
La primera prueba decidirá si se adapta, si se utiliza una alternativa más
ligera o si se conserva ayuda manual explícita para esta entrega.

## Evidencia de aceptación

- Líneas del campo superpuestas y alineadas en muestras repartidas por el video.
- Error en referencias de control que no participaron en el ajuste; informar
  también error de imagen y ubicación del control, sin confundir residual de
  entrenamiento con precisión real.
- Proporción de tiempo con referencia verificada, propagada y perdida;
  duración máxima de seguimiento sin anclaje y tiempo de recuperación.
- Cortes, cuadros saltados, cambios de resolución, poca textura, oclusiones y
  correspondencias falsas no producen posiciones silenciosamente incorrectas.
- Medición por separado de detección, geometría, publicación, retraso y cuadros
  descartados; presupuesto de tiempo medido sobre la GPU real.
- Mismo convenio de coordenadas y comportamiento de calidad en grabación y
  directo. En directo, pérdida y recuperación visibles en la aplicación.

No se fija todavía una precisión, frecuencia o cobertura garantizada: falta
medir estos resultados con el modelo y video reales.

## Límites para las reglas tácticas

Una banda fuera de cámara está **no observada**, no vacía. Conservar lo visto
antes no equivale a conocer las posiciones actuales de quienes salieron del
encuadre. Las reglas deben verificar cobertura suficiente durante la ventana
temporal correspondiente y declarar evidencia insuficiente cuando falte.

La homografía del terreno proyecta puntos sobre el suelo. Los pies de los
jugadores sirven como aproximación; la imagen de un balón aéreo no determina
su posición real sobre el terreno con esta transformación. No convertirla en
una medición exacta ni utilizarla para posesión sin validar esa condición.

## Referencias consultadas

- [SoccerNet: tarea y evaluación de calibración](https://www.soccer-net.org/tasks/camera-calibration).
- [SoccerNet: implementación de referencia por líneas](https://github.com/SoccerNet/sn-calibration).
- [TVCalib: inferencia y modelo de segmentación preentrenado](https://github.com/MM4SPA/tvcalib#inference).
- [OpenCV: correspondencias y homografía](https://docs.opencv.org/4.13.0/d7/dff/tutorial_feature_homography.html).

La implementación utilizó un checkpoint público de Roboflow Sports de 32 marcas,
validación contra líneas y círculo y recuperación por referencias visuales. TVCalib
no se incorporó. El origen del modelo está documentado en
[MODELO_CANCHA.md](../../vision/calibracion/MODELO_CANCHA.md).
Los resultados y límites se describen en
[la validación del rediseño](../validacion/CALIBRACION-DINAMICA-2026-11-17.md).
No se realizaron commits ni push.
