/// Modelos de Gestión Deportiva para la app móvil  —  CU-09.
library;

import 'package:flutter/material.dart';

class Equipo {
  const Equipo({
    required this.id,
    required this.clubId,
    required this.nombre,
    required this.categoria,
    required this.temporada,
    required this.colorLocal,
    required this.colorVisitante,
    required this.colorArquero,
    required this.activo,
    required this.jugadores,
  });

  final int id;
  final int clubId;
  final String nombre;
  final String categoria;
  final String temporada;
  final String colorLocal;
  final String colorVisitante;
  final String colorArquero;
  final bool activo;
  final int jugadores;

  factory Equipo.fromJson(Map<String, dynamic> json) => Equipo(
        id: json['id'] as int? ?? 0,
        clubId: json['club_id'] as int? ?? 0,
        nombre: json['nombre'] as String? ?? '',
        categoria: json['categoria'] as String? ?? '',
        temporada: json['temporada'] as String? ?? '',
        colorLocal: json['color_local'] as String? ?? '#1E5AA8',
        colorVisitante: json['color_visitante'] as String? ?? '#FFFFFF',
        colorArquero: json['color_arquero'] as String? ?? '#F2C200',
        activo: json['activo'] as bool? ?? true,
        jugadores: json['jugadores'] as int? ?? 0,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'club_id': clubId,
        'nombre': nombre,
        'categoria': categoria,
        'temporada': temporada,
        'color_local': colorLocal,
        'color_visitante': colorVisitante,
        'color_arquero': colorArquero,
        'activo': activo,
        'jugadores': jugadores,
      };

  Color get colorLocalParsed => parseHexColor(colorLocal);
  Color get colorVisitanteParsed => parseHexColor(colorVisitante);
  Color get colorArqueroParsed => parseHexColor(colorArquero);

  static Color parseHexColor(String hex) {
    var c = hex.replaceAll('#', '').trim();
    if (c.length == 6) {
      c = 'FF$c';
    }
    final val = int.tryParse(c, radix: 16);
    return val != null ? Color(val) : const Color(0xFF1E5AA8);
  }

  /// Determina si un color es claro para usar texto negro o blanco garantizando
  /// máximo contraste y legibilidad directa bajo la luz del sol.
  static bool esColorClaro(Color color) {
    // Luminancia relativa estándar ITU-R BT.709
    final luminancia =
        (0.299 * color.r + 0.587 * color.g + 0.114 * color.b);
    return luminancia > 0.65;
  }
}

/// Etiquetas en español de la posición de juego  —  CU-11.
const Map<String, String> etiquetasPosicion = {
  'ARQ': 'Arquero',
  'DEF': 'Defensor',
  'MED': 'Mediocampista',
  'DEL': 'Delantero',
};

/// Etiquetas en español del pie hábil  —  CU-11.
const Map<String, String> etiquetasPie = {
  'IZQ': 'Izquierdo',
  'DER': 'Derecho',
  'AMBOS': 'Ambos',
};

class Jugador {
  const Jugador({
    required this.id,
    required this.equipoId,
    required this.nombre,
    required this.apellido,
    required this.dorsal,
    required this.posicion,
    required this.pieHabil,
    required this.alturaCm,
    required this.pesoKg,
    required this.activo,
  });

  final int id;
  final int equipoId;
  final String nombre;
  final String apellido;
  final int dorsal;
  final String posicion;
  final String pieHabil;
  final int alturaCm;
  final double? pesoKg;
  final bool activo;

  String get nombreCompleto => '$nombre $apellido';
  String get posicionLegible => etiquetasPosicion[posicion] ?? posicion;
  String get pieLegible => etiquetasPie[pieHabil] ?? pieHabil;

  factory Jugador.fromJson(Map<String, dynamic> json) => Jugador(
        id: json['id'] as int? ?? 0,
        equipoId: json['equipo_id'] as int? ?? 0,
        nombre: json['nombre'] as String? ?? '',
        apellido: json['apellido'] as String? ?? '',
        dorsal: json['dorsal'] as int? ?? 0,
        posicion: json['posicion'] as String? ?? 'MED',
        pieHabil: json['pie_habil'] as String? ?? 'DER',
        alturaCm: json['altura_cm'] as int? ?? 0,
        pesoKg: (json['peso_kg'] as num?)?.toDouble(),
        activo: json['activo'] as bool? ?? true,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'equipo_id': equipoId,
        'nombre': nombre,
        'apellido': apellido,
        'dorsal': dorsal,
        'posicion': posicion,
        'pie_habil': pieHabil,
        'altura_cm': alturaCm,
        'peso_kg': pesoKg,
        'activo': activo,
      };
}
