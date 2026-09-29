# App móvil

Cliente Flutter para el DT y el asistente de campo.

Flutter no está instalado en esta máquina, así que el proyecto todavía no está
generado. Quien tome la app móvil en el Sprint 4 hace:

```bash
# 1. Instalar Flutter: https://docs.flutter.dev/get-started/install/windows
flutter doctor

# 2. Generar el proyecto DENTRO de esta carpeta
cd movil
flutter create --project-name areatecnica --org com.areatecnica .
```

## Alcance

| Pantalla | Actor | Casos de uso |
|---|---|---|
| Partido en vivo | Director Técnico | CU-40, CU-50, CU-51 |
| Registro de eventos | Asistente de campo | CU-36, CU-37, CU-38 |
| Informe post-partido | Director Técnico | CU-55 |

## Condiciones reales de uso

El DT usa esto **de pie, al sol, con una mano y diez segundos de atención**. Eso
condiciona el diseño más que cualquier otra cosa:

- Textos no menores a 16 puntos
- Cada evento se registra en 2 toques como máximo
- Sin conexión, los eventos quedan en cola local y se envían al recuperarla
- Reconexión automática del WebSocket, con el estado siempre visible

## Nota de alcance

`Pb-46` (app del DT) es el primer candidato a bajar de prioridad si el equipo va
ajustado: la web funciona en el navegador del celular y cubre lo esencial. Son
8 puntos que se liberan sin romper el producto.
