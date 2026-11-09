/// Llamadas al backend de Operación del Partido — P4.
library;

import '../../shared/api/cliente.dart';
import '../../shared/api/almacenamiento.dart';
import 'cola_eventos.dart';
import 'modelos.dart';

Future<dynamic> ping() => cliente.get('/partido/ping');

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
