import 'dart:async';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/deportivo/agenda/modelos.dart';
import 'package:areatecnica/features/deportivo/alineacion/modelos.dart';
import 'package:areatecnica/features/partido/modelos.dart';
import 'package:areatecnica/features/partido/pagina.dart';
import 'package:areatecnica/features/partido/cola_eventos.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Partido _partido({String estado = 'EN_CURSO'}) => Partido(
  id: 7,
  equipoId: 3,
  rival: 'Club Rival',
  esLocal: true,
  fechaHora: DateTime(2026, 11, 8, 16),
  sede: 'Cancha principal',
  estado: estado,
);

JugadorAlineado _jugador(int id, int dorsal, bool titular) => JugadorAlineado(
  jugadorId: id,
  esTitular: titular,
  esCapitan: dorsal == 9,
  posX: 50,
  posY: 50,
  nombre: 'Jugador',
  apellido: 'N$dorsal',
  dorsal: dorsal,
  posicion: dorsal == 1 ? 'ARQ' : 'DEL',
);

final _alineacion = Alineacion(
  partidoId: 7,
  formacion: '4-4-2',
  jugadores: [
    _jugador(101, 1, true),
    _jugador(109, 9, true),
    _jugador(112, 12, false),
    _jugador(119, 19, false),
  ],
);

Future<List<Partido>> _activos() async => [_partido()];
Future<Alineacion> _formacion(int _) async => _alineacion;
Future<void> _sinDeshacer(int _) async {}
Future<void> _sinDescartar(String _) async {}
Future<int> _sinPendientes(int _) async => 0;
Future<ResultadoSincronizacion> _sinSincronizar(int _) async =>
    const ResultadoSincronizacion(confirmados: 0, pendientes: 0);

EventoManual _respuesta(
  int id,
  EventoCrear solicitud, {
  bool segundaAmarilla = false,
}) => EventoManual(
  id: id,
  partidoId: 7,
  tipo: solicitud.tipo,
  equipo: solicitud.equipo,
  jugadorId: solicitud.jugadorId,
  jugadorEntraId: solicitud.jugadorEntraId,
  minuto: 23,
  convertidaEnRoja: segundaAmarilla,
  creadoEn: DateTime(2026, 11, 8, 16, 23),
);

