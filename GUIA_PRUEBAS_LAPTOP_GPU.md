# Pruebas de visión en CPU y GPU remota

Esta guía distingue verificación de software, inferencia sobre video y validación
con anotaciones reales. Pasar pruebas sintéticas no demuestra precisión en cancha.
Ya se recibió un primer ensayo de detección y seguimiento en una T4 de Colab.
La precisión y la conexión completa con la aplicación siguen pendientes de validar.

Para comprobar el circuito desde la web con un clip corto y CPU local, usar
[GUIA_FLUJO_COMPLETO_LOCAL.md](GUIA_FLUJO_COMPLETO_LOCAL.md). Esa prueba no
sustituye la conexión con la GPU remota. El primer ensayo de T4 recibido ya está
documentado en [el informe de Colab](docs/validacion/COLAB-2026-11-16-f3114175.md).

## Estado del proyecto

- El worker diferido y `procesamiento.directo` usan el mismo ensamblado de
  posiciones, clasificación, seguimiento del balón y proyección.
- El reloj usa los tiempos del decodificador. Inferir cada cuadro no multiplica
  la duración del partido; publicar posiciones a 5 Hz es una decisión independiente.
- La API coordina trabajos. Por defecto **no inicia un worker en la CPU del servidor**.
  `VISION_AUTO_WORKER=true` habilita el comportamiento local anterior, solo para pruebas.
- La reproducción en la web consulta las muestras del video sin reinsertarlas.
- Al terminar una grabación se recalculan las métricas con los equipos detectados,
  salvo si el partido está EN_CURSO y el motor de directo es el dueño de las métricas.
- Los pesos especializados **no están incluidos**. Deben obtenerse de una fuente
  identificada y validarse contra sus clases. El arranque falla si son incompatibles.
- Sin pesos especializados se puede probar con COCO (`yolo11n.pt`), que detecta
  personas y balón; no es evidencia de detección especializada de árbitros.
- Los puntos de cancha necesitan un checkpoint compatible con el orden de las
  32 marcas definido en `vision/calibracion/dinamica.py`. Tener cualquier modelo
  de pose no cumple este requisito. Ese checkpoint sigue pendiente de validar.
- Cuando se pierde la referencia de cámara se marca la calibración como inválida
  y se dejan de publicar posiciones métricas. La recuperación automática necesita
  referencias de cancha verificadas; el flujo óptico por sí solo puede derivar.

## 1 Preparación local sin GPU

