/// Alertas de fatiga y de riesgo de expulsión  —  CU-52 (HU-46, T-095).
///
/// Contrato: `GET /asistencia/partidos/{id}/alertas` (backend/app/asistencia/schemas.py::Alerta).
/// El backend las calcula al consultar; la app solo las muestra.
library;

enum TipoAlerta {
  fatiga('FATIGA', 'Fatiga'),
  riesgoExpulsion('RIESGO_EXPULSION', 'Riesgo de expulsión');

  const TipoAlerta(this.valor, this.etiqueta);
  final String valor;
  final String etiqueta;

  static TipoAlerta desde(Object? valor) =>
      values.firstWhere((t) => t.valor == valor, orElse: () => fatiga);
}

enum PrioridadAlerta {
  critica('CRITICA'),
  alta('ALTA'),
  media('MEDIA'),
  baja('BAJA');

  const PrioridadAlerta(this.valor);
  final String valor;

  static PrioridadAlerta desde(Object? valor) =>
      values.firstWhere((p) => p.valor == valor, orElse: () => media);
}

class DatoSoporte {
  const DatoSoporte({required this.metrica, required this.valor, this.umbral});

  final String metrica;
  final double valor;
  final double? umbral;

  factory DatoSoporte.fromJson(Map<String, dynamic> json) => DatoSoporte(
        metrica: json['metrica'] as String? ?? '',
        valor: (json['valor'] as num?)?.toDouble() ?? 0,
        umbral: (json['umbral'] as num?)?.toDouble(),
      );
}

class Alerta {
  const Alerta({
    required this.tipo,
    required this.jugadorId,
    required this.minuto,
    required this.mensaje,
    required this.justificacion,
    required this.prioridad,
    this.nombre,
    this.dorsal,
    this.datosSoporte = const [],
  });

  final TipoAlerta tipo;
  final int jugadorId;
  final String? nombre;
  final int? dorsal;
  final int minuto;
  final String mensaje;
  final String justificacion;
  final PrioridadAlerta prioridad;
  final List<DatoSoporte> datosSoporte;

  /// Identidad de la situación: el mismo tipo de alerta sobre el mismo jugador.
  String get clave => '${tipo.valor}-$jugadorId';

  /// "#8 Pérez", o lo que haya.
  String get quien {
    if (dorsal != null && nombre != null) return '#$dorsal $nombre';
    return nombre ?? (dorsal != null ? '#$dorsal' : 'Jugador $jugadorId');
  }

  factory Alerta.fromJson(Map<String, dynamic> json) => Alerta(
        tipo: TipoAlerta.desde(json['tipo']),
        jugadorId: json['jugador_id'] as int,
        nombre: json['nombre'] as String?,
        dorsal: json['dorsal'] as int?,
        minuto: json['minuto'] as int? ?? 0,
        mensaje: json['mensaje'] as String? ?? '',
        justificacion: json['justificacion'] as String? ?? '',
        prioridad: PrioridadAlerta.desde(json['prioridad']),
        datosSoporte: (json['datos_soporte'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(DatoSoporte.fromJson)
            .toList(),
      );

  /// Ignora lo que no tenga la forma esperada en vez de romper la pantalla.
  static List<Alerta> lista(Object? json) => json is List
      ? json
          .whereType<Map<String, dynamic>>()
          .where((m) => m['jugador_id'] is int)
          .map(Alerta.fromJson)
          .toList()
      : const [];
}
