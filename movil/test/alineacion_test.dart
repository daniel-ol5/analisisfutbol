import 'dart:io';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/deportivo/alineacion/alineacion_pagina.dart';
import 'package:areatecnica/features/deportivo/alineacion/api.dart';
import 'package:areatecnica/features/deportivo/alineacion/cancha.dart';
import 'package:areatecnica/features/deportivo/alineacion/modelos.dart';
import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Respuesta de GET /deportivo/partidos/7/alineacion: 4-3-3, 11 titulares y 3 suplentes.
Map<String, dynamic> _json() {
  // (dorsal, apellido, posicion, pos_x, pos_y, capitan)
  const titulares = [
    (1, 'Arandia', 'ARQ', 5, 50, false),
    (2, 'Rivera', 'DEF', 25, 85, false),
    (4, 'Salinas', 'DEF', 22, 62, false),
    (3, 'Méndez', 'DEF', 22, 38, false),
    (6, 'Ortega', 'DEF', 25, 15, false),
    (5, 'Rojas', 'MED', 45, 50, false),
    (8, 'Navarro', 'MED', 52, 72, false),
    (10, 'Fuentes', 'MED', 52, 28, false),
    (7, 'Aguilera', 'DEL', 75, 85, false),
    (9, 'Ibáñez', 'DEL', 80, 50, true),
    (11, 'Cuéllar', 'DEL', 75, 15, false),
  ];
  const suplentes = [(18, 'Peña', 'MED'), (12, 'Quiroga', 'ARQ'), (13, 'Paredes', 'DEF')];
  return {
    'id': 1,
    'partido_id': 7,
    'formacion': '4-3-3',
    'jugadores': [
      for (final (dorsal, apellido, posicion, x, y, capitan) in titulares)
        {
          'jugador_id': 100 + dorsal, 'es_titular': true, 'es_capitan': capitan,
          'pos_x': x, 'pos_y': y, 'minuto_entra': null, 'minuto_sale': null,
          'nombre': 'N$dorsal', 'apellido': apellido, 'dorsal': dorsal,
          'posicion': posicion,
        },
      for (final (dorsal, apellido, posicion) in suplentes)
        {
          'jugador_id': 100 + dorsal, 'es_titular': false, 'es_capitan': false,
          'pos_x': 0, 'pos_y': 0, 'minuto_entra': null, 'minuto_sale': null,
          'nombre': 'N$dorsal', 'apellido': apellido, 'dorsal': dorsal,
          'posicion': posicion,
        },
    ],
  };
}

Future<Alineacion> _desdeServidor(int _) async => Alineacion.fromJson(_json());
Future<Alineacion?> _sinCache(int _) async => null;

Future<void> _pantallaAlta(WidgetTester tester) async {
  // La cancha y el banco enteros a la vista.
  tester.view.physicalSize = const Size(900, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

Widget _app(Widget pagina) => MaterialApp(theme: temaSol, home: pagina);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('T-053 · Modelo de la alineación', () {
    test('separa titulares, suplentes y capitán', () {
      final a = Alineacion.fromJson(_json());
      expect(a.formacion, '4-3-3');
      expect(a.titulares, hasLength(11));
      expect(a.suplentes.map((j) => j.dorsal), [12, 13, 18]);
      expect(a.capitan?.apellido, 'Ibáñez');
      expect(a.titulares.where((j) => j.esArquero), hasLength(1));
    });

    test('el arco propio va abajo y la banda izquierda a la izquierda', () {
      final a = Alineacion.fromJson(_json());
      const tamano = Size(680, 1050);
      final arquero = posicionEnPantalla(a.titulares.firstWhere((j) => j.dorsal == 1), tamano);
      final nueve = posicionEnPantalla(a.titulares.firstWhere((j) => j.dorsal == 9), tamano);
      final extremoIzq = posicionEnPantalla(a.titulares.firstWhere((j) => j.dorsal == 11), tamano);

      expect(arquero.dx, closeTo(340, 0.01)); // centro
      expect(arquero.dy, greaterThan(tamano.height * 0.9)); // abajo
      expect(nueve.dy, lessThan(tamano.height * 0.25)); // arriba, cerca del arco rival
      expect(extremoIzq.dx, lessThan(tamano.width * 0.2)); // banda izquierda
    });

    test('la alineación descargada queda guardada para verla sin conexión', () async {
      await Almacenamiento.guardarCache('alineacion.7', _json());
      final guardada = await alineacionEnCache(7);
      expect(guardada?.titulares, hasLength(11));
      expect(await alineacionEnCache(8), isNull);
    });

    test('cerrar sesión borra las alineaciones guardadas', () async {
      await Almacenamiento.guardarSesion('a', 'r');
      await Almacenamiento.guardarCache('alineacion.7', _json());
      await Almacenamiento.guardarTema('sol');

      await Almacenamiento.borrarToken();

      expect(await alineacionEnCache(7), isNull);
      expect(await Almacenamiento.leerTema(), 'sol');
    });
  });

  group('T-053 · Ver alineación en móvil', () {
    testWidgets('dibuja los 11 titulares, el capitán, la formación y el banco',
        (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AlineacionPagina(
          partidoId: 7, obtener: _desdeServidor, enCache: _sinCache)));
      await tester.pumpAndSettle();

      expect(find.byType(FichaJugador), findsNWidgets(11));
      expect(find.byKey(const Key('insignia-capitan')), findsOneWidget);
      expect(find.byKey(const Key('formacion')), findsOneWidget);
      expect(find.text('4-3-3'), findsOneWidget);
      expect(find.text('Capitán: 9 Ibáñez'), findsOneWidget);
      expect(find.text('Suplentes (3)'), findsOneWidget);
      expect(find.text('N12 Quiroga'), findsOneWidget);
      expect(find.text('Arquero'), findsOneWidget); // Quiroga en el banco
    });

    testWidgets('sin conexión muestra la última alineación guardada', (tester) async {
      await _pantallaAlta(tester);
      Future<Alineacion> sinRed(int _) => throw const SocketException('sin red');
      Future<Alineacion?> guardada(int _) async => Alineacion.fromJson(_json());

      await tester.pumpWidget(_app(
          AlineacionPagina(partidoId: 7, obtener: sinRed, enCache: guardada)));
      await tester.pumpAndSettle();

      expect(find.textContaining('Sin conexión'), findsOneWidget);
      expect(find.byType(FichaJugador), findsNWidgets(11));
    });

    testWidgets('partido sin alineación lo dice claramente', (tester) async {
      Future<Alineacion> noHay(int _) =>
          throw ErrorApi(404, 'El partido todavía no tiene alineación');

      await tester.pumpWidget(_app(
          AlineacionPagina(partidoId: 7, obtener: noHay, enCache: _sinCache)));
      await tester.pumpAndSettle();

      expect(find.textContaining('todavía no tiene alineación'), findsOneWidget);
      expect(find.byType(Cancha), findsNothing);
    });

    testWidgets('sin conexión y sin nada guardado ofrece reintentar', (tester) async {
      Future<Alineacion> sinRed(int _) => throw const SocketException('sin red');

      await tester.pumpWidget(_app(
          AlineacionPagina(partidoId: 7, obtener: sinRed, enCache: _sinCache)));
      await tester.pumpAndSettle();

      expect(find.text('Sin conexión con el servidor.'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Reintentar'), findsOneWidget);
    });
  });
}
