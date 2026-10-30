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
