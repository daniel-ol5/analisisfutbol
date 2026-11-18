# Verificación local del worker y del panel

Fecha: 16/11/2026. Entorno: Windows, Python 3.12, CPU; sin Torch, Ultralytics ni GPU.
No se hicieron commits, push, despliegues ni contrataciones.

## Evidencia de software

| Verificación | Resultado |
|---|---|
| Backend, batería completa | 541 pruebas pasan |
| Backend, persistencia y procesamiento después de la corrección de métricas | 48 pruebas pasan; incluye la nueva integración de métricas de grabación |
| Visión, batería final sin GPU | 114 pruebas pasan |
| Frontend | 84 pruebas pasan; compilación de producción correcta |
| Ruff sobre Python modificado | Sin errores |
| Navegador Chrome con API y WebSocket simulados | Escritorio 1440×1000 y móvil 390×844; sin errores JavaScript ni desbordamiento horizontal |
| Interrupción del worker en el navegador | Las posiciones desaparecen a los 2 s sin muestras nuevas |
| Cuaderno Colab | Sintaxis Python de sus celdas verificada; sin ejecución de GPU |
| Paquete Colab | 30 archivos de código/configuración, con hashes verificados; sin credenciales ni videos |

La compilación web conserva el aviso de un bundle superior a 500 kB. El linter
web conserva avisos de React; no hay errores de lint. La comprobación visual usó
telemetría ficticia identificada como prueba, no detecciones del video real.

## Corrección del diagnóstico durante la prueba de Colab

El usuario reportó que el paso de grabación terminó y la comprobación posterior
mostró CPU. La comprobación leía los pesos base de YOLO; versiones de Ultralytics
pueden copiar esos pesos al construir el predictor, por lo que ese valor no
demuestra el dispositivo que ejecutó la inferencia. Se cambió el cuaderno y el
informe para consultar el dispositivo del predictor. Se añadió `lap` a los
requisitos para instalarlo antes del primer seguimiento.

Después de la corrección pasaron 119 pruebas de visión en la batería completa;
la regresión final pasó 10 pruebas, incluyendo ambas celdas con predictor CUDA
y pesos base CPU, y el rechazo de un predictor que realmente usa CPU. Estas
regresiones utilizan dobles de prueba, no una GPU física. La lectura del
predictor de la sesión del usuario sigue pendiente de confirmar.

### Primera inferencia GPU confirmada por el usuario

El usuario ejecutó una comprobación independiente con YOLO11n en Colab y reportó:

- CUDA disponible y NVIDIA Tesla T4.
- Un cuadro de inferencia de 384 × 640 con 12 detecciones de persona.
- 2,9 ms de preprocesamiento, 8,2 ms de inferencia y 1,3 ms de posprocesamiento.
- El evento `on_predict_postprocess_end` registró `cuda:0` durante la inferencia.

Esto confirma esa inferencia de un cuadro, no el dispositivo del ensayo anterior
ni rendimiento sostenido, tracking, geometría o precisión. El worker conserva
ahora esa lectura del evento para no depender de la disponibilidad posterior
del predictor. Se preparó `vision/notebooks/Continuar_prueba_Colab.py` para comparar
grabación y directo simulado sobre 30 s a 1280, en carpetas nuevas y reutilizando
el video subido. La batería completa posterior pasó 122 pruebas; la regresión
final de diagnóstico y continuación pasó 9 pruebas con dobles de prueba.

## Archivo inspeccionado

`BAYERN - PSG CAMARA TACTICA - YouTube - Google Chrome 2026-11-16 10-12-48.mp4`:

- 1376 × 776 píxeles; 4574 cuadros decodificados.
- FPS nominales: 30,0309. Último PTS: 152,2937 s.
- Cero PTS no crecientes; los intervalos entre cuadros varían.
- Se verificó decodificación y reloj, sin inferencia ni medición de precisión.

## Correcciones verificadas

- El stride no modifica la duración del video y la publicación a 5 Hz es independiente.
- Las etiquetas del checkpoint se comprueban antes de interpretar detecciones.
- GMC conserva escala y rotación. Una referencia perdida requiere reanclaje absoluto.
- Se descartan coordenadas fuera de cancha; no se pegan al borde del radar.
- Las predicciones del balón no se publican como observaciones.
- Reproducir telemetría no vuelve a insertar posiciones.
- Las grabaciones registran equipos y recalculan métricas al terminar si no están EN_CURSO.
- La API no inicia inferencia en su CPU por defecto. El directo dispone de un lector
  con un solo cuadro pendiente y utiliza el mismo ensamblado de mensajes que la grabación.

## Pendiente antes de aceptar un partido real

1. Ejecutar el cuaderno de Colab, descargar la evidencia y medir rendimiento real.
2. Identificar y validar pesos especializados y el orden del checkpoint de cancha.
3. Anotar tramos independientes para medir detección, IDs, equipos, balón y error geométrico.
4. Separar ejecuciones de procesamiento en persistencia. Actualmente, reintentos o
   videos diferentes del mismo partido pueden mezclar resultados; usar partidos de prueba separados.
5. Ensayar cámara, transporte, API y WebSocket juntos; medir latencia extremo a extremo,
   reconexiones y una sesión de duración de partido. El directo simulado de Colab no lo sustituye.

La guía operativa está en [GUIA_PRUEBAS_LAPTOP_GPU.md](../../GUIA_PRUEBAS_LAPTOP_GPU.md).
El sistema todavía no se considera validado para un partido real ni para reglas tácticas del Sprint 4.
