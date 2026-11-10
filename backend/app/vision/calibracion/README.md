# Corrección de la distorsión del lente — T-036 (CU-23)

Módulo con **funciones puras** (sin base de datos ni HTTP). Ya está integrado
con la API:

- `POST /api/vision/calibracion-intrinseca` calibra el lente a partir de fotos
  del tablero (`app/vision/router.py` y `service.calibrar_intrinseca`).
- `POST /api/vision/partidos/{id}/calibracion` y `/validar` corrigen los
  `puntos_imagen` antes de la homografía de T-029 cuando reciben
  `matriz_camara`, `coef_distorsion` y `tamano_imagen` (`service._puntos_imagen`).

**Por qué hace falta.** Con un gran angular o una action cam, las rectas de la
cancha salen curvas cerca de los bordes del cuadro. La homografía supone que
las rectas siguen siendo rectas, así que no puede compensarlo: en la prueba
sintética, un jugador cerca de la banda queda a **1,75 m** de su posición real
(y el error se reparte: hasta 1,06 m en el centro). Corrigiendo antes, los dos
quedan en **0,01 m**.

## Uso

```python
from app.vision.calibracion import (
    calibrar, precalcular_mapa, corregir_imagen, corregir_puntos, CalibracionIntrinseca,
)

# 1. Una vez por cámara y lente (no por partido): fotos del ajedrez
calibracion = calibrar(fotos, patron=(9, 6))       # esquinas INTERIORES del tablero
calibracion.error_reproyeccion_px                   # < 0,5 px: buena calibración
datos = calibracion.a_dict()                        # JSON, para guardarlo

# 2. Una vez al arrancar el partido: el mapa (lo caro)
calibracion = CalibracionIntrinseca.desde_dict(datos)
mapa = precalcular_mapa(calibracion)

# 3a. Por fotograma, si se quiere la imagen corregida (un remap, barato)
cuadro_corregido = corregir_imagen(cuadro, mapa)

# 3b. O, más barato todavía, corregir solo los puntos (lo que usa la homografía)
pies_corregidos = corregir_puntos(pies_px, calibracion, mapa)   # Nx2
```

### Cómo sacar las fotos del ajedrez

- Tablero impreso de 10 × 7 casillas (9 × 6 esquinas interiores), **rígido y plano**.
- **15 o más fotos**, con la misma resolución con la que se va a filmar.
- El tablero **entero** en cada foto, inclinado de distintas formas y, sobre
  todo, **llegando a las cuatro esquinas y a los cuatro bordes del cuadro**. Es
  ahí donde la distorsión es mayor. Sin esas fotos, la calibración igual da un
  error de reproyección bajo, pero en las esquinas el error se dispara (en la
  prueba sintética pasó de 0,5 px a 30 px).
- Mínimo aceptado: 5 fotos con el patrón detectado (`MIN_IMAGENES`). Si no se
  llega, se lanza `CalibracionInsuficiente`.

## Integración con la homografía (T-029)

La regla es una sola: **la homografía se calcula y se aplica en el espacio
corregido**. Todo punto en píxeles pasa por `corregir_puntos` antes de tocar la
matriz H, tanto al calibrar como en cada fotograma.

```
               píxeles del cuadro            píxeles corregidos             metros
puntos_imagen ─────────────────▶ corregir_puntos ─────────────▶ findHomography(…, puntos_cancha) ─▶ H
pies del jugador ──────────────▶ corregir_puntos ─────────────▶ perspectiveTransform(…, H) ─────────▶ (x, y) m
```

