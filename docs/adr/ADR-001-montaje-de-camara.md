# ADR-001 · Montaje de la cámara

- **Estado:** pendiente de decisión en la reunión de Sprint 0
- **Fecha:** _(completar)_
- **Participantes:** _(completar)_

## Contexto

El docente definió que la entrada del sistema debe ser una cámara. Lo que el
equipo sí decide —y es igual de determinante— es qué cámara, dónde se monta y
qué se procesa. Estas decisiones condicionan si el proyecto es entregable.

## Decisión

### 1. Cámara fija, no transmisión televisiva

_(marcar la opción acordada)_

Con cámara fija la homografía se calcula **una sola vez** antes del partido,
marcando puntos conocidos de la cancha. Con transmisión televisiva la cámara
gira y hace zoom, así que la homografía cambia en cada cuadro y hay que
estimarla continuamente detectando las líneas — un problema de investigación
abierto, con artículos dedicados solo a eso.

### 2. Altura y encuadre

- Altura acordada: ____ m (recomendado entre 5 y 8)
- Ubicación: ____________________
- Toda la cancha en cuadro: sí / no

### 3. Resolución y cantidad de cámaras

- Modelo: ____________________
- Resolución: ____________________
- Cantidad: 1 / 2 (una por mitad de cancha)

A 1080p en plano abierto un jugador ocupa 25–40 píxeles de alto y el balón
entre 5 y 12. Es el límite de lo detectable.

### 4. Máquina con GPU

- Responsable: ____________________
- GPU: ____________________

Sin GPU NVIDIA el tiempo real no es alcanzable. Descubrirlo en el Sprint 3 no
deja margen para corregir.

## Consecuencias

_(completar tras la decisión: qué habilita, qué cierra, qué riesgo queda abierto)_

## Verificación

`Pb-15` cierra este ADR: grabar un partido desde la posición definitiva y correr
YOLO preentrenado encima. El resultado confirma o refuta el montaje mientras
todavía hay tiempo de cambiarlo.
