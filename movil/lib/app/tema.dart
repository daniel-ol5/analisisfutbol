/// Tema visual de la aplicación  —  T-023.
///
/// Pensado para las condiciones reales de uso: el DT está de pie, al sol, con
/// una mano y diez segundos de atención. De ahí el alto contraste y que ningún
/// texto baje de 16 puntos.
library;

import 'package:flutter/material.dart';

import '../shared/api/almacenamiento.dart';

const verde = Color(0xFF0B6B45);
const verdeClaro = Color(0xFF4CC38A);
const ambar = Color(0xFFB36C13);
const rojo = Color(0xFFA2372A);

/// Verde más oscuro para el modo sol: sobre blanco puro supera 7:1 (WCAG AAA).
const verdeSol = Color(0xFF064A30);

ThemeData _base(Brightness brillo) {
  final esquema = ColorScheme.fromSeed(
    seedColor: verde,
    brightness: brillo,
  );
  return _tema(esquema);
}

ThemeData _tema(ColorScheme esquema, {double grosorBorde = 1}) {
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
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(88, 56),
        side: BorderSide(color: esquema.outline, width: grosorBorde),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(
        borderSide: BorderSide(color: esquema.outline, width: grosorBorde),
      ),
      enabledBorder: OutlineInputBorder(
        borderSide: BorderSide(color: esquema.outline, width: grosorBorde),
      ),
      labelStyle: const TextStyle(fontSize: 16),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 72,
      labelTextStyle: WidgetStateProperty.all(
        const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: esquema.outlineVariant, width: grosorBorde),
        borderRadius: BorderRadius.circular(6),
      ),
    ),
  );
}

final temaClaro = _base(Brightness.light);
final temaOscuro = _base(Brightness.dark);

/// Modo sol: blanco y negro puros, bordes gruesos y nada de grises suaves que
/// se pierden con el reflejo de la pantalla.
final temaSol = _tema(
  ColorScheme.fromSeed(seedColor: verde).copyWith(
    primary: verdeSol,
    onPrimary: Colors.white,
    surface: Colors.white,
    onSurface: Colors.black,
    onSurfaceVariant: Colors.black,
    outline: Colors.black,
    outlineVariant: Colors.black,
    surfaceContainerLowest: Colors.white,
    surfaceContainerLow: Colors.white,
    surfaceContainer: Colors.white,
    surfaceContainerHigh: Colors.white,
    surfaceContainerHighest: Colors.white,
    secondaryContainer: const Color(0xFFBFE5D1),
    onSecondaryContainer: Colors.black,
    error: const Color(0xFF8C1D12),
  ),
  grosorBorde: 2,
);

enum ModoTema {
  sistema('Automático'),
  claro('Claro'),
  oscuro('Oscuro'),
  sol('Sol');

  const ModoTema(this.etiqueta);
  final String etiqueta;

  ThemeMode get themeMode => switch (this) {
        ModoTema.sistema => ThemeMode.system,
        ModoTema.oscuro => ThemeMode.dark,
        ModoTema.claro || ModoTema.sol => ThemeMode.light,
      };
}

/// Modo elegido por el usuario. Se guarda en el dispositivo (T-024).
final modoTema = ValueNotifier<ModoTema>(ModoTema.sistema);

Future<void> cargarModoTema() async {
  final guardado = await Almacenamiento.leerTema();
  modoTema.value = ModoTema.values.firstWhere(
    (m) => m.name == guardado,
    orElse: () => ModoTema.sistema,
  );
}

Future<void> cambiarModoTema(ModoTema modo) async {
  modoTema.value = modo;
  await Almacenamiento.guardarTema(modo.name);
}