Future<void> _pantallaAlta(WidgetTester tester) async {
  tester.view.physicalSize = const Size(900, 2600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

Widget _app({
  ObtenerPartidos obtenerPartidos = _activos,
  ObtenerAlineacion obtenerAlineacion = _formacion,
  required RegistrarEvento registrar,
  DeshacerEvento deshacer = _sinDeshacer,
  ContarPendientes contarPendientes = _sinPendientes,
  SincronizarPendientes sincronizarPendientes = _sinSincronizar,
  DescartarPendiente descartarPendiente = _sinDescartar,
}) => MaterialApp(
  theme: temaSol,
  home: PartidoPagina(
    obtenerPartidos: obtenerPartidos,
    obtenerAlineacion: obtenerAlineacion,
    registrar: registrar,
    deshacer: deshacer,
    contarPendientes: contarPendientes,
    sincronizarPendientes: sincronizarPendientes,
    descartarPendiente: descartarPendiente,
  ),
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('modelo de respuesta interpreta evento y segunda amarilla', () {
    final evento = EventoManual.fromJson({
      'id': 4,
      'partido_id': 7,
      'tipo': 'AMARILLA',
      'equipo': 'LOCAL',
      'jugador_id': 109,
      'jugador_entra_id': null,
      'minuto': 31,
      'convertida_en_roja': true,
      'creado_en': '2026-11-08T16:31:00Z',
    });
    expect(evento.tipo, TipoEvento.amarilla);
    expect(evento.convertidaEnRoja, isTrue);
    expect(evento.creadoEn.isUtc, isFalse);
  });

  testWidgets('muestra el partido activo, marcador y botonera', (tester) async {
    await _pantallaAlta(tester);
    Future<EventoManual> registrar(int _, EventoCrear evento) async =>
        _respuesta(1, evento);

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('partido-activo')), findsOneWidget);
    expect(find.text('vs Club Rival'), findsOneWidget);
    expect(find.byKey(const Key('marcador')), findsOneWidget);
    expect(find.byKey(const Key('evento-GOL')), findsOneWidget);
    expect(find.byKey(const Key('evento-AMARILLA')), findsOneWidget);
    expect(find.byKey(const Key('evento-ROJA')), findsOneWidget);
    expect(find.byKey(const Key('cambio-109')), findsOneWidget);
  });

  testWidgets('gol se registra en dos toques y menos de cinco segundos', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    final enviados = <EventoCrear>[];
    Future<EventoManual> registrar(int partidoId, EventoCrear evento) async {
      expect(partidoId, 7);
      enviados.add(evento);
      return _respuesta(1, evento);
    }

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();
    final reloj = Stopwatch()..start();

    // Condición reproducible: API inmediata, pantalla ya cargada y dos taps.
    await tester.tap(find.byKey(const Key('evento-GOL'))); // toque 1
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109'))); // toque 2
    await tester.pumpAndSettle();
    reloj.stop();

    expect(enviados, hasLength(1));
    expect(enviados.single.tipo, TipoEvento.gol);
    expect(enviados.single.jugadorId, 109);
    expect(reloj.elapsed, lessThan(const Duration(seconds: 5)));
    expect(find.text('1-0'), findsOneWidget);
    expect(find.textContaining('Gol registrado'), findsOneWidget);
  });

  for (final tipo in [TipoEvento.amarilla, TipoEvento.roja]) {
    testWidgets('${tipo.etiqueta} registra el jugador elegido', (tester) async {
      await _pantallaAlta(tester);
      final enviados = <EventoCrear>[];
      Future<EventoManual> registrar(int _, EventoCrear evento) async {
        enviados.add(evento);
        return _respuesta(
          2,
          evento,
          segundaAmarilla: tipo == TipoEvento.amarilla,
        );
      }

      await tester.pumpWidget(_app(registrar: registrar));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key('evento-${tipo.codigo}')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('jugador-109')));
      await tester.pumpAndSettle();

      expect(enviados.single.tipo, tipo);
      expect(enviados.single.jugadorId, 109);
      if (tipo == TipoEvento.amarilla) {
        expect(find.textContaining('convertida en roja'), findsOneWidget);
      }
    });
  }

  testWidgets('sustitución registra saliente y entrante en dos toques', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    final enviados = <EventoCrear>[];
    Future<EventoManual> registrar(int _, EventoCrear evento) async {
      enviados.add(evento);
      return _respuesta(3, evento);
    }

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('cambio-109'))); // toque 1
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('suplente-119'))); // toque 2
    await tester.pumpAndSettle();

    expect(enviados, hasLength(1));
    expect(enviados.single.tipo, TipoEvento.sustitucion);
    expect(enviados.single.jugadorId, 109);
    expect(enviados.single.jugadorEntraId, 119);
    expect(find.byKey(const Key('jugador-119')), findsOneWidget);
    expect(find.byKey(const Key('jugador-109')), findsNothing);
  });

  testWidgets('el rival se registra sin jugador', (tester) async {
    await _pantallaAlta(tester);
    final enviados = <EventoCrear>[];
    Future<EventoManual> registrar(int _, EventoCrear evento) async {
      enviados.add(evento);
      return _respuesta(4, evento);
    }

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Visita · Club Rival'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('evento-rival-GOL')));
    await tester.pumpAndSettle();

    expect(enviados.single.equipo, 'VISITANTE');
    expect(enviados.single.jugadorId, isNull);
    expect(find.text('0-1'), findsOneWidget);
  });

  testWidgets('confirmación permite deshacer inmediatamente', (tester) async {
    await _pantallaAlta(tester);
    int? deshecho;
    Future<EventoManual> registrar(int _, EventoCrear evento) async =>
        _respuesta(8, evento);
    Future<void> deshacer(int id) async => deshecho = id;

    await tester.pumpWidget(_app(registrar: registrar, deshacer: deshacer));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('evento-GOL')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Deshacer'));
    await tester.pumpAndSettle();

    expect(deshecho, 8);
    expect(find.text('0-0'), findsOneWidget);
    expect(find.text('Evento deshecho.'), findsOneWidget);
  });

  testWidgets('bloquea toques repetidos mientras el evento está enviándose', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    final pendiente = Completer<EventoManual>();
    var pedidos = 0;
    Future<EventoManual> registrar(int _, EventoCrear evento) {
      pedidos++;
      return pendiente.future;
    }

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('evento-GOL')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109')), warnIfMissed: false);

    expect(pedidos, 1);
    pendiente.complete(
      _respuesta(
        9,
        const EventoCrear(
          tipo: TipoEvento.gol,
          equipo: 'LOCAL',
          jugadorId: 109,
        ),
      ),
    );
    await tester.pumpAndSettle();
  });

  testWidgets('muestra el error del backend y permite reintentar', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    Future<EventoManual> registrar(int _, EventoCrear evento) =>
        throw ErrorApi(409, 'El partido ya finalizó');

    await tester.pumpWidget(_app(registrar: registrar));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('evento-GOL')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109')));
    await tester.pumpAndSettle();

    expect(find.text('El partido ya finalizó'), findsOneWidget);
  });

  testWidgets('muestra y permite descartar un evento guardado sin conexión', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    var pendientes = 0;
    String? descartado;
    Future<EventoManual> registrar(int partidoId, EventoCrear evento) async {
      final identificado = EventoCrear(
        uuid: 'uuid-offline',
        capturadoEn: DateTime.utc(2026, 11, 8, 16, 23),
        tipo: evento.tipo,
        equipo: evento.equipo,
        jugadorId: evento.jugadorId,
      );
      pendientes = 1;
      return EventoManual.pendiente(
        partidoId: partidoId,
        evento: identificado,
        minutoEstimado: 23,
      );
    }

    await tester.pumpWidget(
      _app(
        registrar: registrar,
        contarPendientes: (_) async => pendientes,
        descartarPendiente: (uuid) async {
          descartado = uuid;
          pendientes = 0;
        },
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('evento-GOL')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('jugador-109')));
    await tester.pumpAndSettle();

    expect(find.text('Pendientes: 1'), findsOneWidget);
    expect(find.textContaining('guardado sin conexión'), findsOneWidget);
    await tester.tap(find.text('Deshacer'));
    await tester.pumpAndSettle();

    expect(descartado, 'uuid-offline');
    expect(find.text('Pendientes: 0'), findsOneWidget);
  });

  testWidgets('el contador permite sincronizar manualmente la cola', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    var pendientes = 2;
    var sincronizaciones = 0;

    await tester.pumpWidget(
      _app(
        registrar: (partidoId, evento) async => _respuesta(1, evento),
        contarPendientes: (_) async => pendientes,
        sincronizarPendientes: (_) async {
          sincronizaciones++;
          pendientes = 0;
          return const ResultadoSincronizacion(confirmados: 2, pendientes: 0);
        },
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pendientes: 2'), findsOneWidget);

    await tester.tap(find.byKey(const Key('eventos-pendientes')));
    await tester.pumpAndSettle();

    expect(sincronizaciones, 1);
    expect(find.text('Pendientes: 0'), findsOneWidget);
    expect(find.textContaining('2 evento(s) sincronizado(s)'), findsOneWidget);
  });

  testWidgets('la cola se sincroniza automáticamente al recuperar conexión', (
    tester,
  ) async {
    await _pantallaAlta(tester);
    var pendientes = 1;
    var sincronizaciones = 0;

    await tester.pumpWidget(
      _app(
        registrar: (partidoId, evento) async => _respuesta(1, evento),
        contarPendientes: (_) async => pendientes,
        sincronizarPendientes: (_) async {
          sincronizaciones++;
          pendientes = 0;
          return const ResultadoSincronizacion(confirmados: 1, pendientes: 0);
        },
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pendientes: 1'), findsOneWidget);

    await tester.pump(const Duration(seconds: 15));
    await tester.pumpAndSettle();

    expect(sincronizaciones, 1);
    expect(find.text('Pendientes: 0'), findsOneWidget);
  });

  testWidgets('sin partido activo no muestra una botonera utilizable', (
    tester,
  ) async {
    Future<List<Partido>> programados() async => [
      _partido(estado: 'PROGRAMADO'),
    ];
    Future<EventoManual> registrar(int _, EventoCrear evento) async =>
        _respuesta(1, evento);

    await tester.pumpWidget(
      _app(obtenerPartidos: programados, registrar: registrar),
    );
    await tester.pumpAndSettle();

    expect(find.text('No hay un partido en curso.'), findsOneWidget);
    expect(find.byKey(const Key('evento-GOL')), findsNothing);
  });
}
