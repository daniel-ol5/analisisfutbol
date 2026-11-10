/// Llamadas al backend de Operación del Partido — P4 (T-069, T-070, T-071).
library;

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'cola_eventos.dart';
import 'modelos.dart';

String _claveCacheEstado(int partidoId) => 'partido.estado.$partidoId';
const _claveCachePartidos = 'partido.agenda';
const _claveCacheAgendaCompartida = 'agenda.partidos';

Future<dynamic> ping() => cliente.get('/partido/ping');

// ---------------------------------------------------------------------------
// Estado en vivo y cronómetro sincronizado (CU-30 · T-071)
// ---------------------------------------------------------------------------

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
  try {
    final json = await Almacenamiento.leerCache(_claveCacheEstado(partidoId));
    if (json == null) return null;
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
  try {
    final json = await Almacenamiento.leerCache(_claveCachePartidos) ??
        await Almacenamiento.leerCache(_claveCacheAgendaCompartida);
    if (json == null) return null;
    return _parsearPartidos(json['partidos'] as List);
  } catch (_) {
    return null;
  }
}

List<ResumenPartidoVivo> _parsearPartidos(List lista) => [
      for (final p in lista)
        ResumenPartidoVivo.fromJson(p as Map<String, dynamic>),
    ];

// ---------------------------------------------------------------------------
// Eventos manuales y cola offline (CU-36, CU-37 y CU-38 · T-069 / T-070)
// ---------------------------------------------------------------------------

final ColaEventos _cola = ColaEventos();
final GestorEventosOffline _gestor = GestorEventosOffline(
  cola: _cola,
  registrarRemoto: _registrarRemoto,
  sincronizarRemoto: _sincronizarRemoto,
);

Future<int> _clubActual() async {
  final usuario = await Almacenamiento.leerUsuario();
  final clubId = usuario?['club_id'];
  if (clubId is int) return clubId;
  throw ErrorApi(
    401,
    'No se encontró el perfil local para proteger la cola del club.',
  );
}

Future<EventoManual> _registrarRemoto(int partidoId, EventoCrear evento) async {
  final json =
      await cliente.post('/partido/$partidoId/eventos', cuerpo: evento.toJson())
          as Map<String, dynamic>;
  return EventoManual.fromJson(json);
}

Future<List<EventoManual>> _sincronizarRemoto(
  int partidoId,
  List<EventoCrear> eventos,
) async {
  final json =
      await cliente.post(
            '/partido/$partidoId/eventos/sincronizar',
            cuerpo: eventos.map((evento) => evento.toJson()).toList(),
          )
          as List<dynamic>;
  return json
      .map((evento) => EventoManual.fromJson(evento as Map<String, dynamic>))
      .toList();
}

Future<EventoManual> registrarEvento(int partidoId, EventoCrear evento) async {
  return _gestor.registrar(
    clubId: await _clubActual(),
    partidoId: partidoId,
    evento: evento,
  );
}

Future<ResultadoSincronizacion> sincronizarPendientes(int partidoId) async {
  return _gestor.sincronizar(clubId: await _clubActual(), partidoId: partidoId);
}

Future<int> contarPendientes(int partidoId) async =>
    _cola.contar(clubId: await _clubActual(), partidoId: partidoId);

Future<void> descartarPendiente(String uuid) async {
  await _gestor.descartar(clubId: await _clubActual(), uuid: uuid);
}

Future<void> deshacerEvento(int eventoId) async {
  await cliente.delete('/partido/eventos/$eventoId');
}
