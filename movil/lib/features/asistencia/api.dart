/// Llamadas al backend de Asistencia y Reportes  —  P6.
///
/// Endpoints bajo /asistencia. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/cliente.dart';

typedef Recomendacion = ({
  String mensaje,
  String justificacion,
  String prioridad,
  int minuto,
});
typedef Regla = ({String nombre, bool activa});

Future<List<Recomendacion>> listarRecomendaciones(int partidoId) async {
  final respuesta =
      await cliente.get('/asistencia/partidos/$partidoId/recomendaciones')
          as List;
  return [
    for (final registro in respuesta.cast<Map<String, dynamic>>())
      (
        mensaje: registro['mensaje'] as String,
        justificacion: registro['justificacion'] as String,
        prioridad: registro['prioridad'] as String,
        minuto: registro['minuto'] as int,
      ),
  ];
}

Future<List<Regla>> listarReglas() async {
  final respuesta = await cliente.get('/asistencia/reglas') as List;
  return [
    for (final registro in respuesta.cast<Map<String, dynamic>>())
      (
        nombre: registro['nombre'] as String,
        activa: registro['activa'] as bool,
      ),
  ];
}
