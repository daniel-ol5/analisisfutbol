import 'dart:math';

import 'package:areatecnica/app/router.dart';
import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/seguridad/modelos.dart';
import 'package:areatecnica/features/seguridad/perfil_pagina.dart';
import 'package:areatecnica/features/seguridad/validacion.dart';
import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Relación de contraste WCAG entre dos colores.
double _contraste(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  return (max(la, lb) + 0.05) / (min(la, lb) + 0.05);
}

const _perfilJson = {
  'id': 2,
  'club_id': 1,
  'email': 'dt@demo.com',
  'nombre': 'José',
  'apellido': 'Pérez',
  'rol': 'DT',
  'activo': true,
  'club_nombre': 'Club Demo',
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
    modoTema.value = ModoTema.sistema;
  });

  group('T-023 · Tema para uso al sol', () {
    test('el modo sol cumple contraste AAA (7:1) en texto y botones', () {
      final e = temaSol.colorScheme;
      expect(_contraste(e.onSurface, e.surface), greaterThanOrEqualTo(7));
      expect(_contraste(e.onSurfaceVariant, e.surface), greaterThanOrEqualTo(7));
      expect(_contraste(e.onPrimary, e.primary), greaterThanOrEqualTo(7));
      expect(_contraste(e.primary, e.surface), greaterThanOrEqualTo(7));
    });

    test('ningún texto base baja de 16 puntos en ningún tema', () {
      for (final tema in [temaClaro, temaOscuro, temaSol]) {
        final t = tema.textTheme;
        for (final estilo in [t.bodySmall, t.bodyMedium, t.bodyLarge]) {
          expect(estilo!.fontSize, greaterThanOrEqualTo(16));
        }
      }
    });

    test('el modo elegido se guarda y se recupera al reabrir la app', () async {
      await cambiarModoTema(ModoTema.sol);
      modoTema.value = ModoTema.sistema; // simula reinicio
      await cargarModoTema();
      expect(modoTema.value, ModoTema.sol);
    });
  });

  group('CU-05 · Validación de formularios', () {
    test('la contraseña nueva sigue las mismas reglas que la web', () {
      expect(validarPasswordNueva('actual123', 'corta'), contains('al menos 8'));
      expect(validarPasswordNueva('actual123', 'actual123'), contains('distinta'));
      expect(validarPasswordNueva('actual123', 'á' * 40), contains('superar'));
      expect(validarPasswordNueva('actual123', 'nuevaClave456'), isNull);
    });

    test('la confirmación debe coincidir', () {
      expect(validarConfirmacion('abc12345', ''), isNotNull);
      expect(validarConfirmacion('abc12345', 'otra'), contains('no coinciden'));
      expect(validarConfirmacion('abc12345', 'abc12345'), isNull);
    });

    test('nombre y apellido admiten hasta 80 caracteres', () {
      expect(validarNombre('a' * 80, 'El nombre'), isNull);
      expect(validarNombre('a' * 81, 'El nombre'), contains('80'));
    });

    test('Perfil interpreta la respuesta de /seguridad/yo', () {
      final p = Perfil.fromJson(_perfilJson);
      expect(p.nombreCompleto, 'José Pérez');
      expect(p.clubNombre, 'Club Demo');
      expect(p.rolLegible, 'Director técnico');
    });
  });

  group('T-025 · Perfil propio en móvil', () {
    testWidgets('sin sesión, ir al perfil lleva al login', (tester) async {
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      router.go('/perfil');
      await tester.pumpAndSettle();

      expect(find.text('Iniciar sesión'), findsOneWidget);
      expect(find.text('Ingresar'), findsOneWidget);
    });

    testWidgets('muestra nombre, correo, club y rol desde la caché',
        (tester) async {
      await Almacenamiento.guardarSesion('token', 'refresco');
      await Almacenamiento.guardarUsuario(Map.of(_perfilJson));

      await tester.pumpWidget(MaterialApp(theme: temaSol, home: const PerfilPagina()));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('perfil-nombre')), findsOneWidget);
      expect(find.text('José Pérez'), findsOneWidget);
      expect(find.text('dt@demo.com'), findsOneWidget);
      expect(find.text('Club Demo'), findsOneWidget);
      expect(find.text('Director técnico'), findsOneWidget);
      // El formulario viene precargado con los datos actuales.
      expect(find.widgetWithText(TextFormField, 'José'), findsOneWidget);
    });

    testWidgets('el cambio de contraseña valida antes de llamar al servidor',
        (tester) async {
      // Pantalla alta: el formulario entero a la vista, errores incluidos.
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await Almacenamiento.guardarSesion('token', 'refresco');
      await Almacenamiento.guardarUsuario(Map.of(_perfilJson));
      await tester.pumpWidget(MaterialApp(home: const PerfilPagina()));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Cambiar contraseña'));
      await tester.pumpAndSettle();

      expect(find.text('Ingresa tu contraseña actual.'), findsOneWidget);
      expect(find.text('Confirma la nueva contraseña.'), findsOneWidget);
    });

    testWidgets('el modo sol se activa con un toque desde el perfil',
        (tester) async {
      await Almacenamiento.guardarSesion('token', 'refresco');
      await Almacenamiento.guardarUsuario(Map.of(_perfilJson));
      await tester.pumpWidget(MaterialApp(home: const PerfilPagina()));
      await tester.pumpAndSettle();

      final sol = find.widgetWithText(ChoiceChip, 'Sol');
      await tester.scrollUntilVisible(sol, 300,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(sol);
      await tester.pumpAndSettle();

      expect(modoTema.value, ModoTema.sol);
      expect(await Almacenamiento.leerTema(), 'sol');
    });
  });
}
