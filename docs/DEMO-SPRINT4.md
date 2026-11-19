# Demostración reproducible — Sprint 4

Esta guía prepara un recorrido local de las funciones que están implementadas. No usa datos de
producción, credenciales de Firebase, una cámara física ni el worker GPU.

## 1. Levantar los servicios

Desde la raíz del repositorio, copia `.env.example` a `.env` y completa sus cuatro claves. Luego:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/api/salud
```

La API aplica las migraciones y ejecuta un seed idempotente. El escenario resultante contiene:

- administrador del club demo;
- competición `Torneo Demostracion`;
- equipo `Primera Demo` y 18 jugadores;
- tres partidos: programado con alineación, programado sin alineación y finalizado;
- alineación 4-3-3 con once titulares y capitán;
- catálogo global de doce reglas tácticas.

La cuenta es `admin@club-demo.example.com`. La contraseña es el valor local de
`DEMO_ADMIN_PASSWORD`; no se escribe en esta guía ni en el repositorio.

## 2. Comprobar el escenario sin modificarlo

En una terminal nueva, asigna la misma contraseña del `.env` a la sesión y ejecuta:

```powershell
$env:DEMO_ADMIN_PASSWORD = "TU_CLAVE_DEMO"
cd backend
python -m scripts.demo_sprint4 verificar
```

El comando comprueba salud, login, equipo, competición, agenda, alineación, estado del partido,
calibración, reglas, métricas y recomendaciones. Antes de preparar el partido puede mostrar avisos
por calibración y recomendaciones ausentes; esos avisos son esperados.

## 3. Preparar el partido automáticamente

```powershell
python -m scripts.demo_sprint4 preparar --duracion 12
```

El preparador:

1. rechaza por defecto cualquier API que no sea localhost;
2. selecciona el partido demo que tenga alineación;
3. crea una calibración sintética exacta para el emisor simulado;
4. inicia el partido si todavía está programado;
5. registra una tarjeta roja ficticia con UUID estable;
6. envía 60 muestras a 5 Hz desde el minuto 5;
7. verifica métricas, reglas y una recomendación crítica.

La tarjeta ficticia garantiza que el motor genere una recomendación crítica real. Al repetir el
comando se reutiliza el mismo evento y el cooldown impide duplicar la recomendación.

La calibración creada por este script sirve exclusivamente para probar el flujo de software: mapea
1050 x 680 píxeles a 105 x 68 metros. No acredita precisión de una cámara real.

Opciones útiles:

```powershell
python -m scripts.demo_sprint4 preparar --partido 1 --duracion 20
python -m scripts.demo_sprint4 preparar --sin-evento-critico
python -m scripts.demo_sprint4 verificar --url http://127.0.0.1:8000/api
```

No uses `--permitir-host-remoto` sin confirmar expresamente que el destino es un entorno de
desarrollo desechable.

## 4. Levantar la web

En otra terminal:

```powershell
cd web
npm ci
npm run dev
```

Abre `http://127.0.0.1:5173` e inicia sesión. Si Vite usa otra dirección, utiliza la URL que muestre
la terminal.

## 5. Recorrido sugerido

1. **Inicio de sesión:** entrar con el administrador demo.
2. **Gestión Deportiva:** mostrar equipo, plantel y competición.
3. **Agenda:** localizar `Club Rival Uno` y abrir su alineación 4-3-3.
4. **Operación del Partido:** seleccionar el mismo partido. Debe estar `EN_CURSO`, con calibración
   válida, evento manual y telemetría ya recibida.
5. **Análisis Táctico:** mostrar posesión, métricas disponibles, cronología, mapa y panel táctico.
6. **Priorización/cooldown:** volver a ejecutar `preparar --duracion 2`; debe conservar una sola
   recomendación crítica.
7. **Asistencia:** consultar la recomendación con Swagger en
   `http://127.0.0.1:8000/api/docs`, ruta
   `GET /api/asistencia/partidos/{partido_id}/recomendaciones`.
8. **Cierre:** finalizar el partido desde Operación del Partido únicamente al terminar el ensayo.

## 6. Limitaciones que deben decirse durante la demostración

- Las pantallas web y Flutter de Asistencia siguen pendientes; la recomendación se muestra por API.
- Crear/editar/probar reglas, alertas, valoración, informes, exportación y comparativa todavía
  responden 501. Están detallados en `docs/validacion/REVISION-CRUZADA-SPRINT4.md`.
- Firebase permanece deshabilitado sin credenciales reales; las pruebas automatizadas usan un
  proveedor simulado.
- La telemetría de esta demo procede del emisor simulado, no de YOLO/ByteTrack ni de una cámara.
- La prueba física de cancha pertenece a T-106 y no queda acreditada con este recorrido.

## 7. Detener el entorno

```powershell
docker compose down
```

No agregues `-v`: el comando anterior conserva el volumen de desarrollo. El preparador nunca borra
registros ni reinicia una base.

