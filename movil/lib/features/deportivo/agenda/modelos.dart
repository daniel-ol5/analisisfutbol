/// Modelo de la agenda de partidos  —  CU-15 · T-052 (HU-14).
library;

/// Un partido de la agenda (respuesta de GET /deportivo/partidos).
class Partido {
  const Partido({
    required this.id,
    required this.equipoId,
    required this.rival,
    required this.esLocal,
    required this.fechaHora,
    required this.sede,
    required this.estado,
    this.golesFavor = 0,
    this.golesContra = 0,
  });

  final int id;
  final int equipoId;
  final String rival;
  final bool esLocal;

  /// En la hora local del teléfono; el backend la manda en UTC.
  final DateTime fechaHora;
  final String sede;

  /// PROGRAMADO, EN_CURSO, FINALIZADO, PROCESANDO, ANALIZADO o CANCELADO.
  final String estado;
  final int golesFavor;
  final int golesContra;

  /// Todavía no se jugó (o se está jugando): va en "Próximos".
  bool get pendiente => estado == 'PROGRAMADO' || estado == 'EN_CURSO';
  bool get cancelado => estado == 'CANCELADO';

  /// Ya se jugó: tiene resultado para mostrar.
  bool get conResultado => !pendiente && !cancelado;

  String get estadoLegible => switch (estado) {
        'PROGRAMADO' => 'Programado',
        'EN_CURSO' => 'En curso',
        'FINALIZADO' => 'Finalizado',
        'PROCESANDO' => 'Procesando',
        'ANALIZADO' => 'Analizado',
        'CANCELADO' => 'Cancelado',
        _ => estado,
      };

  factory Partido.fromJson(Map<String, dynamic> json) => Partido(
        id: json['id'] as int,
        equipoId: json['equipo_id'] as int,
        rival: json['rival'] as String? ?? '',
        esLocal: json['es_local'] as bool? ?? true,
        fechaHora: DateTime.parse(json['fecha_hora'] as String).toLocal(),
        sede: json['sede'] as String? ?? '',
        estado: json['estado'] as String? ?? 'PROGRAMADO',
        golesFavor: json['goles_favor'] as int? ?? 0,
        golesContra: json['goles_contra'] as int? ?? 0,
      );
}

/// Filtros básicos de la agenda (T-052). Se aplican en el teléfono sobre la
/// agenda descargada, así que también funcionan sin conexión.
enum Momento {
  todos('Todos'),
  proximos('Próximos'),
  jugados('Jugados'),
  cancelados('Cancelados');

  const Momento(this.etiqueta);
  final String etiqueta;

  bool incluye(Partido p) => switch (this) {
        Momento.todos => true,
        Momento.proximos => p.pendiente,
        Momento.jugados => p.conResultado,
        Momento.cancelados => p.cancelado,
      };
}

class FiltroAgenda {
  const FiltroAgenda({this.momento = Momento.todos, this.equipoId});

  final Momento momento;

  /// null = todos los equipos del club.
  final int? equipoId;

  bool get activo => momento != Momento.todos || equipoId != null;

  List<Partido> aplicar(List<Partido> partidos) => [
        for (final p in partidos)
          if (momento.incluye(p) && (equipoId == null || p.equipoId == equipoId)) p,
      ];

  FiltroAgenda conMomento(Momento m) => FiltroAgenda(momento: m, equipoId: equipoId);
  FiltroAgenda conEquipo(int? id) => FiltroAgenda(momento: momento, equipoId: id);
}

/// La agenda separada como se lee en la cancha: lo que viene primero.
class Agenda {
  Agenda(List<Partido> partidos)
      : proximos = partidos.where((p) => p.pendiente).toList()
          ..sort(_proximosPrimero),
        jugados = partidos.where((p) => !p.pendiente).toList()
          ..sort((a, b) => b.fechaHora.compareTo(a.fechaHora));

  /// En curso arriba; después los programados, del más cercano al más lejano.
  final List<Partido> proximos;

  /// Jugados y cancelados ("Anteriores"), del más reciente al más antiguo.
  final List<Partido> jugados;

  bool get vacia => proximos.isEmpty && jugados.isEmpty;

  static int _proximosPrimero(Partido a, Partido b) {
    final enCurso = (b.estado == 'EN_CURSO' ? 1 : 0) - (a.estado == 'EN_CURSO' ? 1 : 0);
    return enCurso != 0 ? enCurso : a.fechaHora.compareTo(b.fechaHora);
  }
}

const _dias = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'];
const _meses = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

/// "sáb 15 nov · 16:00". Sin el año si es el año en curso.
String fechaCorta(DateTime f, {DateTime? hoy}) {
  final ahora = hoy ?? DateTime.now();
  final hora = '${f.hour.toString().padLeft(2, '0')}:${f.minute.toString().padLeft(2, '0')}';
  final anio = f.year == ahora.year ? '' : ' ${f.year}';
  return '${_dias[f.weekday - 1]} ${f.day} ${_meses[f.month - 1]}$anio · $hora';
}