Desde la raíz, PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt -r vision/requirements-pruebas.txt
```

Esto instala pruebas y decodificación de video, sin Torch ni Ultralytics.

```powershell
cd vision
..\.venv\Scripts\python -m pytest
cd ..\backend
..\.venv\Scripts\python -m pytest
cd ..\web
npm.cmd ci
npm.cmd test
npm.cmd run build
```

Las pruebas del backend usan `backend/test.db`, separada de la base de desarrollo.
Para inspeccionar el archivo proporcionado, desde `vision`:

```powershell
..\.venv\Scripts\python -m evaluacion.inspeccionar_video "..\almacen\BAYERN - PSG CAMARA TACTICA - YouTube - Google Chrome 2026-11-16 10-12-48.mp4"
```

El informe contiene resolución, cantidad de cuadros y tiempos reales; no ejecuta
inferencia. El archivo es una captura de 1376 × 776, de unos 152 segundos,
y no conserva todo el detalle del original de YouTube.

## 2 Preparar una sesión GPU

### Primera prueba: Google Colab

El equipo eligió **probar primero Colab**. Abrir
[Primera_prueba_Colab.ipynb](vision/notebooks/Primera_prueba_Colab.ipynb) mediante
Archivo → Subir cuaderno en [Colab](https://colab.research.google.com/).
Seleccionar un entorno con GPU y ejecutar las celdas en orden.

Preparar el código en la laptop, desde `vision`:

```powershell
..\.venv\Scripts\python -m evaluacion.preparar_colab
```

El comando muestra la ruta de `analisisfutbol-colab.zip` en la carpeta temporal.
No sobrescribe un paquete existente: cambiar `--salida` para otro ensayo.
Incluye solo código y configuración del worker, con hashes por archivo.
No incluye `.env`, videos, pesos, bases de datos, `.git` ni credenciales.

En el cuaderno:

1. Subir ese ZIP, instalar requisitos y comprobar CUDA.
2. Subir el video. Para el primer ensayo, conservar el límite de 30 segundos.
3. Para detección y seguimiento, mantener `USAR_CALIBRACION=False`.
4. Para posiciones en metros, descargar `primer-cuadro.png` desde Archivos de
   Colab, calibrarlo en la aplicación local, guardar y pulsar **Descargar calibración**.
   Subir ese JSON con `USAR_CALIBRACION=True`. Debe corresponder a ese primer encuadre
   y a la resolución original; no sustituirlo por una matriz identidad.
5. Ejecutar grabación y directo simulado con las mismas opciones.
6. Descargar el ZIP con cajas por cuadro, muestras métricas opcionales, capturas,
   tiempos, versiones, GPU y hashes. Conservarlo antes de desconectar el entorno.

El ensayo usa el código del proyecto sin conectar la API local a Internet.
Los resultados se descargan para revisión; **no se importan automáticamente a
la aplicación**. El directo simulado procesa el archivo a velocidad real con el
lector que descarta cuadros atrasados: no prueba transporte de cámara ni WebSocket.

El dispositivo observado se consulta en el predictor de Ultralytics. Sus pesos
originales pueden permanecer en CPU mientras una copia realiza la inferencia
en CUDA. Consultar solo `YOLO.model.parameters()` puede producir un diagnóstico
incorrecto. `lap` se instala con los requisitos antes de iniciar el seguimiento.
La lectura se conserva desde el evento `on_predict_postprocess_end`, aunque el
predictor sea liberado después. Para continuar una sesión que ya tiene el video
subido, copiar [Continuar_prueba_Colab.py](vision/notebooks/Continuar_prueba_Colab.py)
completo en una celda nueva. Por defecto ejecuta ambos ensayos sin calibración,
verifica CUDA durante la inferencia y descarga un ZIP; no requiere repetir la
subida del video. Para la segunda fase, cambiar `USAR_CALIBRACION_ENSAYO` a `True`
y subir el JSON válido de la aplicación cuando lo solicite. Mantener los mismos
pesos y tamaño de inferencia para comparar con el primer ensayo.

Según la [FAQ oficial](https://research.google.com/colaboratory/faq.html), Colab
no garantiza GPU, límites ni duración de sesión. Se usa aquí como cuaderno
interactivo de evaluación. No instalar servidores SSH ni mantener workers
distribuidos en su modalidad gratuita. Un directo de partido completo sigue
necesitando validar un entorno estable. No se ha ejecutado este cuaderno en
una GPU de Colab todavía.

### Alternativa posterior para el directo: instancia con SSH

Si Colab no cubre la siguiente fase, evaluar **Vast.ai bajo demanda**, una A5000 o
3090/4090 de 24 GB, solo durante sesiones concretas. El worker es independiente
del proveedor. Comparar costo por minuto de video y retraso del directo.
No hay una instancia contratada ni una cuenta conectada por este proyecto.

En [Vast.ai](https://cloud.vast.ai/), crear/verificar la cuenta y revisar el saldo.
Para SSH, registrar una clave pública propia siguiendo su
[guía oficial](https://docs.vast.ai/guides/instances/connect/ssh.md).
La clave privada permanece en la laptop. Seleccionar una oferta con:

- Una GPU de 24 GB, al menos 16 GB de RAM y espacio suficiente para entorno y clip.
- Modalidad **on-demand** para el directo; una oferta interrumpible puede detenerse.
- Host verificado, duración disponible mayor que el ensayo y buena conexión.
- Desglose visible de cómputo, disco y transferencia de datos en ambas direcciones.

Los precios son de mercado, no una tarifa fija del proyecto. Una primera prueba
de dos horas debe cotizarse antes de contratar, dentro del presupuesto total de
US$10–20. A 5 Mbit/s, 90 minutos de video representan aproximadamente 3,4 GB de
entrada, además de resultados y archivos. El almacenamiento se cobra mientras
existe la instancia, incluso detenida: descargar los resultados antes de eliminarla.

Seleccionar una plantilla PyTorch con CUDA compatible con el controlador del host.
Comprobar primero:

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'SIN CUDA')"
```

Transferir el código autorizado mediante un ZIP o SCP, sin incluir `.env`, `.git`,
entornos virtuales, `node_modules` o videos innecesarios. No se necesita hacer
commits ni push para ejecutar el worker remoto.

```bash
cd /workspace/analisisfutbol
python -m pip install -r vision/requirements.txt
python -m pip freeze > /workspace/entorno-prueba.txt
```

Guardar la versión de Python, Torch, Ultralytics, GPU, pesos y sus hashes en cada
ensayo. Un rendimiento sin esa información no es reproducible.

## 3 Conectar la API local sin abrirla a Internet

Los pasos 3–5 corresponden a una instancia propia con SSH. El cuaderno de Colab
del paso 2 funciona por archivos y no necesita estos túneles.

La API puede seguir en la laptop i5. El worker de la nube no puede acceder a
`localhost` de esa laptop directamente. Usar una API desplegada con HTTPS o un
túnel SSH. Ejemplo desde la laptop, con los datos de SSH del proveedor:

```powershell
ssh -N -R 18000:127.0.0.1:8000 -L 19000:127.0.0.1:19000 USUARIO@HOST -p PUERTO_SSH
```

Esto permite al worker acceder a la API mediante `http://127.0.0.1:18000/api`.
El segundo reenvío sirve para el ensayo de video comprimido del paso 5.
Mantener esa terminal abierta. No desactivar el firewall.

## 4 Procesar una grabación

En la web: crear un partido de prueba separado, calibrar su primer encuadre,
subir un video y solicitar procesamiento. **Un partido en movimiento requiere
validar la referencia durante los paneos**, no solo calibrar su primer cuadro.

