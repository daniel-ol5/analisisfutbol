/// Modelos de la alineación  —  CU-17 / HU-14.
library;

/// Un jugador de la alineación, con sus datos (respuesta de GET .../alineacion).
///
/// Coordenadas relativas, mismos ejes que el tracking:
///  - posX: porcentaje del largo, 0 = arco propio, 100 = arco rival.
///  - posY: porcentaje del ancho, 0 = banda izquierda, 100 = banda derecha
///    (mirando hacia el arco rival).
class JugadorAlineado {
  const JugadorAlineado({
    required this.jugadorId,
    required this.esTitular,
    required this.esCapitan,
    required this.posX,
    required this.posY,
    required this.nombre,
    required this.apellido,
    required this.dorsal,
    required this.posicion,
  });

  final int jugadorId;
  final bool esTitular;
  final bool esCapitan;
  final double posX;
  final double posY;
  final String nombre;
  final String apellido;
  final int dorsal;
  final String posicion;

  bool get esArquero => posicion == 'ARQ';

  factory JugadorAlineado.fromJson(Map<String, dynamic> json) => JugadorAlineado(
        jugadorId: json['jugador_id'] as int,
        esTitular: json['es_titular'] as bool? ?? false,
        esCapitan: json['es_capitan'] as bool? ?? false,
        posX: (json['pos_x'] as num).toDouble(),
        posY: (json['pos_y'] as num).toDouble(),
        nombre: json['nombre'] as String? ?? '',
        apellido: json['apellido'] as String? ?? '',
        dorsal: json['dorsal'] as int,
        posicion: json['posicion'] as String? ?? '',
      );

  String get posicionLegible => switch (posicion) {
        'ARQ' => 'Arquero',
        'DEF' => 'Defensor',
        'MED' => 'Mediocampista',
        'DEL' => 'Delantero',
        _ => posicion,
      };
}

class Alineacion {
  const Alineacion({
    required this.partidoId,
    required this.formacion,
    required this.jugadores,
  });

  final int partidoId;
  final String formacion;
  final List<JugadorAlineado> jugadores;

  List<JugadorAlineado> get titulares =>
      jugadores.where((j) => j.esTitular).toList();

  List<JugadorAlineado> get suplentes =>
      jugadores.where((j) => !j.esTitular).toList()
        ..sort((a, b) => a.dorsal.compareTo(b.dorsal));

  JugadorAlineado? get capitan =>
      jugadores.where((j) => j.esCapitan).firstOrNull;

  factory Alineacion.fromJson(Map<String, dynamic> json) => Alineacion(
        partidoId: json['partido_id'] as int,
        formacion: json['formacion'] as String,
        jugadores: [
          for (final j in json['jugadores'] as List)
            JugadorAlineado.fromJson(j as Map<String, dynamic>),
        ],
      );
}
