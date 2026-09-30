/// Llamadas al backend de Gestión Deportiva  —  P2.
///
/// Endpoints bajo /deportivo. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/cliente.dart';

Future<dynamic> ping() => cliente.get('/deportivo/ping');
