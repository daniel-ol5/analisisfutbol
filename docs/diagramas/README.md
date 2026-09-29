# Diagramas

Los diagramas son **código**, no imágenes. Se editan en `.puml` y se versionan;
los `.png` y `.svg` son salida generada y se regeneran cuando cambia el fuente.

| Archivo | Contenido |
|---|---|
| `modelo-datos.puml` | Modelo completo: 19 tablas con todos sus atributos, tipos y notas de diseño |
| `modelo-datos-resumen.puml` | Solo entidades y relaciones. Para presentaciones y para entender la forma general |

En ambos, el color verde marca lo que ya está implementado. Hoy son `club` y
`usuario`; los otros 17 modelos están diseñados pero pendientes.

## Cómo regenerarlos

**Opción 1 — VS Code (la más cómoda para editar)**

Instalar la extensión `jebbs.plantuml`, abrir el `.puml` y pulsar `Alt+D` para
la vista previa en vivo. Necesita Java instalado.

**Opción 2 — línea de comandos**

```bash
# descargar una vez
curl -L -o plantuml.jar https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar

# regenerar
java -jar plantuml.jar -tpng docs/diagramas/*.puml
java -jar plantuml.jar -tsvg docs/diagramas/*.puml

# validar sintaxis sin generar nada
java -jar plantuml.jar -checkonly docs/diagramas/*.puml
```

**Opción 3 — sin instalar nada**

Pegar el contenido del `.puml` en <https://www.plantuml.com/plantuml/uml/>.

> El `-checkonly` conviene agregarlo a la integración continua: detecta un
> diagrama roto en el Pull Request en vez de en la defensa.

## Para qué sirve cada formato

- **SVG** — es vectorial, así que se puede acercar sin perder nitidez. Es el
  formato correcto para el modelo detallado, que a tamaño completo supera el
  límite de 4096 px que PlantUML aplica a los PNG.
- **PNG** — para pegar en el documento de entrega o en una presentación.

## Pendientes

- `casos-uso.puml` — diagrama de casos de uso por paquete
- `arquitectura.puml` — diagrama de despliegue: worker en cancha, API en la nube
