/// Modelos de eventos manuales del partido — CU-36, CU-37 y CU-38.
library;

import 'package:uuid/uuid.dart';

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
    this.uuid,
    this.capturadoEn,
  });

  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;
  final String? uuid;
  final DateTime? capturadoEn;

  EventoCrear conIdentidad({
    DateTime Function()? reloj,
    String Function()? generarUuid,
  }) => EventoCrear(
    tipo: tipo,
    equipo: equipo,
    jugadorId: jugadorId,
    jugadorEntraId: jugadorEntraId,
    uuid: uuid ?? (generarUuid ?? const Uuid().v4)(),
    capturadoEn: capturadoEn ?? (reloj ?? DateTime.now)().toUtc(),
  );

  Map<String, dynamic> toJson() => {
    if (uuid != null) 'uuid': uuid,
    if (capturadoEn != null)
      'capturado_en': capturadoEn!.toUtc().toIso8601String(),
    'tipo': tipo.codigo,
    'equipo': equipo,
    if (jugadorId != null) 'jugador_id': jugadorId,
    if (jugadorEntraId != null) 'jugador_entra_id': jugadorEntraId,
  };

  factory EventoCrear.fromJson(Map<String, dynamic> json) => EventoCrear(
    uuid: json['uuid'] as String?,
    capturadoEn: json['capturado_en'] == null
        ? null
        : DateTime.parse(json['capturado_en'] as String).toUtc(),
    tipo: TipoEvento.values.firstWhere((tipo) => tipo.codigo == json['tipo']),
    equipo: json['equipo'] as String,
    jugadorId: json['jugador_id'] as int?,
    jugadorEntraId: json['jugador_entra_id'] as int?,
  );
}

class EventoManual {
  const EventoManual({
    required this.id,
    required this.partidoId,
    required this.tipo,
    required this.equipo,
    required this.minuto,
    required this.creadoEn,
    this.uuid,
    this.jugadorId,
    this.jugadorEntraId,
    this.convertidaEnRoja = false,
    this.pendiente = false,
  });

  final int id;
  final int partidoId;
  final String? uuid;
  final TipoEvento tipo;
  final String equipo;
  final int? jugadorId;
  final int? jugadorEntraId;
  final int minuto;
  final bool convertidaEnRoja;
  final DateTime creadoEn;
  final bool pendiente;

  factory EventoManual.fromJson(Map<String, dynamic> json) => EventoManual(
    id: json['id'] as int,
    partidoId: json['partido_id'] as int,
    uuid: json['uuid'] as String?,
    tipo: TipoEvento.values.firstWhere((tipo) => tipo.codigo == json['tipo']),
    equipo: json['equipo'] as String,
    jugadorId: json['jugador_id'] as int?,
    jugadorEntraId: json['jugador_entra_id'] as int?,
    minuto: json['minuto'] as int,
    convertidaEnRoja: json['convertida_en_roja'] as bool? ?? false,
    creadoEn: DateTime.parse(json['creado_en'] as String).toLocal(),
  );

  factory EventoManual.pendiente({
    required int partidoId,
    required EventoCrear evento,
    int minutoEstimado = 0,
  }) => EventoManual(
    id: -1,
    partidoId: partidoId,
    uuid: evento.uuid,
    tipo: evento.tipo,
    equipo: evento.equipo,
    jugadorId: evento.jugadorId,
    jugadorEntraId: evento.jugadorEntraId,
    minuto: minutoEstimado,
    creadoEn: evento.capturadoEn?.toLocal() ?? DateTime.now(),
    pendiente: true,
  );
}
