# Ocho referencias para la prueba corta

Esta guía conserva las correspondencias del ensayo manual. El flujo principal
actual es [calibración dinámica](GUIA_CALIBRACION_DINAMICA.md), con reconocimiento
automático. Para usar esta tabla como respaldo, subir el clip correspondiente,
seleccionarlo en Calibrar cámara y extraer su cuadro en el segundo 0. La nueva
pantalla también incluye el punto 8 en su plantilla; no requiere modo libre.
Las instrucciones antiguas de cargar una imagen independiente se sustituyen
por esa extracción desde el video.

El primer encuadre del video completo tiene varias referencias fuera de la
imagen. No completar las ocho inventando marcas ni contando los límites de
la imagen como límites de la cancha. La plantilla actual tampoco incluye los
cruces del círculo central, aunque pueden marcarse con el modo libre.

Se preparó otro clip de unos diez segundos que comienza alrededor del segundo
18 del original. La calibración de esta guía corresponde exclusivamente a ese
nuevo clip y a su primer cuadro.

- **Cargar en calibración:** [imagen limpia](almacen/calibracion-prueba-18s/primer-cuadro.png).
- **Consultar mientras se marca:** [imagen con ocho referencias numeradas](almacen/calibracion-prueba-18s/guia-8-puntos.png).
- **Subir y procesar:** [nuevo clip](almacen/prueba-integral-calibrable-10s.mp4).

La imagen limpia se extrajo directamente del nuevo clip, a 1376 × 776 píxeles.
La imagen numerada solo sirve de guía; la cruz amarilla indica la referencia,
no el círculo que contiene su número.

## Correspondencias

Para este ensayo se conserva el supuesto de cancha de **105 × 68 m**, pendiente
de verificar. El origen del plano está abajo a la izquierda: X crece hacia la
portería derecha e Y hacia la banda opuesta.

| Nº en la guía | Referencia en la imagen | Referencia de la plantilla / modo | X (m) | Y (m) |
|---|---|---|---:|---:|
| 1 | Mediocampo con la banda lejana | Mediocampo banda superior (opuesta) | 52.50 | 68.00 |
| 2 | Mediocampo con la banda cercana | Mediocampo banda inferior (tribuna) | 52.50 | 0.00 |
| 3 | Esquina del campo arriba a la derecha | Esquina superior derecha (opuesta) | 105.00 | 68.00 |
| 4 | Vértice frontal lejano del área grande derecha | Área der. · vértice frontal superior | 88.50 | 54.16 |
| 5 | Vértice frontal cercano del área grande derecha | Área der. · vértice frontal inferior | 88.50 | 13.84 |
| 6 | Área grande derecha con la línea de meta, lado lejano | Área der. · unión superior con línea de meta | 105.00 | 54.16 |
| 7 | Área grande derecha con la línea de meta, lado cercano | Área der. · unión inferior con línea de meta | 105.00 | 13.84 |
| 8 | Cruce de la línea de mediocampo con el círculo, lado lejano | Punto libre: cruce superior del círculo en el plano | 52.50 | 43.15 |

El punto 8 es una intersección entre dos líneas pintadas. No usar el extremo
superior de la elipse por su apariencia: la referencia es donde la línea de
mediocampo cruza el círculo.

## Marcar en la aplicación

1. Seleccionar el partido y cargar la **imagen limpia nueva**. Si había puntos
   de la imagen anterior, borrarlos antes de empezar.
2. En el plano derecho, elegir el hito correspondiente al nº 1 y después
   pulsar su marca en la imagen izquierda. Repetir para los números 2 a 7.
   Se puede elegir directamente cada hito en el plano; no es necesario
   completar los que no aparecen en la imagen.
3. Pulsar **Punto libre en cancha (secundario)**. En el plano derecho, pulsar
   la intersección superior del círculo central con la línea de mediocampo.
   Después pulsar la referencia nº 8 en la imagen izquierda. El modo libre
   toma las coordenadas del clic en el plano: aproximarlas cuidadosamente a
   (52.50, 43.15); la tabla inferior muestra los metros registrados.
4. Revisar los ocho pares, guardar y comprobar el error informado. Un error
   alto exige revisar las correspondencias, no añadir puntos arbitrarios.
5. Continuar con [la guía del flujo completo](GUIA_FLUJO_COMPLETO_LOCAL.md),
   usando el **nuevo clip** para grabación y para directo simulado. Si ya se
   había procesado el clip anterior, utilizar otro partido de prueba.

No utilizar **Autocompletar 8 puntos válidos** para esta prueba: su función
actual distribuye puntos sintéticos según el tamaño de imagen; no identifica
las líneas de la fotografía. Tampoco se ha validado un modelo automático de
hitos que pueda sustituir este marcado manual.

## Comprobación realizada y límites

Se verificó que el nuevo clip es legible, conserva 1376 × 776, contiene 300
cuadros y sus tiempos avanzan en orden hasta aproximadamente 9.98 s. La imagen
de calibración es su primer cuadro decodificado.

Una selección manual aproximada de estas ocho referencias permitió calcular
la homografía con el algoritmo del backend y produjo un residual medio de
aproximadamente 0.37 m sobre los propios puntos. También se contrastaron el
punto penal y el cruce inferior del círculo, que no participaron en ese ajuste.
Es una comprobación orientativa de que las correspondencias son utilizables;
no mide la precisión real ni certifica las dimensiones asumidas del campo.
La aplicación calculará el resultado de los puntos que efectivamente marques.

No se guardó ninguna calibración automáticamente ni se ejecutó el worker con
este clip. Queda pendiente comprobar el flujo real y la estabilidad de la
referencia cuando la cámara se mueve. La calibración de este encuadre no debe
aplicarse al comienzo del video completo ni al clip anterior.
