/// Modelos de eventos manuales del partido — CU-36, CU-37 y CU-38.
library;

enum TipoEvento {
  gol('GOL', 'Gol'),
  amarilla('AMARILLA', 'Amarilla'),
  roja('ROJA', 'Roja'),
  sustitucion('SUSTITUCION', 'Cambio');

  const TipoEvento(this.codigo, this.etiqueta);
  final String codigo;
  final String etiqueta;
}

class EventoCrear {
  const EventoCrear({
    required this.tipo,
    required this.equipo,
    this.jugadorId,
    this.jugadorEntraId,
  });

  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;

  Map<String, dynamic> toJson() => {
    'tipo': tipo.codigo,
    'equipo': equipo,
    if (jugadorId != null) 'jugador_id': jugadorId,
    if (jugadorEntraId != null) 'jugador_entra_id': jugadorEntraId,
  };
}

class EventoManual {
  const EventoManual({
    required this.id,
    required this.partidoId,
    required this.tipo,
    required this.equipo,
    required this.minuto,
    required this.creadoEn,
    this.jugadorId,
    this.jugadorEntraId,
    this.convertidaEnRoja = false,
  });

  final int id;
  final int partidoId;
  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;
  final int minuto;
  final bool convertidaEnRoja;
  final DateTime creadoEn;

  factory EventoManual.fromJson(Map<String, dynamic> json) => EventoManual(
    id: json['id'] as int,
    partidoId: json['partido_id'] as int,
    tipo: TipoEvento.values.firstWhere((tipo) => tipo.codigo == json['tipo']),
    equipo: json['equipo'] as String,
    jugadorId: json['jugador_id'] as int?,
    jugadorEntraId: json['jugador_entra_id'] as int?,
    minuto: json['minuto'] as int,
    convertidaEnRoja: json['convertida_en_roja'] as bool? ?? false,
    creadoEn: DateTime.parse(json['creado_en'] as String).toLocal(),
  );
}
