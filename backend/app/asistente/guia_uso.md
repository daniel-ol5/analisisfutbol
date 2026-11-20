# Guía de uso de Área Técnica

Área Técnica analiza los partidos de tu club con una cámara: sigue a los
jugadores y al balón, calcula métricas (posesión, distancias, sprints) y te da
recomendaciones tácticas durante el partido. Funciona en la **web** (computadora)
y en la **app móvil** (celular). Algunas tareas solo se pueden hacer en la web.

## Roles

| Rol | Qué puede hacer |
|---|---|
| Administrador (ADMIN) | Todo: usuarios del club, equipos, partidos, cámara, partido en vivo, análisis y recomendaciones. |
| Director Técnico (DT) | Equipos y plantel, programar partidos, alineación, registrar eventos, ver análisis, recomendaciones y reglas tácticas. |
| Analista (ANALISTA) | Cámara y videos, calibración, iniciar y finalizar el partido, asignar jugadores a lo detectado, análisis y recomendaciones. |
| Asistente (ASISTENTE) | Consultar equipos y plantel, alineación, registrar eventos del partido, subir videos y ver el análisis. No ve recomendaciones. |

Solo el Administrador crea usuarios. Cada usuario ve únicamente los datos de su club.

## El flujo completo, paso a paso

### 1. Registrar el club
- Web: en la pantalla de inicio de sesión, opción de registro (`/registro`). Se crea el club y su primer usuario, que es Administrador.
- Móvil: no se puede registrar el club; solo iniciar sesión.
- Después, el Administrador crea a los demás usuarios en **Administración > Usuarios** (`/seguridad/usuarios`, solo web) y elige el rol de cada uno.

### 2. Crear el equipo y sus colores
- Web: **Gestión deportiva > Equipos** (`/deportivo/equipos`). Los colores de camiseta se cargan en **Indumentaria** (`/deportivo/equipos/indumentaria`).
- Móvil: **Gestión deportiva** (`/deportivo`), pestaña Equipos (botón «Nuevo equipo»).
- Por qué importa: el sistema separa a los dos equipos por el color de la camiseta. Si los colores están mal cargados, mezcla jugadores de los dos equipos.

### 3. Cargar los jugadores
- Web: **Gestión deportiva > Plantel** (`/deportivo/plantel`). Se cargan uno por uno o todos juntos con un archivo CSV (hay plantilla para descargar).
- Móvil: **Gestión deportiva** (`/deportivo`), pestaña Plantel (botón «Nuevo jugador»). El CSV solo está en la web.
- Por qué importa: sin plantel no se puede armar la alineación ni saber qué jugador es cada uno en el análisis.

### 4. Programar el partido
- Web: **Gestión deportiva > Calendario** (`/deportivo/calendario`), botón para programar (`/deportivo/calendario/programar`). Solo Administrador y Director Técnico.
- Móvil: la **agenda** (`/partidos`) muestra los partidos, pero no se pueden programar desde el celular.
- La alineación se arma en la web en `/deportivo/calendario/alineacion` y en el móvil tocando el partido en la agenda (`/partidos/{id}/alineacion`). Debe haber un solo arquero entre los titulares.

### 5. Montar y calibrar la cámara (solo web)
- Antes de calibrar, revisa **Visión y video > Guía de montaje** (`/vision/guia-montaje`): cámara a unos 7 m de altura (entre 5 y 8 m), en la tribuna principal alineada con el mediocampo, viendo toda la cancha (las cuatro esquinas y las líneas de banda), en 1080p a 30 cuadros por segundo.
- Luego, **Visión y video > Calibración** (`/vision/calibracion`): elige el partido, la fuente (grabación subida o cámara en directo) y las medidas de la cancha (largo y ancho en metros).
  - **Reconocimiento automático**: el sistema reconoce las marcas de la cancha solo. Es la opción recomendada.
  - **Referencia manual de respaldo** (solo con video subido): marcas 8 puntos reales del suelo (esquinas, cruces del círculo central, área chica) en la imagen y en el plano. Con «Validar ahora» ves el error medio; la calibración es válida si el error medio es de 2 m o menos.
- Solo Administrador y Analista pueden calibrar.
- Por qué calibrar: la calibración traduce lo que ve la cámara (píxeles) a metros reales de la cancha. Sin ella no hay posiciones en el plano, ni distancias, ni velocidades.
- Por qué la cámara debe estar fija: la calibración vale para ese encuadre. Si la cámara se mueve o hace zoom, las posiciones dejan de coincidir con la cancha y hay que calibrar de nuevo.

### 6. Iniciar el partido (solo web)
- **Control de partido** (`/partido`): elige el partido, la dirección de ataque y pulsa «Iniciar partido». Solo Administrador y Analista.
- Ahí también se maneja el entretiempo, el tiempo de descuento y el final del partido.
- El partido solo se puede iniciar si está programado y tiene calibración (válida, si es manual).
- Registrar eventos (gol, tarjetas, cambios) lo pueden hacer Administrador, Director Técnico y Asistente, en la web (`/partido`) y en el móvil (**Control de partido**, `/partido`). En el móvil los eventos se guardan aunque no haya conexión y se envían al volver la señal. Un evento se puede deshacer dentro de los 60 segundos.
- Si en vez de transmitir en vivo tienes una grabación: **Visión y video > Videos** (`/vision/videos`) para subirla y procesarla.