En Bash de la GPU, introducir la contraseña sin guardarla en scripts:

```bash
read -s -p "Contraseña: " VISION_PASSWORD; export VISION_PASSWORD; echo
cd /workspace/analisisfutbol/vision
python -m procesamiento.worker --api http://127.0.0.1:18000/api --email ANALISTA --dispositivo cuda:0 --clases coco --tamano-img 1280 --una-vez
```

Para pesos de fútbol de cuatro clases, instalarlos previamente en
`vision/pesos/yolov8_futbol.pt` y usar `--clases futbol`. Comprobar procedencia,
orden de clases y métricas; el nombre del archivo no acredita su calidad.
El worker valida `modelo.names` antes de interpretar detecciones.

No usar dos procesamientos del mismo partido como si fueran mediciones
independientes: la separación por ejecuciones y sustitución de resultados en
la base es un punto pendiente de la siguiente fase. Usar partidos de prueba separados.

En Análisis → Grabación, escoger el video procesado. El reloj, las cajas y el
plano siguen el tiempo del reproductor. Pausar o buscar no debe insertar filas.
Un archivo local en Vista previa no se analiza automáticamente.

## 5 Ensayar directo

Primero probar el mismo archivo a velocidad real. Crear otro partido de prueba,
calibrarlo e iniciarlo desde Operación del partido. La ingesta exige EN_CURSO.
En la GPU, usando una ruta de video accesible allí:

```bash
python -m procesamiento.directo --api http://127.0.0.1:18000/api --email ANALISTA --partido ID --fuente /workspace/clip.mp4 --simular-directo --dispositivo cuda:0 --clases coco --color-propio '#C8102E' --color-rival '#17202A'
```

Para medir el transporte desde la laptop, el receptor puede abrir una entrada TCP:

```bash
python -m procesamiento.directo --api http://127.0.0.1:18000/api --email ANALISTA --partido ID --fuente 'tcp://127.0.0.1:19000?listen=1' --dispositivo cuda:0 --clases coco --color-propio '#C8102E' --color-rival '#17202A'
```

Iniciar inmediatamente el emisor local con FFmpeg, por el túnel SSH del paso 3:

```powershell
ffmpeg -re -i "RUTA_DEL_VIDEO.mp4" -an -c:v libx264 -preset ultrafast -tune zerolatency -b:v 5M -maxrate 5M -bufsize 1M -f mpegts tcp://127.0.0.1:19000
```

La entrada TCP depende del soporte FFmpeg del OpenCV de la instancia. Se debe
verificar en la sesión alquilada; este transporte no se ha ensayado todavía.
Para la cámara real se sustituye la entrada de archivo por su RTSP o dispositivo
de captura. No cambiar de encuadre, resolución o fuente sin verificar calibración.

El worker conserva un solo cuadro pendiente para no acumular una cola atrasada.
`retraso_s` mide procesamiento desde la recepción del cuadro, **no todo el tránsito
de red**. La latencia de cámara a pantalla se debe medir aparte con un reloj visible.
En Análisis → Directo, el plano recibe las posiciones por el canal de partido.
La vista previa de cámara del navegador es local y no transporta video a la GPU.

## 6 Aceptación antes de cerrar la fase

Registrar resultados por clip y por configuración:

| Prueba | Evidencia requerida |
|---|---|
| Tiempo | Las últimas posiciones coinciden con la duración real; sin multiplicaciones por stride |
| Modelos | Clases verificadas, origen y hash de cada checkpoint |
| Detección y seguimiento | mAP e IDF1 en anotaciones reales; mínimos del backlog: 0,85 y 0,70 |
| Equipos | Matriz de confusión, incluyendo árbitro, portero y desconocido |
| Balón | Precisión y cobertura solo cuando es visible; predicción separada de observación |
| Calibración | Error sobre marcas independientes, al principio y durante paneos; detectar izquierda/derecha ambiguas |
| Encuadre | Personas fuera del terreno excluidas; posiciones fuera de vista no inventadas |
| Directo | Sin retraso creciente; objetivo inicial de latencia extremo a extremo menor a 2 s |
| Resistencia | Sesión de duración de partido, reconexión, expiración de tokens, cancelación |
| Datos | Reproducir no cambia filas; reintentar un procesamiento no debe mezclar ejecuciones |

La primera batería debe usar tramos cortos anotados de este video y un clip
independiente para evaluar. Ajustar y medir sobre cuadros vecinos del mismo tramo
puede ocultar errores. Para recomendaciones colectivas, registrar también cobertura
del encuadre: observar solo media cancha no permite afirmar que la otra está vacía.

Detener la GPU al terminar, descargar los resultados y revisar almacenamiento
persistente: detener cómputo no necesariamente detiene todos los cargos.

Referencias: [precios Vast.ai](https://docs.vast.ai/guides/instances/pricing.md),
[tipos de instancia](https://docs.vast.ai/guides/instances/choosing/instance-types.md),
[seguimiento Ultralytics](https://docs.ultralytics.com/modes/track),
[calibración SoccerNet](https://www.soccer-net.org/tasks/camera-calibration).
