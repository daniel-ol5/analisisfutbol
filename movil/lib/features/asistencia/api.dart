/// Llamadas al backend de Asistencia y Reportes  —  P6.
///
/// Endpoints bajo /asistencia. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/cliente.dart';

Future<dynamic> ping() => cliente.get('/asistencia/ping');