| Función | Recibe | Devuelve |
|---|---|---|
| `calibrar(imagenes, patron=(9, 6))` | Fotos del ajedrez (BGR o gris), todas del mismo tamaño | `CalibracionIntrinseca` |
| `precalcular_mapa(calibracion, alfa=0.0)` | La calibración | `MapaCorreccion` (mapas para `remap` y `matriz_nueva`, la K' de la imagen corregida) |
| `corregir_puntos(puntos, calibracion, mapa=None, alfa=0)` | Lista o array de `(x, y)` en píxeles del cuadro **original** | Array `Nx2` en píxeles de la imagen **corregida**. Sin `mapa` usa `matriz_corregida(calibracion, alfa)` |
| `matriz_corregida(calibracion, alfa=0.0)` | La calibración | K' de la imagen corregida, sin calcular el mapa (lo que usa la API) |
| `corregir_imagen(imagen, mapa)` | Un cuadro del tamaño calibrado | El cuadro corregido, mismo tamaño |
| `CalibracionIntrinseca.a_dict()` / `desde_dict()` | — | JSON con `matriz_camara`, `coef_distorsion`, `tamano_imagen`, `error_reproyeccion_px`, `imagenes_usadas` |

Cómo quedó integrado (T-036):

1. **Calibrar el lente:** `POST /api/vision/calibracion-intrinseca` con 5 a 20
   fotos del tablero. Devuelve `matriz_camara`, `coef_distorsion`,
   `tamano_imagen`, `error_reproyeccion_px` e `imagenes_usadas`. No guarda nada.
2. **Calibrar la cancha:** `POST /api/vision/partidos/{id}/calibracion` con los
   puntos y esos tres campos (campos nuevos y opcionales del contrato; los
   extra se ignoran). La API corrige `puntos_imagen` con `alfa=0` antes de
   `calcular_homografia`, y los residuos de CU-21 salen ya corregidos.
   `matriz_camara` y `tamano_imagen` se guardan en dos columnas JSON nuevas de
   `calibracion`.
3. **En el worker** (pendiente, ver abajo): al arrancar, `desde_dict` con los
   tres campos de la calibración + `precalcular_mapa(alfa=0)`, una vez. Por
   fotograma: `corregir_puntos` sobre el punto de apoyo de cada detección
   (centro inferior de la caja) y después `matriz_h`.
4. Sin los tres campos (cámara sin distorsión apreciable, o clientes viejos que
   mandan solo `coef_distorsion`), no se corrige nada y todo sigue igual que
   antes de T-036.

### ⚠️ Lo que falta del lado del worker

Cuando una calibración trae `matriz_camara`, su `matriz_h` va de píxeles
**corregidos** a metros. Si el worker la aplica a píxeles crudos, las
posiciones salen mal en toda la cancha. Hoy `POST /vision/trabajos/tomar`
(`Trabajo`) entrega `matriz_h` pero no la intrínseca: hay que agregarle esos
tres campos (cambio aditivo) y corregir en el worker antes de aplicar H. Hasta
entonces, no enviar la intrínseca en partidos que se procesen con el worker.

### Notas

- `alfa=0` (por defecto) recorta los bordes negros que deja la corrección. Si
  así se pierde una banda de la cancha, usar `alfa=1` (conserva todo el cuadro,
  con bordes negros). El `mapa.matriz_nueva` cambia con `alfa`: la homografía
  debe calcularse con el mismo mapa que se use después.
- La calibración es por cámara **y** por lente y resolución: si cambia el
  zoom o la resolución de grabación, hay que recalibrar.
- Funciona con OpenCV 4.10+ y 5.x (`invertir_distorsion` cubre el cambio de API
  de `undistortPointsIter`).

## Pruebas

`backend/tests/test_vision_distorsion.py` renderiza fotos sintéticas del ajedrez
con una cámara gran angular conocida, calibra sin usar los valores verdaderos y
verifica el criterio de CU-23:

| | Centro | Borde y esquinas |
|---|---|---|
| Píxeles, sin corregir | 0,0 px | 27 – 143 px |
| Píxeles, corregido | 0,03 px | 0,02 – 0,51 px |
| Metros (homografía de la cancha), sin corregir | 1,06 m | 1,75 m |
| Metros, corregido | 0,01 m | 0,01 m |
