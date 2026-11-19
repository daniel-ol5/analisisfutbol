# Plan de pruebas en dispositivos reales — T-097

**Tarea:** T-097 (Sprint 4) · Responsable: Araceli
**Criterio de aceptación:** la app funciona en al menos **tres dispositivos Android**, en **exterior** y con **red inestable**, **sin cierres inesperados**.

Este plan se ejecuta con la app instalada desde el APK y el backend real. Para cada
dispositivo se recorren todos los casos y se anota el resultado en la planilla del final.

---

## 1. Preparación

### Dispositivos

Tres Android distintos. Que haya variedad de tamaño de pantalla y de potencia.

| # | Marca y modelo | Versión de Android | Pantalla (pulgadas) | Gama |
|---|---|---|---|---|
| D1 | | | | Baja |
| D2 | | | | Media |
| D3 | | | | Media o alta |

Si es posible, al menos uno con Android 10 o anterior y otro con Android 14 o posterior.

### Backend

- **Pruebas en interiores (Wi-Fi):** el APK de prueba apunta a la computadora de desarrollo
  (`http://<IP de la PC>:8001/api`). El celular tiene que estar en la **misma red Wi-Fi** que la PC.
- **Pruebas en exterior (datos móviles):** hace falta el backend desplegado (T-084) y un APK
  compilado con su URL:
  `flutter build apk --release --dart-define=API_URL=https://<servidor>/api`

### Datos para la prueba

Antes de salir a la cancha, con un usuario **DT** del club:

1. Un partido **en curso**, con alineación cargada y la cámara calibrada.
2. Al menos una **recomendación activa**. Se genera con el emisor simulado:
   `python scripts/emisor_simulado.py --partido <id> --email <dt> --password <clave> --duracion 120`
3. Un jugador **amonestado** y otra tarjeta en los últimos 10 minutos, para que aparezca la
   alerta de riesgo de expulsión.

### Instalación del APK

1. Copiar `app-release.apk` al celular (por cable, Drive o WhatsApp).
2. Abrirlo y permitir **"Instalar apps de fuentes desconocidas"** cuando lo pida.
3. Abrir **Área Técnica** e iniciar sesión.

---

## 2. Casos de prueba

Cada caso se marca **OK**, **Falla** (anotar qué pasó) o **N/A**. Un **cierre inesperado**
(la app se cierra sola o muestra "La app se detuvo") es siempre **Falla**.

### A. Sesión

| ID | Caso | Resultado esperado |
|---|---|---|
| A1 | Iniciar sesión con usuario y clave correctos | Entra al inicio |
| A2 | Clave incorrecta | Mensaje de error, la app no se cierra |
| A3 | Cerrar la app (sacarla de recientes) y volver a abrirla | Sigue con la sesión iniciada |
| A4 | Activar el **modo Sol** desde el perfil | Alto contraste; queda guardado al reabrir |

### B. Agenda y alineación

| ID | Caso | Resultado esperado |
|---|---|---|
| B1 | Abrir la agenda de partidos | Lista de partidos con fecha y rival |
| B2 | Filtrar por momento y por equipo | La lista se filtra |
| B3 | Abrir la alineación de un partido | Se ve la cancha con los titulares |
| B4 | Modo avión, volver a abrir la agenda | Muestra lo guardado y avisa que no hay conexión |

### C. Partido en vivo

| ID | Caso | Resultado esperado |
|---|---|---|
| C1 | Abrir el partido en curso | Cronómetro corriendo y marcador |
| C2 | Registrar un **gol** | Se suma al marcador; se puede deshacer |
| C3 | Registrar una **amarilla** con jugador | Confirmación en pantalla |
| C4 | Registrar un **cambio** (sale y entra) | Confirmación; el suplente queda en cancha |
| C5 | Tocar rápido varias veces el mismo botón | Registra un solo evento |
| C6 | **Modo avión**, registrar 2 eventos y volver a conectar | Quedan en cola y se sincronizan solos al volver la red |
| C7 | Bloquear la pantalla 1 minuto y desbloquear | El cronómetro sigue en el minuto correcto |

### D. Alertas (T-095)

