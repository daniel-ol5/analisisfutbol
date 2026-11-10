/// Llamadas al backend de Análisis Táctico  —  P5 · CU-40 (T-080).
library;

import '../../shared/api/cliente.dart';
import 'modelos.dart';

Future<dynamic> ping() => cliente.get('/analisis/ping');

/// Carga la lista de partidos del club para el selector de análisis.
Future<List<PartidoInfo>> listarPartidosClub() async {
  final respuesta = await cliente.get('/deportivo/partidos');
  if (respuesta is List) {
    return respuesta
        .whereType<Map<String, dynamic>>()
        .map(PartidoInfo.fromJson)
        .toList();
  }
  return [];
}
