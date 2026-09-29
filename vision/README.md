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
