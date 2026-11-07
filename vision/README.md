# Worker de visión

Ejecuta el pipeline de visión por computadora **en la máquina con GPU que va a
la cancha**. No es parte del backend: es un proceso independiente.

```
Cámara ──► YOLO ──► ByteTrack ──► color de equipo ──► homografía
                                                          │
                                        WebSocket (JSON)  ▼
                                                      Backend
```

La decisión arquitectónica central del proyecto: **el video nunca sale de la
cancha**. Solo viajan coordenadas — unas 23 posiciones cinco veces por segundo,
entre 5 y 10 KB/s. Transmitir el video al servidor sería inviable por 4G y
agregaría segundos de latencia.

## Módulos

| Carpeta | Responsabilidad | Casos de uso |
|---|---|---|
| `deteccion/` | Carga del modelo YOLO e inferencia por cuadro | CU-24 |
| `seguimiento/` | ByteTrack y clasificación de equipo por color de camiseta | CU-24, CU-25 |
| `calibracion/` | Homografía y proyección de píxeles a metros | CU-26 |
| `emisor/` | Cliente WebSocket hacia el backend | CU-32 |
| `evaluacion/` | mAP, IDF1 y error de reproyección sobre el clip de referencia | Pb-17 |
| `entrenamiento/` | Andamiaje para afinar el modelo propio de 3 clases (jugador/árbitro/balón) | CU-29 |

## Requisitos

No están instalados todavía, a propósito: `torch` y `ultralytics` pesan más de
2 GB y solo tienen sentido en la máquina que tenga GPU NVIDIA.

```bash
python -m venv venv
venv\Scripts\activate

# CUDA 12.1 — verificar la versión propia en https://pytorch.org
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

Mínimo GTX 1650 / RTX 3050; recomendado RTX 3060 o superior.

## Dos detalles que no son menores

**`vid_stride=6`** — procesar 1 de cada 6 cuadros da 5 FPS desde una fuente de
30. El análisis táctico no necesita más y baja el costo de cómputo seis veces.
Es lo que hace posible el tiempo real en una laptop.

**El punto de apoyo, no el centro de la caja** — la homografía mapea el plano
del suelo. Proyectar el centro de la caja del jugador en vez de sus pies
desplaza cada posición varios metros, y como el error crece con la distancia a
la cámara, las métricas salen mal de forma no uniforme y muy difícil de
diagnosticar.

```python
x1, y1, x2, y2 = caja
pie_x, pie_y = (x1 + x2) / 2, y2     # y2, no (y1 + y2) / 2
```

## Desarrollo

Desarrollar siempre contra video grabado y conectar la cámara en vivo al final.
Es el mismo pipeline: solo cambia el origen.

```python
modelo.track(source="partido.mp4", ...)          # durante el desarrollo
modelo.track(source="rtsp://192.168.1.50", ...)  # el día de la demostración
```

Un archivo grabado es reproducible y se depura paso a paso. Desarrollar contra
la cámara en vivo hace que cada prueba dependa del clima y de conseguir cancha.

## Verificación de campo pendiente (T-055 a T-058)

El código de `evaluacion/` (Pb-17) ya calcula mAP@50 e IDF1, con pruebas
unitarias que validan la integración con `pycocotools`/`motmetrics` sobre
datos sintéticos. Pero los criterios de aceptación de T-055 a T-058 son
empíricos: dependen de un clip real (cancha, iluminación, oclusiones) que
todavía no existe en el repositorio. No se resuelven escribiendo más código,
sino grabando/anotando ese clip y corriendo el pipeline una vez con GPU.

| Tarea | Criterio | Qué falta |
|---|---|---|
| T-055 (CU-24) | mAP@50 de jugador >= 0,85 e IDF1 >= 0,70 sobre el clip de referencia | Grabar y anotar a mano (cajas + `tid`) el clip de referencia, y correr `evaluacion.calcular_map50` / `calcular_idf1` sobre la salida real del modelo |
| T-056 (CU-24) | Recall aceptable con jugadores en oclusión parcial | Clip real con oclusiones; no hay forma sintética creíble de generarlas |
| T-057 (CU-25) | Precisión de color de camiseta con iluminación real de cancha (sol/sombra/reflectores) | Clip real: el ruido gaussiano sintético de `tests/test_color.py` no reproduce sombras duras ni reflejos |
| T-058 (CU-26) | Verificación de la homografía contra marcas físicas de la cancha | Calibrar la cámara real y medir contra puntos físicos conocidos, no contra la cámara sintética de `tests/test_homografia.py` |

Se decidió documentar este gap y avanzar con el resto del backlog en vez de
bloquear el desarrollo esperando el día de grabación.

## Modelo propio de 3 clases (CU-29) — andamiaje listo, entrenamiento pendiente

`deteccion/modelo.py::CLASES_COCO` (el modelo preentrenado que usa hoy
`seguimiento.tracker.seguir`) solo distingue "persona" y "balón": un árbitro
se detecta como jugador, y HU-21 lo separa después por color de camiseta. El
criterio de HU-20 de que YOLO detecte árbitro como clase propia requiere un
modelo afinado con datos propios (CU-29), que no se resuelve escribiendo más
código, sino anotando un clip real — igual que T-055 a T-058 arriba.

Lo que sí está listo en `entrenamiento/` para el día que ese clip exista:

- `dataset.yaml`: configuración de ultralytics con las 3 clases
  (`jugador=0, arbitro=1, balon=2`), en el mismo orden que
  `deteccion/modelo.py::CLASES_PROPIO` (una prueba en
  `tests/test_entrenamiento.py` falla si se desincronizan).
- `entrenar.py`: `entrenar()` afina YOLO11 (`yolo11n.pt`) sobre ese dataset.
  Import perezoso de `ultralytics`, igual que `deteccion/modelo.py`: se
  puede importar y probar sin GPU.

Pasos que faltan y que no son de código:

1. Grabar y anotar (cajas + clase) un clip real con formato YOLO en
   `labels/{train,val}/*.txt`, siguiendo el layout documentado en
   `entrenamiento/dataset.yaml`.
2. Correr `python -m entrenamiento.entrenar` en la máquina con GPU.
3. Subir `weights/best.pt` a un storage con URL https y registrarlo con
   `POST /vision/modelos` (`backend/app/vision/schemas.py::ModeloCrear`),
   activarlo, y solo entonces cambiar `ConfigModelo.clases` de
   `CLASES_COCO` a `CLASES_PROPIO` en el worker.
