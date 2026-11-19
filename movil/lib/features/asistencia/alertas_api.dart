/// Llamada de las alertas del partido  —  CU-52 (T-095).
library;

import '../../shared/api/cliente.dart';
import 'alertas_modelos.dart';

/// Inyectable: las pruebas pasan una función que no usa la red.
typedef ObtenerAlertas = Future<List<Alerta>> Function(int partidoId);

Future<List<Alerta>> obtenerAlertas(int partidoId) async =>
    Alerta.lista(await cliente.get('/asistencia/partidos/$partidoId/alertas'));
