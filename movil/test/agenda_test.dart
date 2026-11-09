import 'dart:io';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/deportivo/agenda/agenda_pagina.dart';
import 'package:areatecnica/features/deportivo/agenda/api.dart';
import 'package:areatecnica/features/deportivo/agenda/modelos.dart';
import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Un partido como lo devuelve GET /deportivo/partidos (fecha en UTC).
Map<String, dynamic> _partido(int id, String rival, String fecha, String estado,
        {bool local = true, int gf = 0, int gc = 0, int equipo = 1}) =>
    {
      'id': id, 'equipo_id': equipo, 'competicion_id': null, 'rival': rival,
      'es_local': local, 'fecha_hora': fecha, 'sede': 'Cancha municipal',
      'estado': estado, 'ataca_hacia': null, 'goles_favor': gf,
      'goles_contra': gc, 'parte': 0, 'minuto_actual': 0,
    };

/// Agenda de prueba, en el orden del backend (por fecha).
final _json = [
  _partido(1, 'Bolívar', '2026-10-04T19:00:00Z', 'ANALIZADO', gf: 2, gc: 1),
  _partido(2, 'The Strongest', '2026-10-18T19:00:00Z', 'CANCELADO', local: false),
  _partido(3, 'Always Ready', '2026-11-08T20:00:00Z', 'EN_CURSO'),
  _partido(4, 'Wilstermann', '2026-11-22T19:30:00Z', 'PROGRAMADO', local: false),
  _partido(5, 'Oriente', '2026-11-15T19:30:00Z', 'PROGRAMADO', equipo: 2),
];

List<Partido> _partidos() =>
    [for (final p in _json) Partido.fromJson(p)];

Future<List<Partido>> _desdeServidor() async => _partidos();
Future<AgendaGuardada?> _sinCache() async => null;
Future<Map<int, String>> _unEquipo() async => {1: 'Primera'};
Future<Map<int, String>> _dosEquipos() async => {1: 'Primera', 2: 'Reserva'};

