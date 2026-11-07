/// Tema visual de la aplicación  —  T-023.
///
/// Unificado con la paleta analítica de la Web:
///   - #0D9488 (Teal 600 - Primario)
///   - #14B8A6 (Teal 500 - Acento luminoso)
///   - #1F2937 (Slate 800 - Pizarra estructural / Sidebar / Texto)
///   - #F0FDFA (Teal 50 - Superficie de acento suave)
///
/// Conserva el alto contraste para lectura al sol (WCAG AAA en modo Sol) y
/// ningún texto base por debajo de 16 puntos.
library;

import 'package:flutter/material.dart';

import '../shared/api/almacenamiento.dart';

/// Colores principales de marca (se mantiene el alias `verde` por compatibilidad).
const verde = Color(0xFF0D9488);
const verdeClaro = Color(0xFF14B8A6);
const pizarra = Color(0xFF1F2937);
const pizarraOscura = Color(0xFF111827);
const mentaSuave = Color(0xFFF0FDFA);
const mentaBorde = Color(0xFF99F6E4);
const fondoClaro = Color(0xFFF8FAFC);

const ambar = Color(0xFFD97706);
const rojo = Color(0xFFDC2626);

/// Teal profundo para el modo sol: sobre blanco puro supera 7:1 (WCAG AAA).
const verdeSol = Color(0xFF064E46);

ThemeData _tema(
  ColorScheme esquema, {
  required Color fondoScaffold,
  required Color fondoAppBar,
  required Color colorBordeTarjeta,
  double grosorBorde = 1,
}) {
  return ThemeData(
    colorScheme: esquema,
    scaffoldBackgroundColor: fondoScaffold,
    useMaterial3: true,
    // Ningún texto por debajo de 16: tiene que leerse al sol (T-023).
    textTheme: TextTheme(
      bodySmall: TextStyle(fontSize: 16, color: esquema.onSurface),
      bodyMedium: TextStyle(fontSize: 16, color: esquema.onSurface),
      bodyLarge: TextStyle(fontSize: 18, color: esquema.onSurface),
      labelLarge: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      titleMedium: TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: esquema.onSurface,
      ),
      titleLarge: TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w800,
        color: esquema.onSurface,
      ),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: fondoAppBar,
      foregroundColor: esquema.onSurface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0.5,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontSize: 19,
        fontWeight: FontWeight.w800,
        color: esquema.onSurface,
        letterSpacing: -0.3,
      ),
      shape: Border(
        bottom: BorderSide(color: colorBordeTarjeta, width: 1),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: esquema.primary,
        foregroundColor: esquema.onPrimary,
        // Zona táctil grande: se usa con una sola mano y sin mirar.
        minimumSize: const Size(88, 54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(88, 54),
        foregroundColor: esquema.onSurface,
        side: BorderSide(color: esquema.outline, width: grosorBorde),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: esquema.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: esquema.outline, width: grosorBorde),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: esquema.outline, width: grosorBorde),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: esquema.primary, width: 2),
      ),
      labelStyle: const TextStyle(fontSize: 16),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 70,
      backgroundColor: fondoAppBar,
      surfaceTintColor: Colors.transparent,
      indicatorColor: esquema.secondaryContainer,
      labelTextStyle: WidgetStateProperty.all(
        const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: esquema.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: colorBordeTarjeta, width: grosorBorde),
        borderRadius: BorderRadius.circular(10),
      ),
    ),
  );
}

final temaClaro = _tema(
  ColorScheme.fromSeed(
    seedColor: verde,
    brightness: Brightness.light,
  ).copyWith(
    primary: verde,
    onPrimary: Colors.white,
    secondary: verdeClaro,
    onSecondary: Colors.white,
    secondaryContainer: mentaSuave,
    onSecondaryContainer: const Color(0xFF0F766E),
    surface: Colors.white,
    onSurface: pizarra,
    onSurfaceVariant: const Color(0xFF4B5563),
    outline: const Color(0xFF94A3B8),
    outlineVariant: const Color(0xFFE2E8F0),
    error: rojo,
  ),
  fondoScaffold: fondoClaro,
  fondoAppBar: Colors.white,
  colorBordeTarjeta: const Color(0xFFE2E8F0),
);

final temaOscuro = _tema(
  ColorScheme.fromSeed(
    seedColor: verdeClaro,
    brightness: Brightness.dark,
  ).copyWith(
    primary: verdeClaro,
    onPrimary: pizarraOscura,
    secondary: verde,
    secondaryContainer: const Color(0xFF134E4A),
    onSecondaryContainer: mentaSuave,
    surface: pizarra,
    onSurface: const Color(0xFFF8FAFC),
    onSurfaceVariant: const Color(0xFFCBD5E1),
    outline: const Color(0xFF64748B),
    outlineVariant: const Color(0xFF334155),
    error: const Color(0xFFF87171),
  ),
  fondoScaffold: pizarraOscura,
  fondoAppBar: pizarra,
  colorBordeTarjeta: const Color(0xFF334155),
);

/// Modo sol: blanco y negro puros, bordes gruesos y nada de grises suaves que
/// se pierden con el reflejo de la pantalla. Cumple WCAG AAA (7:1).
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
    secondaryContainer: const Color(0xFFCCFBF1),
    onSecondaryContainer: Colors.black,
    error: const Color(0xFF8C1D12),
  ),
  fondoScaffold: Colors.white,
  fondoAppBar: Colors.white,
  colorBordeTarjeta: Colors.black,
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
        ModoTema.sistema => ThemeMode.light,
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
