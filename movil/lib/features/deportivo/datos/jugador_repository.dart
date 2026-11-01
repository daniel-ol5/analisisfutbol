/// Capa de datos (Repository) del plantel de jugadores  —  CU-11.
///
/// Encapsula las llamadas HTTP de `api.dart` (que usan el `Cliente` HTTP
/// compartido, con reintento automático de token y caché local) detrás de
/// una interfaz de Repository/Data Source, para que la UI no dependa
/// directamente de las funciones de transporte.
library;

import '../api.dart' as api;
import '../modelos.dart';

class JugadorRepository {
  const JugadorRepository();

  /// Consulta la nómina de un equipo, con caché local para lectura
  /// instantánea y búsqueda sin conexión en la cancha.
  Future<List<Jugador>> listar(
    int equipoId, {
    bool activos = true,
    bool forzarRed = false,
  }) {
    return api.listarJugadores(equipoId, activos: activos, forzarRed: forzarRed);
  }

  Future<Jugador> crear(
    int equipoId, {
    required String nombre,
    required String apellido,
    required int dorsal,
    required String posicion,
    required String pieHabil,
    required int alturaCm,
    double? pesoKg,
  }) {
    return api.crearJugador(
      equipoId,
      nombre: nombre,
      apellido: apellido,
      dorsal: dorsal,
      posicion: posicion,
      pieHabil: pieHabil,
      alturaCm: alturaCm,
      pesoKg: pesoKg,
    );
  }
}
