# Probar la calibración dinámica desde la aplicación

La calibración ahora reconoce marcas del campo, sigue los paneos y recupera
referencias contra imágenes ya calibradas. Se usa una cámara situada en un
punto fijo de la tribuna que gira o hace zoom. Una zona fuera de cámara queda
no observada.

## Preparación en esta máquina

Ya se aplicó la migración `a9d8c1e7f302` a la base local. La API respondió en
el puerto 8000 con el contrato actualizado. La web de esta sesión quedó en
[http://127.0.0.1:5174](http://127.0.0.1:5174).

Los dos checkpoints usados en las pruebas están instalados localmente en
`vision/pesos`: `yolo11n.pt` y `yolo_cancha_keypoints.pt`. No se incluyen en el
paquete de código de Colab. La referencia de origen y SHA256 del segundo está
en [MODELO_CANCHA.md](vision/calibracion/MODELO_CANCHA.md).

En otra instalación del proyecto:

```powershell
cd "C:\Users\Juan Carlos\Desktop\Daniel\SW1\deportivo\analisisfutbol\backend"
.\venv\Scripts\python.exe -m alembic upgrade head
```

El worker requiere su entorno con Torch y `vision/requirements.txt`. Para
instalar el modelo de cancha, desde `vision`:

```powershell
..\.venv\Scripts\python.exe -m calibracion.instalar_modelo
```

## Grabación

1. Iniciar sesión con una cuenta ADMIN o ANALISTA propia.
2. Crear un **partido nuevo de prueba** en Gestión Deportiva. Mantenerlo sin
   iniciar mientras se procesa la grabación. No reutilizar ensayos anteriores
   como mediciones independientes: la separación histórica de ejecuciones de
   análisis todavía necesita trabajo adicional.
3. En **Video del partido**, seleccionar ese partido y subir
   `almacen/prueba-integral-10s.mp4`. Es el clip usado en la prueba integral.
4. En **Calibrar cámara**, seleccionar el mismo partido, **Grabación subida**
   y el video. Elegir **Reconocimiento automático**. Confirmar las dimensiones
   del campo; 105 × 68 m sigue siendo un supuesto para este material.
5. Pulsar **Guardar configuración**. No hace falta marcar ocho puntos. Este
   paso configura el reconocimiento; la referencia se verifica durante el
   procesamiento, no al pulsar Guardar.
6. Volver a Video del partido, indicar camisetas roja y oscura y pulsar
   **Procesar**. Después ejecutar el worker desde `vision`:

```powershell
..\.venv\Scripts\python.exe -m procesamiento.worker --api http://127.0.0.1:8000/api --email TU_CORREO --dispositivo cpu --clases coco --tamano-img 640 --stride 6 --una-vez
```

La contraseña se solicita en la terminal. Encolar antes de ejecutar
`--una-vez`: si no encuentra trabajo, termina.

7. Esperar a **PROCESADO** y abrir Análisis → Grabación. Seleccionar el video,
   activar **Mostrar detecciones** y **Verificar líneas de cancha**. Comprobar
   el estado de referencia, la alineación y el área visible del plano.

En CPU este ensayo comprueba funcionamiento. El tamaño 640 y las camisetas
por color no validan detección de balón, árbitros o identidad individual.

## Directo simulado desde la aplicación

1. Crear **otro partido nuevo** para el directo.
2. En Calibrar cámara, seleccionar ese segundo partido y **Cámara en directo**.
   Usar el nombre `camara-principal`, las dimensiones del campo y reconocimiento
   automático. Guardar.
3. En Operación del Partido, seleccionar el segundo partido, indicar dirección
   de ataque e iniciarlo. En Análisis, seleccionar el partido y **Directo**.
4. Ejecutar desde `vision`, sustituyendo correo e ID del partido:

```powershell
..\.venv\Scripts\python.exe -m procesamiento.directo --api http://127.0.0.1:8000/api --email TU_CORREO --partido ID_DIRECTO --fuente "..\almacen\prueba-integral-10s.mp4" --fuente-id camara-principal --simular-directo --dispositivo cpu --tamano-img 640 --clases coco --color-propio "#C8102E" --color-rival "#17202A"
```

El archivo entra con su reloj real. El lector conserva el cuadro más reciente
y descarta atrasados si la CPU no alcanza. No se debe formar una cola que
termine analizando jugadas antiguas como si fueran actuales.

El panel recibe telemetría por WebSocket; este comando no retransmite el video
al navegador. La vista previa local de cámara tampoco envía imagen al worker.
Al terminar el clip se deja de recibir telemetría. Finalizar el partido en
Operación para cerrar sus métricas.

Una cámara real sustituye la ruta del archivo por su índice o URL de captura,
y se omite `--simular-directo`. La fuente debe conservar el nombre configurado.
El transporte de una cámara local a una GPU remota necesita una prueba aparte.

## Respaldo manual

Para una grabación, seleccionar video y segundo y pulsar **Ver cuadro del
video**. El servidor devuelve la imagen junto a su PTS, resolución e índice.
Elegir Referencia manual de respaldo y marcar ocho correspondencias reales.
La plantilla incluye cruces del círculo, punto central, áreas chicas y penales.
No existe el autocompletado sintético anterior.

La referencia se aplica en su cuadro, incluso si el worker está usando stride;
no se utiliza antes de ese instante. Después se sigue y recupera dinámicamente.
Para un encuadre sin referencias identificables, esperar otra vista o utilizar
el reconocimiento automático. No inventar puntos para superar la validación.

## Ensayo con Colab

Abrir [Calibracion_dinamica_Colab.ipynb](vision/notebooks/Calibracion_dinamica_Colab.ipynb)
en Colab. Seleccionar GPU y ejecutar sus celdas. Se suben el paquete de código
preparado y el video; el cuaderno descarga y verifica el modelo de cancha.
Compara grabación y directo simulado y exporta resultados.

El paquete de esta versión es
[worker-calibracion-dinamica-2026-11-17.zip](almacen/worker-calibracion-dinamica-2026-11-17.zip).
Para cambios posteriores, generar uno nuevo desde `vision`:

```powershell
..\.venv\Scripts\python.exe -m evaluacion.preparar_colab --salida "..\almacen\worker-calibracion-otra-version.zip"
```

Este cuaderno es una evaluación interactiva y no conecta automáticamente la
GPU con la API local. La ejecución de Colab del pipeline rediseñado, la cámara
real, la red remota y las dos horas continuas siguen pendientes de aceptación.

## Evidencia disponible

El [informe de validación](docs/validacion/CALIBRACION-DINAMICA-2026-11-17.md)
detalla las pruebas, resultados y límites de precisión. El estado «verificada»
indica que el método superó controles geométricos; no certifica exactitud
táctica en cualquier punto de la cancha.

No se hicieron commits ni push.
