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

import 'package:flutter/foundation.dart';

enum Entorno { dev, mock, prod }

const String _nombreEntorno =
    String.fromEnvironment('ENTORNO', defaultValue: 'dev');

const Entorno entornoActual = _nombreEntorno == 'prod'
    ? Entorno.prod
    : _nombreEntorno == 'mock'
        ? Entorno.mock
        : Entorno.dev;

const String _urlExplicita = String.fromEnvironment('API_URL');

/// En el emulador de Android, `10.0.2.2` apunta al localhost de la máquina
/// anfitriona. En Web (Chrome/Edge) y escritorio (Windows/macOS/Linux),
/// `10.0.2.2` no existe y se queda colgado esperando timeout TCP, por lo que
/// se usa `127.0.0.1`.
String get _hostLocal =>
    (!kIsWeb && defaultTargetPlatform == TargetPlatform.android)
        ? '10.0.2.2'
        : '127.0.0.1';

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