### 7. Asignar los jugadores detectados (solo web)
- **Control de partido > Asignación** (`/partido/asignar`): el sistema detecta personas y les da un identificador (track). Aquí eliges qué jugador del plantel es cada identificador. Solo Administrador y Analista.
- Por qué importa: un identificador sin asignar cuenta para las métricas del equipo, pero no genera métricas de ningún jugador.

### 8. Ver métricas y recomendaciones
- Web: **Análisis táctico** (`/analisis`): panel del partido en vivo con el plano 2D y la posesión; además métricas tácticas (`/analisis/metricas`), mapa de calor (`/analisis/mapa-de-calor`) y red de pases (`/analisis/red-de-pases`).
- Móvil: **Análisis táctico** (`/analisis`) y, desde Control de partido, el **resumen** del partido (`/partidos/{id}/resumen`): posesión, distancias, los 3 jugadores que más corrieron y métricas cada 5 minutos.
- Recomendaciones en vivo: web en **Asistencia y reportes** (`/asistencia`); móvil en `/partidos/{id}/recomendaciones`. Se muestran como máximo 3, ordenadas por prioridad. Puedes valorarlas como Útil, No útil o Aplicada. Las ven Administrador, Director Técnico y Analista.
- Las reglas que generan recomendaciones se configuran en la web en **Asistencia y reportes > Reglas** (`/asistencia/reglas`); solo Administrador y Director Técnico las modifican.
- En el móvil, **Asistencia y reportes** (`/asistencia`) y las alertas del partido (`/partidos/{id}/alertas`) también avisan durante el juego.

### 9. Informe del partido
- El informe post-partido todavía no está disponible en Área Técnica. Por ahora, los resultados se consultan en Análisis táctico.

## Qué hay en cada plataforma

- Solo en la web: registro del club, usuarios, programar partidos y competiciones, indumentaria, carga de jugadores por CSV, guía de montaje, calibración, videos, modelos, iniciar y finalizar el partido, asignación de jugadores, mapa de calor, red de pases, métricas tácticas y reglas.
- Solo en el móvil: resumen de métricas a pantalla completa, alertas del partido y registro de eventos sin conexión.
- En las dos: inicio de sesión y perfil, equipos y plantel, agenda y alineación, registro de eventos, análisis en vivo y recomendaciones.

## Buenas prácticas

- Cámara fija, alta y centrada en el mediocampo; que se vea toda la cancha. No muevas la cámara ni el zoom durante el partido.
- Calibra con el mismo encuadre que vas a usar en el partido. Si la cámara se movió, vuelve a calibrar.
- Usa colores de camiseta bien distintos entre los dos equipos y distintos del arquero. Si se parecen, el sistema puede confundir a los jugadores.
- Carga el plantel y la alineación antes del partido.
- Asigna los identificadores a los jugadores apenas aparezcan, para tener métricas por jugador desde el principio.
- Durante el partido, usa el celular en el banco para ver la posesión, el resumen y las recomendaciones.

## Errores comunes y cómo resolverlos

- «No se puede iniciar el partido: no hay calibración para este partido»: falta calibrar. Ve a **Visión y video > Calibración**, elige el partido y guarda la calibración.
- «No se puede iniciar el partido: calibración no válida, error medio X»: los puntos marcados no coinciden bien con la cancha. Vuelve a marcar los puntos con cuidado o usa el reconocimiento automático.
- «No se puede iniciar un partido en estado …»: el partido ya empezó, terminó o fue cancelado. Solo se inician partidos programados.
- «La fecha y hora del partido debe ser futura»: elige una fecha posterior a la actual al programar.
- «El dorsal N ya está en uso por otro jugador activo del equipo»: cambia el número o da de baja al otro jugador.
- «Faltan columnas obligatorias en el CSV»: descarga la plantilla del plantel y respeta sus columnas.
- «Tiene que haber un solo arquero entre los titulares»: revisa la alineación.
- «El plazo de 60 segundos para deshacer el evento ya venció»: después de 60 segundos un evento ya no se puede deshacer.
- «Ese email ya tiene una cuenta»: el correo ya está registrado; usa otro.
- No ves una sección del menú: tu rol no tiene acceso. Pide al Administrador del club que revise tu rol.
- La sesión se cerró sola: la sesión vence por seguridad; vuelve a iniciar sesión.
- «Sin conexión en vivo»: se perdió la conexión; los datos se actualizan solos cuando vuelve.

## Preguntas frecuentes

- **¿Puedo calibrar desde el celular?** No. La calibración, iniciar el partido y la asignación de jugadores se hacen en la web.
- **¿Por qué no veo recomendaciones?** Aparecen solo con un partido en curso y cuando se cumple alguna regla táctica. El rol Asistente no las ve.
- **¿Por qué un jugador no tiene métricas?** Porque su identificador no está asignado. Asígnalo en Control de partido > Asignación.
- **¿Qué pasa si la cámara se mueve?** Las posiciones dejan de ser correctas. Vuelve a dejarla fija y calibra de nuevo.
- **¿Cómo creo usuarios para mi equipo técnico?** El Administrador los crea en Administración > Usuarios (web).
- **¿Qué hago si un evento quedó mal?** Deshazlo dentro de los 60 segundos y vuelve a registrarlo.