Future<void> _pantallaAlta(WidgetTester tester) async {
  tester.view.physicalSize = const Size(900, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

/// La agenda dentro de un router, para comprobar a dónde lleva cada toque.
Widget _app(AgendaPagina pagina) => MaterialApp.router(
      theme: temaSol,
      routerConfig: GoRouter(routes: [
        GoRoute(path: '/', builder: (_, _) => pagina),
        GoRoute(
          path: '/partidos/:id/alineacion',
          builder: (_, e) => Text('alineacion ${e.pathParameters['id']}'),
        ),
        GoRoute(
          path: '/partidos/:id/eventos',
          builder: (_, e) => Text('eventos ${e.pathParameters['id']}'),
        ),
      ]),
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('T-052 · Modelo de la agenda', () {
    test('próximos con el partido en curso primero, después por fecha', () {
      final agenda = Agenda(_partidos());
      expect(agenda.proximos.map((p) => p.id), [3, 5, 4]);
    });

    test('jugados y cancelados, del más reciente al más antiguo', () {
      final agenda = Agenda(_partidos());
      expect(agenda.jugados.map((p) => p.id), [2, 1]);
      expect(agenda.jugados.first.cancelado, isTrue);
      expect(agenda.jugados.last.conResultado, isTrue);
    });

    test('filtro por momento: próximos, jugados con resultado y cancelados', () {
      List<int> ids(FiltroAgenda f) => f.aplicar(_partidos()).map((p) => p.id).toList();
      expect(ids(const FiltroAgenda()), [1, 2, 3, 4, 5]);
      expect(ids(const FiltroAgenda(momento: Momento.proximos)), [3, 4, 5]);
      expect(ids(const FiltroAgenda(momento: Momento.jugados)), [1]);
      expect(ids(const FiltroAgenda(momento: Momento.cancelados)), [2]);
    });

    test('filtro por equipo, combinable con el momento', () {
      List<int> ids(FiltroAgenda f) => f.aplicar(_partidos()).map((p) => p.id).toList();
      expect(ids(const FiltroAgenda(equipoId: 2)), [5]);
      expect(ids(const FiltroAgenda(momento: Momento.proximos, equipoId: 1)), [3, 4]);
      expect(const FiltroAgenda().activo, isFalse);
      expect(const FiltroAgenda().conEquipo(2).activo, isTrue);
      expect(const FiltroAgenda(momento: Momento.jugados).conEquipo(1).momento, Momento.jugados);
    });

    test('la fecha llega en UTC y se muestra en la hora local', () {
      final p = Partido.fromJson(_json.first);
      expect(p.fechaHora.isUtc, isFalse);
      expect(p.fechaHora, DateTime.utc(2026, 10, 4, 19).toLocal());
    });

    test('fecha corta en español, sin el año en curso', () {
      final f = DateTime(2026, 11, 15, 16, 5);
      expect(fechaCorta(f, hoy: DateTime(2026, 11, 8)), 'dom 15 nov · 16:05');
      expect(fechaCorta(f, hoy: DateTime(2027, 1, 1)), 'dom 15 nov 2026 · 16:05');
    });

    test('la agenda descargada queda guardada para verla sin conexión', () async {
      await Almacenamiento.guardarCache('agenda.partidos', {
        'guardado': '2026-11-07T12:00:00Z',
        'partidos': _json,
      });
      final guardada = await agendaEnCache();
      expect(guardada?.partidos, hasLength(5));
      expect(guardada?.guardado, DateTime.utc(2026, 11, 7, 12).toLocal());
    });

    test('una caché de otra versión de la app se ignora', () async {
      await Almacenamiento.guardarCache('agenda.partidos', {'otra': 'cosa'});
      expect(await agendaEnCache(), isNull);
    });

    test('cerrar sesión borra la agenda guardada', () async {
      await Almacenamiento.guardarSesion('a', 'r');
      await Almacenamiento.guardarCache('agenda.partidos', {
        'guardado': '2026-11-07T12:00:00Z',
        'partidos': _json,
      });
      await Almacenamiento.borrarToken();
      expect(await agendaEnCache(), isNull);
    });
  });

  group('T-052 · Agenda de partidos en móvil', () {
    testWidgets('muestra próximos y jugados con estado y resultado', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.text('Próximos (3)'), findsOneWidget);
      expect(find.text('Anteriores (2)'), findsOneWidget);
      expect(find.text('vs Always Ready'), findsOneWidget);
      expect(find.text('En curso'), findsOneWidget);
      expect(find.text('Cancelado'), findsOneWidget);
      expect(find.byKey(const Key('resultado-1')), findsOneWidget);
      expect(find.text('2-1'), findsOneWidget);
      // Con un solo equipo, el nombre no se repite en cada tarjeta.
      expect(find.textContaining('Primera'), findsNothing);
    });

    testWidgets('con varios equipos, cada partido dice de cuál es', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _dosEquipos)));
      await tester.pumpAndSettle();

      expect(
          find.descendant(
              of: find.byType(TarjetaPartido), matching: find.textContaining('Reserva')),
          findsOneWidget);
    });

    testWidgets('un toque en el partido abre su alineación', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      await tester.tap(find.text('vs Wilstermann'));
      await tester.pumpAndSettle();

      expect(find.text('alineacion 4'), findsOneWidget);
    });

    testWidgets('un partido en curso abre la botonera de eventos', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      await tester.tap(find.text('vs Always Ready'));
      await tester.pumpAndSettle();

      expect(find.text('eventos 3'), findsOneWidget);
    });

    testWidgets('sin conexión muestra la última agenda guardada y su fecha', (tester) async {
      await _pantallaAlta(tester);
      Future<List<Partido>> sinRed() => throw const SocketException('sin red');
      Future<AgendaGuardada?> guardada() async => AgendaGuardada(
          partidos: _partidos(), guardado: DateTime(2026, 11, 7, 9, 30));

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: sinRed, enCache: guardada, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.textContaining('Sin conexión: agenda guardada el sáb 7 nov'),
          findsOneWidget);
      expect(find.text('vs Always Ready'), findsOneWidget);
    });

    testWidgets('con el servidor respondiendo no avisa de falta de conexión',
        (tester) async {
      await _pantallaAlta(tester);
      Future<AgendaGuardada?> guardada() async => AgendaGuardada(
          partidos: _partidos(), guardado: DateTime(2026, 11, 7, 9, 30));

      await tester.pumpWidget(_app(AgendaPagina(
          obtener: _desdeServidor, enCache: guardada, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.textContaining('Sin conexión'), findsNothing);
    });

    testWidgets('sin conexión y sin nada guardado ofrece reintentar', (tester) async {
      Future<List<Partido>> sinRed() => throw const SocketException('sin red');

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: sinRed, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.text('Sin conexión con el servidor.'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Reintentar'), findsOneWidget);
    });

    testWidgets('los chips filtran la agenda sin volver a pedirla', (tester) async {
      await _pantallaAlta(tester);
      var pedidos = 0;
      Future<List<Partido>> contar() async {
        pedidos++;
        return _partidos();
      }

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: contar, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ChoiceChip, 'Jugados'));
      await tester.pumpAndSettle();
      expect(find.text('vs Bolívar'), findsOneWidget);
      expect(find.text('vs Always Ready'), findsNothing);
      expect(find.text('vs The Strongest'), findsNothing); // cancelado

      await tester.tap(find.widgetWithText(ChoiceChip, 'Cancelados'));
      await tester.pumpAndSettle();
      expect(find.text('vs The Strongest'), findsOneWidget);
      expect(find.text('vs Bolívar'), findsNothing);
      expect(pedidos, 1);
    });

    testWidgets('con un solo equipo no aparece el filtro por equipo', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();
      expect(find.text('Todos los equipos'), findsNothing);
    });

    testWidgets('con varios equipos se filtra por equipo', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _dosEquipos)));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ChoiceChip, 'Reserva'));
      await tester.pumpAndSettle();
      expect(find.text('vs Oriente'), findsOneWidget);
      expect(find.text('vs Wilstermann'), findsNothing);
      expect(find.text('Próximos (1)'), findsOneWidget);
    });

    testWidgets('si nada coincide, ofrece quitar los filtros', (tester) async {
      await _pantallaAlta(tester);
      await tester.pumpWidget(_app(const AgendaPagina(
          obtener: _desdeServidor, enCache: _sinCache, equipos: _dosEquipos)));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ChoiceChip, 'Reserva'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(ChoiceChip, 'Cancelados'));
      await tester.pumpAndSettle();
      expect(find.text('Ningún partido coincide con los filtros.'), findsOneWidget);

      await tester.tap(find.widgetWithText(OutlinedButton, 'Quitar filtros'));
      await tester.pumpAndSettle();
      expect(find.text('vs Always Ready'), findsOneWidget);
    });

    testWidgets('los filtros también funcionan sin conexión', (tester) async {
      await _pantallaAlta(tester);
      Future<List<Partido>> sinRed() => throw const SocketException('sin red');
      Future<AgendaGuardada?> guardada() async => AgendaGuardada(
          partidos: _partidos(), guardado: DateTime(2026, 11, 7, 9, 30));

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: sinRed, enCache: guardada, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ChoiceChip, 'Próximos'));
      await tester.pumpAndSettle();
      expect(find.text('Próximos (3)'), findsOneWidget);
      expect(find.textContaining('Anteriores'), findsNothing);
    });

    testWidgets('agenda vacía lo dice claramente', (tester) async {
      Future<List<Partido>> vacia() async => [];

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: vacia, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.text('Todavía no hay partidos programados.'), findsOneWidget);
    });

    testWidgets('un error del servidor se muestra con su mensaje', (tester) async {
      Future<List<Partido>> falla() => throw ErrorApi(500, 'Error interno');

      await tester.pumpWidget(_app(
          AgendaPagina(obtener: falla, enCache: _sinCache, equipos: _unEquipo)));
      await tester.pumpAndSettle();

      expect(find.text('Error interno'), findsOneWidget);
    });
  });
}
