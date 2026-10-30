/// Llamadas al backend de la alineación  —  CU-17 (T-053).
library;

import '../../../shared/api/almacenamiento.dart';
import '../../../shared/api/cliente.dart';
import 'modelos.dart';

String _claveCache(int partidoId) => 'alineacion.$partidoId';

/// Alineación del partido. La deja en el dispositivo para verla sin conexión.
/// ErrorApi 404 si el partido todavía no tiene alineación.
Future<Alineacion> obtenerAlineacion(int partidoId) async {
  final json = await cliente.get('/deportivo/partidos/$partidoId/alineacion')
      as Map<String, dynamic>;
  await Almacenamiento.guardarCache(_claveCache(partidoId), json);
  return Alineacion.fromJson(json);
}

/// Última alineación descargada de ese partido, o null si nunca se descargó.
Future<Alineacion?> alineacionEnCache(int partidoId) async {
  final json = await Almacenamiento.leerCache(_claveCache(partidoId));
  if (json == null) return null;
  try {
    return Alineacion.fromJson(json);
  } catch (_) {
    return null; // caché de otra versión de la app
  }
}
