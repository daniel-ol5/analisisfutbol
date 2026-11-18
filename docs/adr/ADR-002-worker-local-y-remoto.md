# ADR 002 Ejecución local y remota del worker

- Fecha: 16/11/2026.
- Estado: implementación inicial con pruebas de software; validación de GPU y cancha pendiente.
- Restricciones: laptop de desarrollo i5 con GPU integrada, GTX 1650 disponible
  fuera de esta máquina y presupuesto inicial de US$10–20 mensuales para pruebas.
- Ambas modalidades, grabación y directo, forman parte del objetivo de entrega.
- Primera prueba elegida por el equipo: Google Colab mediante un cuaderno
  interactivo, sin conexión a la API local. Vast.ai queda como alternativa
  posterior para ensayos de directo sostenido, pendiente de selección y contratación.

## Decisión

Mantener la inferencia fuera de la API. Reutilizar el pipeline de geometría,
equipos y balón para un archivo y para una fuente continua. Separar tiempo de
video, frecuencia de inferencia, frecuencia de publicación y rendimiento real.

El modo local mantiene el video en cancha. El modo remoto transmite video
comprimido a una instancia GPU alquilada durante sesiones concretas. La API
puede permanecer local mediante un túnel SSH o usar un despliegue HTTPS.
Una GPU remota no mejora el detalle perdido en el video original.

La primera evaluación en Colab compara un archivo y su lectura a velocidad real.
Exporta cajas, capturas, telemetría opcional y un informe de rendimiento. Sin
calibración no genera posiciones métricas. Esta simulación no certifica cámara,
transporte ni WebSocket. No se usa Colab como servidor persistente ni como un
worker distribuido en segundo plano. Su disponibilidad y duración no están garantizadas.

La reproducción de resultados es de solo lectura y sigue el reloj del video.
Un WebSocket conectado no demuestra que exista inferencia en directo.

## Visibilidad y calibración

Una cámara que panea no observa toda la cancha simultáneamente. Publicar el
polígono visible y declarar la pérdida de referencia. Conservar escala y
rotación al componer movimientos. La compensación relativa necesita reanclajes
absolutos contra marcas conocidas; su error debe medirse en puntos independientes.
La precisión del checkpoint de marcas de cancha y su orden de etiquetas aún
deben verificarse. No se acepta una matriz identidad como calibración recuperada.

## Verificación realizada y pendiente

Se añaden regresiones para tiempos CPU/GPU, etiquetas incompatibles, límites de
cancha, PTS variables y distinción entre predicción y observación del balón.
La inspección del clip Bayern–PSG decodifica el archivo, sin ejecutar inferencia.
El cuaderno está preparado y su sintaxis fue verificada; la ejecución sobre
una GPU de Colab sigue pendiente. Los archivos descargados no se importan
automáticamente a la aplicación.

La aceptación exige comparar grabación y transmisión del mismo clip, evaluar
anotaciones reales, ejecutar una sesión de duración de partido y medir costo,
latencia extremo a extremo y recuperación de conexión. El valor de retraso del
worker de directo mide solo procesamiento desde la recepción del cuadro.

Queda pendiente separar versiones de procesamiento en persistencia para que
reintentos o diferentes videos del mismo partido no mezclen datos. Hasta resolverlo,
usar partidos de prueba separados. Las recomendaciones del Sprint 4 necesitarán
usar cobertura y calidad como condición para evaluar sus reglas.

No se ha contratado ni desplegado ninguna instancia externa.
