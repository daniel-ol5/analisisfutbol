/// Llamadas de recomendaciones  —  CU-50 (T-094).
///
/// Pasan por el cliente único (token y renovación). Es una clase para que las
/// pruebas la reemplacen sin red.
library;

import '../../shared/api/cliente.dart';
import 'recomendaciones_modelos.dart';

class RecomendacionesApi {
  const RecomendacionesApi();

  /// Como máximo 3 activas, priorizadas.
  Future<List<Recomendacion>> listar(int partidoId) async {
    final respuesta = await cliente.get(
      '/asistencia/partidos/$partidoId/recomendaciones',
      params: {'solo_activas': 'true'},
    );
    return respuesta is List
        ? respuesta
            .where(Recomendacion.valida)
            .cast<Map<String, dynamic>>()
            .map(Recomendacion.fromJson)
            .toList()
        : const [];
  }

  /// T-090/T-094: se mostró por primera vez. Idempotente en el servidor.
  Future<void> marcarVista(int recomendacionId) =>
      cliente.post('/asistencia/recomendaciones/$recomendacionId/vista');
}
