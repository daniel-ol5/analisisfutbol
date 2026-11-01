/// Entorno de ejecución de la app: dev (backend local), mock (Prism sobre el
/// contrato OpenAPI, ver docker-compose.yml) o prod (backend desplegado).
///
/// Se elige con --dart-define=ENTORNO=dev|mock|prod (default: dev). Un
/// --dart-define=API_URL=... explícito tiene prioridad sobre el valor del
/// entorno; es la forma de apuntar a una IP de red local, como la de la
/// laptop cuando se prueba desde un dispositivo físico:
///
///   flutter run --dart-define=API_URL=http://192.168.0.27:8000/api
library;

enum Entorno { dev, mock, prod }

const String _nombreEntorno = String.fromEnvironment('ENTORNO', defaultValue: 'dev');

const Entorno entornoActual = _nombreEntorno == 'prod'
    ? Entorno.prod
    : _nombreEntorno == 'mock'
        ? Entorno.mock
        : Entorno.dev;

/// 10.0.2.2 es el alias del emulador de Android hacia el localhost de la
/// máquina anfitriona; no resuelve nada en un dispositivo físico (de ahí la
/// prioridad de API_URL arriba).
const Map<Entorno, String> _urlPorDefecto = {
  Entorno.dev: 'http://10.0.2.2:8000/api',
  Entorno.mock: 'http://10.0.2.2:4010/api',
  Entorno.prod: '',
};

const String _urlExplicita = String.fromEnvironment('API_URL');

/// URL base de la API para el entorno actual.
///
/// No hay una URL de prod embebida a propósito: hace falta pasar siempre
/// --dart-define=API_URL=https://tu-backend.com/api en builds de Entorno.prod
/// para no arriesgarse a publicar apuntando por error a un backend de
/// desarrollo.
String get urlApi {
  if (_urlExplicita.isNotEmpty) return _urlExplicita;

  final porDefecto = _urlPorDefecto[entornoActual]!;
  if (porDefecto.isEmpty) {
    throw StateError(
      'Entorno.prod requiere --dart-define=API_URL=https://tu-backend.com/api',
    );
  }
  return porDefecto;
}
