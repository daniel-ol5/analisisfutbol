/// Llamadas al backend de Seguridad y Administración  —  P1.
///
/// Endpoints bajo /seguridad. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/cliente.dart';

Future<dynamic> ping() => cliente.get('/seguridad/ping');
