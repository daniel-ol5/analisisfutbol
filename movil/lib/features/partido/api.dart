/// Llamadas al backend de Operación del Partido  —  P4 (CU-30 · T-071).
library;

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'modelos.dart';

String _claveCacheEstado(int partidoId) => 'partido.estado.$partidoId';
const _claveCachePartidos = 'partido.agenda';
const _claveCacheAgendaCompartida = 'agenda.partidos';

Future<dynamic> ping() => cliente.get('/partido/ping');

/// Obtiene el estado en vivo del partido (`GET /partido/{id}/estado`) y guarda
/// la última respuesta en el dispositivo para consultarla si se cae la red.
Future<EstadoEnVivo> obtenerEstadoPartido(int partidoId) async {
  final json =
      await cliente.get('/partido/$partidoId/estado') as Map<String, dynamic>;
  await Almacenamiento.guardarCache(_claveCacheEstado(partidoId), {
    'guardado': DateTime.now().toUtc().toIso8601String(),
    'estado': json,
  });
  return EstadoEnVivo.fromJson(json);
}

/// Último estado descargado de ese partido, o `null` si nunca se descargó.
Future<EstadoGuardado?> estadoPartidoEnCache(int partidoId) async {
  final json = await Almacenamiento.leerCache(_claveCacheEstado(partidoId));
  if (json == null) return null;
  try {
    return EstadoGuardado(
      estado: EstadoEnVivo.fromJson(json['estado'] as Map<String, dynamic>),
      guardado: DateTime.parse(json['guardado'] as String).toLocal(),
    );
  } catch (_) {
    return null;
  }
}

/// Lista los partidos del club (`GET /deportivo/partidos`) para el selector de
/// `/partido`, sin importar tipos desde `features/deportivo`.
Future<List<ResumenPartidoVivo>> listarPartidosVivo() async {
  final respuesta = await cliente.get('/deportivo/partidos') as List;
  await Almacenamiento.guardarCache(_claveCachePartidos, {
    'guardado': DateTime.now().toUtc().toIso8601String(),
    'partidos': respuesta,
  });
  return _parsearPartidos(respuesta);
}

/// Lista de partidos guardada en caché (lee la caché propia o la de la agenda).
Future<List<ResumenPartidoVivo>?> partidosVivoEnCache() async {
  final json = await Almacenamiento.leerCache(_claveCachePartidos) ??
      await Almacenamiento.leerCache(_claveCacheAgendaCompartida);
  if (json == null) return null;
  try {
    return _parsearPartidos(json['partidos'] as List);
  } catch (_) {
    return null;
  }
}

List<ResumenPartidoVivo> _parsearPartidos(List lista) => [
      for (final p in lista)
        ResumenPartidoVivo.fromJson(p as Map<String, dynamic>),
    ];
