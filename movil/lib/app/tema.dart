/// Tema visual de la aplicación.
///
/// Pensado para las condiciones reales de uso: el DT está de pie, al sol, con
/// una mano y diez segundos de atención. De ahí el alto contraste y que ningún
/// texto baje de 16 puntos.
library;

import 'package:flutter/material.dart';

const verde = Color(0xFF0B6B45);
const verdeClaro = Color(0xFF4CC38A);
const ambar = Color(0xFFB36C13);
const rojo = Color(0xFFA2372A);

ThemeData _base(Brightness brillo) {
  final esquema = ColorScheme.fromSeed(
    seedColor: verde,
    brightness: brillo,
  );
  return ThemeData(
    colorScheme: esquema,
    useMaterial3: true,
    // Ningún texto por debajo de 16: tiene que leerse al sol.
    textTheme: const TextTheme(
      bodySmall: TextStyle(fontSize: 16),
      bodyMedium: TextStyle(fontSize: 16),
      bodyLarge: TextStyle(fontSize: 18),
      labelLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      titleMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
      titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        // Zona táctil grande: se usa con una sola mano y sin mirar.
        minimumSize: const Size(88, 56),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: esquema.outlineVariant),
        borderRadius: BorderRadius.circular(6),
      ),
    ),
  );
}

final temaClaro = _base(Brightness.light);
final temaOscuro = _base(Brightness.dark);
