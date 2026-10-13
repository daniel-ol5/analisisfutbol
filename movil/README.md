# App móvil

Cliente Flutter para el DT y el asistente de campo.

## Puesta en marcha

```bash
cd movil
flutter pub get
flutter run --dart-define=API_URL=http://10.0.2.2:8000/api
```

`API_URL` por defecto apunta al emulador de Android hacia el backend local
(`10.0.2.2` es el alias del emulador hacia el localhost de la máquina
anfitriona). Para un dispositivo físico, usar la IP de la red local. Mientras
un caso de uso siga devolviendo 501, se puede apuntar al mock en el puerto
4010 en su lugar.

## Estructura

```
lib/
  app/            Entrada de la app: router (GoRouter), tema, pantalla de inicio
  features/
    <paquete>/     api.dart (llamadas HTTP) + pagina.dart (UI), uno por paquete
                    de casos de uso: seguridad, deportivo, vision, partido,
                    analisis, asistencia. Las features no se importan entre sí.
  shared/
    api/           cliente.dart (cliente HTTP único, adjunta el token) y
                    almacenamiento.dart (sesión en flutter_secure_storage:
                    Keystore en Android, Keychain en iOS)
    ui/            Pendiente: placeholder para features aún no implementadas
```

Cada feature no implementada muestra `Pendiente` con sus casos de uso. El
paquete de seguridad (P1) ya tiene CU-02 (iniciar sesión) y CU-03 (cerrar
sesión) funcionando contra `/api/seguridad/login` y `/api/seguridad/logout`.

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
