/// Llamadas del resumen de métricas  —  CU-43 (T-081).
///
/// Todo pasa por el cliente único (token, renovación y errores en `ErrorApi`).
/// Es una clase para que las pruebas la reemplacen sin red.
library;

import '../../shared/api/cliente.dart';
import 'modelos.dart';
import 'resumen_modelos.dart';

class ResumenApi {
  const ResumenApi();

  Future<PartidoInfo> partido(int partidoId) async => PartidoInfo.fromJson(
      await cliente.get('/deportivo/partidos/$partidoId') as Map<String, dynamic>);

  Future<MetricasPartido> metricas(int partidoId) async =>
      MetricasPartido.fromJson(
          await cliente.get('/analisis/partidos/$partidoId/metricas')
              as Map<String, dynamic>);

  /// Ordenada por distancia (así la devuelve el backend). `equipo`: LOCAL o VISITANTE.
  Future<List<MetricaJugador>> jugadores(int partidoId, String equipo) async =>
      MetricaJugador.lista(await cliente.get(
          '/analisis/partidos/$partidoId/metricas/jugadores',
          params: {'equipo': equipo}));

  Future<List<IntervaloMetricas>> intervalos(int partidoId) async {
    final respuesta =
        await cliente.get('/analisis/partidos/$partidoId/metricas/intervalos');
    return respuesta is List
        ? respuesta
            .whereType<Map<String, dynamic>>()
            .map(IntervaloMetricas.fromJson)
            .toList()
        : const [];
  }
}
