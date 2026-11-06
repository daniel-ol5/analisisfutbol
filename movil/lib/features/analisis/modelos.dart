/// Modelos de Análisis Táctico en Vivo  —  P5 · CU-40 (T-080).
library;

enum EstadoConexion {
  desconectado,
  conectando,
  conectado,
  reconectando,
  error,
}

enum EquipoDetectado {
  local,
  visitante,
  arbitro,
  desconocido;

  static EquipoDetectado desdeTexto(String? texto) {
    switch (texto?.toUpperCase()) {
      case 'LOCAL':
        return EquipoDetectado.local;
      case 'VISITANTE':
        return EquipoDetectado.visitante;
      case 'ARBITRO':
        return EquipoDetectado.arbitro;
      default:
        return EquipoDetectado.desconocido;
    }
  }

  String get etiqueta {
    switch (this) {
      case EquipoDetectado.local:
        return 'LOCAL';
      case EquipoDetectado.visitante:
        return 'VISITANTE';
      case EquipoDetectado.arbitro:
        return 'ÁRBITRO';
      case EquipoDetectado.desconocido:
        return 'DESCONOCIDO';
    }
  }
}

class PosicionDetectada {
  final int tid;
  final EquipoDetectado equipo;
  final double x;
  final double y;
  final double conf;
  final int? dorsal;

  const PosicionDetectada({
    required this.tid,
    required this.equipo,
    required this.x,
    required this.y,
    required this.conf,
    this.dorsal,
  });

  factory PosicionDetectada.fromJson(Map<String, dynamic> json) {
    return PosicionDetectada(
      tid: (json['tid'] as num?)?.toInt() ?? 0,
      equipo: EquipoDetectado.desdeTexto(json['equipo'] as String?),
      x: (json['x'] as num?)?.toDouble() ?? 0.0,
      y: (json['y'] as num?)?.toDouble() ?? 0.0,
      conf: (json['conf'] as num?)?.toDouble() ?? 0.0,
      dorsal: (json['dorsal'] as num?)?.toInt(),
    );
  }

  Map<String, dynamic> toJson() => {
        'tid': tid,
        'equipo': equipo.etiqueta,
        'x': x,
        'y': y,
        'conf': conf,
        if (dorsal != null) 'dorsal': dorsal,
      };
}

class IndicadorCalidad {
  final bool workerConectado;
  final double fps;
  final int jugadoresDetectados;
  final bool balonVisible;
  final double retrasoS;
  final bool degradado;
  final String? motivo;

  const IndicadorCalidad({
    required this.workerConectado,
    required this.fps,
    required this.jugadoresDetectados,
    required this.balonVisible,
    required this.retrasoS,
    required this.degradado,
    this.motivo,
  });

  factory IndicadorCalidad.fromJson(Map<String, dynamic> json) {
    return IndicadorCalidad(
      workerConectado: json['worker_conectado'] == true,
      fps: (json['fps'] as num?)?.toDouble() ?? 0.0,
      jugadoresDetectados:
          (json['jugadores_detectados'] as num?)?.toInt() ?? 0,
      balonVisible: json['balon_visible'] == true,
      retrasoS: (json['retraso_s'] as num?)?.toDouble() ?? 0.0,
      degradado: json['degradado'] == true,
      motivo: json['motivo'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'worker_conectado': workerConectado,
        'fps': fps,
        'jugadores_detectados': jugadoresDetectados,
        'balon_visible': balonVisible,
        'retraso_s': retrasoS,
        'degradado': degradado,
        if (motivo != null) 'motivo': motivo,
      };
}

class MensajeWorker {
  final int partido;
  final double t;
  final List<PosicionDetectada> jugadores;
  final PosicionDetectada? balon;
  final IndicadorCalidad calidad;

  const MensajeWorker({
    required this.partido,
    required this.t,
    required this.jugadores,
    this.balon,
    required this.calidad,
  });

  factory MensajeWorker.fromJson(Map<String, dynamic> json) {
    final jugadoresRaw = json['jugadores'] as List<dynamic>? ?? [];
    final balonRaw = json['balon'] as Map<String, dynamic>?;
    final calidadRaw =
        json['calidad'] as Map<String, dynamic>? ?? <String, dynamic>{};

    return MensajeWorker(
      partido: (json['partido'] as num?)?.toInt() ?? 0,
      t: (json['t'] as num?)?.toDouble() ?? 0.0,
      jugadores: jugadoresRaw
          .whereType<Map<String, dynamic>>()
          .map(PosicionDetectada.fromJson)
          .toList(),
      balon: balonRaw != null ? PosicionDetectada.fromJson(balonRaw) : null,
      calidad: IndicadorCalidad.fromJson(calidadRaw),
    );
  }

  Map<String, dynamic> toJson() => {
        'partido': partido,
        't': t,
        'jugadores': jugadores.map((j) => j.toJson()).toList(),
        if (balon != null) 'balon': balon!.toJson(),
        'calidad': calidad.toJson(),
      };
}

class PuntoTrayectoria {
  final double x;
  final double y;
  final double t;

  const PuntoTrayectoria({
    required this.x,
    required this.y,
    required this.t,
  });
}

class PartidoInfo {
  final int id;
  final int equipoId;
  final String rival;
  final bool esLocal;
  final String? fechaHora;
  final String? sede;
  final String estado;
  final int golesFavor;
  final int golesContra;
  final String? parte;
  final int minutoActual;

  const PartidoInfo({
    required this.id,
    required this.equipoId,
    required this.rival,
    required this.esLocal,
    this.fechaHora,
    this.sede,
    required this.estado,
    required this.golesFavor,
    required this.golesContra,
    this.parte,
    required this.minutoActual,
  });

  factory PartidoInfo.fromJson(Map<String, dynamic> json) {
    return PartidoInfo(
      id: (json['id'] as num?)?.toInt() ?? 0,
      equipoId: (json['equipo_id'] as num?)?.toInt() ?? 0,
      rival: json['rival']?.toString() ?? 'Rival',
      esLocal: json['es_local'] != false,
      fechaHora: json['fecha_hora']?.toString(),
      sede: json['sede']?.toString(),
      estado: json['estado']?.toString() ?? 'PROGRAMADO',
      golesFavor: (json['goles_favor'] as num?)?.toInt() ?? 0,
      golesContra: (json['goles_contra'] as num?)?.toInt() ?? 0,
      parte: json['parte']?.toString(),
      minutoActual: (json['minuto_actual'] as num?)?.toInt() ?? 0,
    );
  }
}

