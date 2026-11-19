/// Recomendaciones tácticas  —  CU-50 (T-094).
///
/// Escrito a mano desde docs/api/openapi.json (`Recomendacion`, `DatoSoporte`)
/// y docs/api/websockets.md (mensaje `recomendacion`).
library;

enum Prioridad {
  critica('CRITICA', 'CRÍTICA'),
  alta('ALTA', 'ALTA'),
  media('MEDIA', 'MEDIA'),
  baja('BAJA', 'BAJA');

  const Prioridad(this.valor, this.etiqueta);
  final String valor;
  final String etiqueta;

  static Prioridad desde(Object? texto) => Prioridad.values.firstWhere(
        (p) => p.valor == texto,
        orElse: () => Prioridad.baja,
      );
}

/// Cifra real que disparó la regla: valor medido contra umbral.
class DatoSoporte {
  const DatoSoporte({required this.metrica, required this.valor, this.umbral});

  final String metrica;
  final double valor;
  final double? umbral;

  factory DatoSoporte.fromJson(Map<String, dynamic> json) => DatoSoporte(
        metrica: json['metrica']?.toString() ?? '',
        valor: (json['valor'] as num?)?.toDouble() ?? 0,
        umbral: (json['umbral'] as num?)?.toDouble(),
      );

  static const _metricas = {
    'minuto': ('Minuto', "'"),
    'altura_linea_m': ('Altura de la línea', ' m'),
    'amplitud_propia_m': ('Amplitud propia', ' m'),
    'compacidad_propia_m': ('Compacidad propia', ' m'),
    'posesion_propia_pct': ('Posesión propia', ' %'),
    'posesion_rival_pct': ('Posesión rival', ' %'),
    'pases_intentados_propios': ('Pases intentados', ''),
    'pases_completados_rival': ('Pases completados rival', ''),
    'precision_pase_propio_pct': ('Precisión de pase', ' %'),
    'ritmo_propio_m_min': ('Ritmo propio', ' m/min'),
    'caida_ritmo_propio_pct': ('Caída del ritmo', ' %'),
    'amarillas_propias_10min': ('Amarillas (10 min)', ''),
    'rojas_propias': ('Expulsiones', ''),
  };

  static String _numero(double v) => v == v.roundToDouble()
      ? v.toStringAsFixed(0)
      : v.toStringAsFixed(1).replaceAll('.', ',');

  /// Por ejemplo «Posesión rival: 68,4 % (umbral 65 %)».
  String get legible {
    final (etiqueta, unidad) = _metricas[metrica] ?? (metrica, '');
    final base = '$etiqueta: ${_numero(valor)}$unidad';
    return umbral == null ? base : '$base (umbral ${_numero(umbral!)}$unidad)';
  }
}

/// T-095 (CU-51): lo que el DT marca con un toque. Una sola vez por recomendación.
enum OpcionValoracion {
  util('UTIL', 'Útil'),
  noUtil('NO_UTIL', 'No útil'),
  aplicada('APLICADA', 'Aplicada');

  const OpcionValoracion(this.valor, this.etiqueta);
  final String valor;
  final String etiqueta;

  /// Cuerpo de POST /asistencia/recomendaciones/{id}/valorar (mismo que la web, T-091).
  Map<String, Object?> get cuerpo => {
        'util': switch (this) {
          OpcionValoracion.util => true,
          OpcionValoracion.noUtil => false,
          OpcionValoracion.aplicada => null,
        },
        'aplicada': this == OpcionValoracion.aplicada,
        'comentario': '',
      };
}

class Recomendacion {
  const Recomendacion({
    required this.id,
    required this.partidoId,
    required this.reglaId,
    required this.t,
    required this.minuto,
    required this.mensaje,
    required this.justificacion,
    required this.prioridad,
    required this.datosSoporte,
    required this.estado,
    this.util,
  });

  final int id;
  final int partidoId;
  final int reglaId;
  final double t;
  final int minuto;
  final String mensaje;
  final String justificacion;
  final Prioridad prioridad;
  final List<DatoSoporte> datosSoporte;

  /// PENDIENTE, VISTA, APLICADA o DESCARTADA.
  final String estado;

  /// T-095: null mientras no se valoró (o si solo se marcó como aplicada).
  final bool? util;

  bool get activa => estado == 'PENDIENTE' || estado == 'VISTA';

  /// T-095: la valoración que ya tiene en el servidor, si tiene.
  OpcionValoracion? get valoracion => switch ((estado, util)) {
        ('APLICADA', _) => OpcionValoracion.aplicada,
        (_, true) => OpcionValoracion.util,
        (_, false) || ('DESCARTADA', _) => OpcionValoracion.noUtil,
        _ => null,
      };

  /// Si el objeto recibido tiene la forma de una recomendación.
  static bool valida(Object? json) =>
      json is Map<String, dynamic> &&
      json['id'] is num &&
      json['regla_id'] is num &&
      json['mensaje'] is String &&
      Prioridad.values.any((p) => p.valor == json['prioridad']);

  factory Recomendacion.fromJson(Map<String, dynamic> json) => Recomendacion(
        id: (json['id'] as num).toInt(),
        partidoId: (json['partido_id'] as num?)?.toInt() ?? 0,
        reglaId: (json['regla_id'] as num).toInt(),
        t: (json['t'] as num?)?.toDouble() ?? 0,
        minuto: (json['minuto'] as num?)?.toInt() ?? 0,
        mensaje: json['mensaje'] as String,
        justificacion: json['justificacion']?.toString() ?? '',
        prioridad: Prioridad.desde(json['prioridad']),
        datosSoporte: (json['datos_soporte'] as List? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(DatoSoporte.fromJson)
            .toList(),
        estado: json['estado']?.toString() ?? 'PENDIENTE',
        util: json['util'] as bool?,
      );
}

const maxActivas = 3;

/// Como máximo 3, por prioridad y, a igual prioridad, la más reciente primero
/// (la misma regla que el servidor con `solo_activas=true`).
List<Recomendacion> ordenarActivas(Iterable<Recomendacion> lista) {
  final activas = lista.where((r) => r.activa).toList()
    ..sort((a, b) {
      final porPrioridad = a.prioridad.index.compareTo(b.prioridad.index);
      if (porPrioridad != 0) return porPrioridad;
      final porT = b.t.compareTo(a.t);
      return porT != 0 ? porT : b.id.compareTo(a.id);
    });
  return activas.take(maxActivas).toList();
}

/// Una nueva (por /vivo) reemplaza a la de la misma regla y desplaza a la de menor prioridad.
List<Recomendacion> incorporar(List<Recomendacion> lista, Recomendacion nueva) =>
    ordenarActivas([
      ...lista.where((r) => r.id != nueva.id && r.reglaId != nueva.reglaId),
      nueva,
    ]);
