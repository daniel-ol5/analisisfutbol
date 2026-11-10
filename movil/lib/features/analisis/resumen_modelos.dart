/// Modelos del resumen de métricas  —  CU-43 (T-081).
///
/// Escritos a mano a partir del contrato (docs/api/openapi.json y
/// docs/api/websockets.md). Solo los campos que usa el resumen.
library;

double _num(Object? valor) => (valor as num?)?.toDouble() ?? 0.0;

/// Reparto de la posesión en %: local + visitante + disputa = 100.
class Posesion {
  const Posesion({
    required this.local,
    required this.visitante,
    required this.disputa,
  });

  final double local;
  final double visitante;
  final double disputa;

  static const vacia = Posesion(local: 0, visitante: 0, disputa: 0);

  bool get sinDatos => local + visitante + disputa <= 0;

  /// Formato del mensaje `posesion` del servidor: `{local_pct, visitante_pct, disputa_pct}`.
  factory Posesion.desdePct(Map<String, dynamic> json) => Posesion(
        local: _num(json['local_pct']),
        visitante: _num(json['visitante_pct']),
        disputa: _num(json['disputa_pct']),
      );
}

/// `MetricaEquipo` del contrato (solo lo que muestra el resumen).
class MetricaEquipo {
  const MetricaEquipo({required this.posesionPct, required this.distanciaM});

  final double posesionPct;
  final double distanciaM;

  factory MetricaEquipo.fromJson(Map<String, dynamic> json) => MetricaEquipo(
        posesionPct: _num(json['posesion_pct']),
        distanciaM: _num(json['distancia_m']),
      );
}

/// `MetricasPartido`: GET /analisis/partidos/{id}/metricas.
class MetricasPartido {
  const MetricasPartido({
    required this.local,
    required this.visitante,
    required this.disputaPct,
    this.ultimosLocal,
    this.ultimosVisitante,
  });

  final MetricaEquipo local;
  final MetricaEquipo visitante;
  final double disputaPct;
  final MetricaEquipo? ultimosLocal;
  final MetricaEquipo? ultimosVisitante;

  Posesion get posesion => Posesion(
        local: local.posesionPct,
        visitante: visitante.posesionPct,
        disputa: disputaPct,
      );

  /// Los últimos 5 minutos; la disputa es lo que falta para 100.
  Posesion? get posesionUltimos {
    final l = ultimosLocal, v = ultimosVisitante;
    if (l == null || v == null) return null;
    final disputa = 100 - l.posesionPct - v.posesionPct;
    if (l.posesionPct + v.posesionPct <= 0) return Posesion.vacia;
    return Posesion(
      local: l.posesionPct,
      visitante: v.posesionPct,
      disputa: disputa < 0 ? 0 : disputa,
    );
  }

  factory MetricasPartido.fromJson(Map<String, dynamic> json) {
    MetricaEquipo? opcional(Object? valor) => valor is Map<String, dynamic>
        ? MetricaEquipo.fromJson(valor)
        : null;
    return MetricasPartido(
      local: MetricaEquipo.fromJson(
          json['acumulado_local'] as Map<String, dynamic>? ?? const {}),
      visitante: MetricaEquipo.fromJson(
          json['acumulado_visitante'] as Map<String, dynamic>? ?? const {}),
      disputaPct: _num(json['posesion_disputa_pct']),
      ultimosLocal: opcional(json['ultimos_5_min_local']),
      ultimosVisitante: opcional(json['ultimos_5_min_visitante']),
    );
  }
}

/// `MetricaJugador`: GET .../metricas/jugadores y mensaje `metricas_jugadores`.
class MetricaJugador {
  const MetricaJugador({
    required this.trackId,
    required this.distanciaM,
    required this.sprints,
    this.jugadorId,
    this.nombre,
    this.dorsal,
  });

  final int? jugadorId;
  final int trackId;
  final String? nombre;
  final int? dorsal;
  final double distanciaM;
  final int sprints;

  /// Apellido (o el nombre completo si es una sola palabra) para que entre en media pantalla.
  String get etiqueta {
    final partes = (nombre ?? '').trim().split(RegExp(r'\s+'));
    final apellido = partes.length > 1 ? partes.sublist(1).join(' ') : partes.first;
    if (apellido.isEmpty) return 'Track $trackId';
    return apellido;
  }

  factory MetricaJugador.fromJson(Map<String, dynamic> json) => MetricaJugador(
        jugadorId: (json['jugador_id'] as num?)?.toInt(),
        trackId: (json['track_id'] as num?)?.toInt() ?? 0,
        nombre: json['nombre'] as String?,
        dorsal: (json['dorsal'] as num?)?.toInt(),
        distanciaM: _num(json['distancia_m']),
        sprints: (json['sprints'] as num?)?.toInt() ?? 0,
      );

  static List<MetricaJugador> lista(Object? valor) => valor is List
      ? valor
          .whereType<Map<String, dynamic>>()
          .map(MetricaJugador.fromJson)
          .toList()
      : const [];
}

/// `Intervalo` de 5 minutos (GET .../metricas/intervalos y mensaje `intervalo`).
class IntervaloMetricas {
  const IntervaloMetricas({
    required this.minutoDesde,
    required this.minutoHasta,
    required this.posesion,
  });

  final int minutoDesde;
  final int minutoHasta;
  final Posesion posesion;

  factory IntervaloMetricas.fromJson(Map<String, dynamic> json) {
    final local = json['local'] as Map<String, dynamic>? ?? const {};
    final visitante = json['visitante'] as Map<String, dynamic>? ?? const {};
    return IntervaloMetricas(
      minutoDesde: (json['minuto_desde'] as num?)?.toInt() ?? 0,
      minutoHasta: (json['minuto_hasta'] as num?)?.toInt() ?? 0,
      posesion: Posesion(
        local: _num(local['posesion_pct']),
        visitante: _num(visitante['posesion_pct']),
        disputa: _num(json['posesion_disputa_pct']),
      ),
    );
  }
}
