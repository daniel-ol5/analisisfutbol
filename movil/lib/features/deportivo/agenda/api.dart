/// Llamadas al backend de la agenda de partidos  —  CU-15 (T-052).
library;

import '../../../shared/api/almacenamiento.dart';
import '../../../shared/api/cliente.dart';
import 'modelos.dart';

const _claveCache = 'agenda.partidos';

/// Agenda del club recién descargada. La deja en el dispositivo para
/// consultarla en la cancha sin cobertura.
Future<List<Partido>> listarPartidos() async {
  final respuesta = await cliente.get('/deportivo/partidos') as List;
  await Almacenamiento.guardarCache(_claveCache, {
    'guardado': DateTime.now().toUtc().toIso8601String(),
    'partidos': respuesta,
  });
  return _partidos(respuesta);
}

/// Última agenda descargada, con la hora en que se guardó; null si nunca se
/// descargó o si la guardó otra versión de la app.
Future<AgendaGuardada?> agendaEnCache() async {
  final json = await Almacenamiento.leerCache(_claveCache);
  if (json == null) return null;
  try {
    return AgendaGuardada(
      partidos: _partidos(json['partidos'] as List),
      guardado: DateTime.parse(json['guardado'] as String).toLocal(),
    );
  } catch (_) {
    return null;
  }
}

class AgendaGuardada {
  const AgendaGuardada({required this.partidos, required this.guardado});
  final List<Partido> partidos;
  final DateTime guardado;
}

List<Partido> _partidos(List lista) =>
    [for (final p in lista) Partido.fromJson(p as Map<String, dynamic>)];
