/// Entorno de ejecución de la app: dev (backend local), mock (Prism sobre el
/// contrato OpenAPI, ver docker-compose.yml) o prod (backend desplegado).
///
/// Se elige con --dart-define=ENTORNO=dev|mock|prod (default: dev). Un
/// --dart-define=API_URL=... explícito tiene prioridad sobre el valor del
/// entorno; por ejemplo, para probar por WiFi con la IP de la laptop:
///
///   flutter run --dart-define=API_URL=http://192.168.0.27:8000/api
///
/// En Android (celular por USB o emulador) se usa 127.0.0.1 y el puerto se
/// conecta con adb reverse antes de ejecutar la app:
///
///   adb reverse tcp:8000 tcp:8000   (dev)
///   adb reverse tcp:4010 tcp:4010   (mock)
library;

enum Entorno { dev, mock, prod }

const String _nombreEntorno =
    String.fromEnvironment('ENTORNO', defaultValue: 'dev');

const Entorno entornoActual = _nombreEntorno == 'prod'
    ? Entorno.prod
    : _nombreEntorno == 'mock'
        ? Entorno.mock
        : Entorno.dev;

const String _urlExplicita = String.fromEnvironment('API_URL');

/// Host del backend local.
///
/// 127.0.0.1 sirve en todas las plataformas:
///  - Web y escritorio: es directamente la máquina local.
///  - Android (celular real o emulador): adb reverse redirige el puerto del
///    dispositivo al de la laptop por el cable/ADB.
///
/// Si se usa el emulador SIN adb reverse, se puede volver a la dirección
/// especial del emulador con: --dart-define=HOST_LOCAL=10.0.2.2
const String _hostLocal =
    String.fromEnvironment('HOST_LOCAL', defaultValue: '127.0.0.1');

/// URL base de la API para el entorno actual.
///
/// No hay una URL de prod embebida a propósito: hace falta pasar siempre
/// --dart-define=API_URL=https://tu-backend.com/api en builds de Entorno.prod
/// para no arriesgarse a publicar apuntando por error a un backend de
/// desarrollo.
String get urlApi {
  if (_urlExplicita.isNotEmpty) return _urlExplicita;

  return switch (entornoActual) {
    Entorno.dev => 'http://$_hostLocal:8000/api',
    Entorno.mock => 'http://$_hostLocal:4010/api',
    Entorno.prod => throw StateError(
        'Entorno.prod requiere --dart-define=API_URL=https://tu-backend.com/api',
      ),
  };
}