| ID | Caso | Resultado esperado |
|---|---|---|
| D1 | Con un amonestado y fricción, abrir el partido en curso | **Barra roja arriba del cronómetro** con la alerta de riesgo de expulsión |
| D2 | Tocar la barra | Se abre "Alertas del partido" con la justificación |
| D3 | Tocar **Entendido** | La alerta desaparece |
| D4 | Leer la barra **al sol** | Se lee sin esfuerzo |

### E. Recomendaciones y valoración (T-094, T-095)

| ID | Caso | Resultado esperado |
|---|---|---|
| E1 | Abrir Resumen y luego Recomendaciones del partido | Como máximo 3 tarjetas, ordenadas por prioridad |
| E2 | Tocar **Útil** en una tarjeta | "Marcada como Útil"; los botones desaparecen |
| E3 | Tocar **Aplicada** o **No útil** en otra | Se marca; desaparece en la próxima actualización |
| E4 | **Modo avión** y tocar **Útil** | Aviso "Sin conexión: no se guardó"; al volver la red, reintentar funciona |
| E5 | Generar una recomendación nueva con la pantalla abierta | Aparece sola, sin recargar |

### F. Notificaciones push (T-096)

Se completa cuando T-096 esté integrada.

| ID | Caso | Resultado esperado |
|---|---|---|
| F1 | Primer inicio de sesión | La app pide permiso de notificaciones |
| F2 | Recomendación **CRÍTICA** con la app **abierta** | Llega el aviso |
| F3 | Recomendación CRÍTICA con la app **en segundo plano** | Notificación en la barra del sistema; al tocarla se abre la recomendación correcta |
| F4 | Recomendación CRÍTICA con la app **cerrada** | Igual que F3 (**criterio de T-096**) |
| F5 | Recomendación de prioridad **no crítica** | **No** llega notificación |

### G. Condiciones de campo

| ID | Condición | Qué se hace | Resultado esperado |
|---|---|---|---|
| G1 | **Exterior, a pleno sol** | Recorrer C1, D1 y E1 con el brillo al máximo, en modo Sol | Todo se lee; ningún texto queda lavado por el sol |
| G2 | **Red inestable** | Durante C y E, alternar modo avión cada 30 s tres veces | La app avisa "sin conexión", **no se cierra**, y al volver la red se pone al día sola |
| G3 | **Datos móviles débiles** | Recorrer C, D y E con 3G o poca señal | Tarda más pero responde; sin cierres |
| G4 | **Rotar la pantalla** en cada pantalla principal | La app se adapta | Sin desbordes ni cierres |
| G5 | **Uso continuo** | 15 minutos con el partido abierto | Sin cierres; el celular no se recalienta en exceso |

---

## 3. Planilla de resultados

Copiar una tabla por dispositivo.

**Dispositivo:** D__ · **Fecha:** ____ · **Lugar** (interior o exterior): ____ · **Red** (Wi-Fi, 4G, 3G): ____

| ID | Resultado (OK, Falla, N/A) | Observaciones |
|---|---|---|
| A1 | | |
| A2 | | |
| A3 | | |
| A4 | | |
| B1 | | |
| B2 | | |
| B3 | | |
| B4 | | |
| C1 | | |
| C2 | | |
| C3 | | |
| C4 | | |
| C5 | | |
| C6 | | |
| C7 | | |
| D1 | | |
| D2 | | |
| D3 | | |
| D4 | | |
| E1 | | |
| E2 | | |
| E3 | | |
| E4 | | |
| E5 | | |
| F1 | | |
| F2 | | |
| F3 | | |
| F4 | | |
| F5 | | |
| G1 | | |
| G2 | | |
| G3 | | |
| G4 | | |
| G5 | | |

**Cierres inesperados en este dispositivo:** ____ (el criterio pide **0**)

---

## 4. Resumen para cerrar T-097

| Dispositivo | Casos OK | Fallas | Cierres inesperados | ¿Cumple? |
|---|---|---|---|---|
| D1 | | | | |
| D2 | | | | |
| D3 | | | | |

T-097 se cumple cuando los tres dispositivos tienen **0 cierres inesperados**. Las fallas que
no sean cierres se anotan en Jira como defectos, con el ID del caso y una captura.
