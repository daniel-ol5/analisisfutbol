/// Llamadas al backend de Operación del Partido — P4.
library;

import '../../shared/api/cliente.dart';
import 'modelos.dart';

Future<dynamic> ping() => cliente.get('/partido/ping');

Future<EventoManual> registrarEvento(int partidoId, EventoCrear evento) async {
  final json =
      await cliente.post('/partido/$partidoId/eventos', cuerpo: evento.toJson())
          as Map<String, dynamic>;
  return EventoManual.fromJson(json);
}

Future<void> deshacerEvento(int eventoId) async {
  await cliente.delete('/partido/eventos/$eventoId');
}
