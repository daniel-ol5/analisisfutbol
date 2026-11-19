/// Alertas de fatiga y riesgo de expulsión en el móvil  —  CU-52 (HU-46, T-095).
///
/// HU-46, criterio 3: "Notificación destacada en la barra superior móvil".
/// Los criterios de cuándo se genera cada alerta (120 %, 25 %, 15 minutos,
/// fase de fricción) se prueban en el backend: la app muestra lo que recibe.
library;

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/asistencia/alertas_estado.dart';
import 'package:areatecnica/features/asistencia/alertas_modelos.dart';
import 'package:areatecnica/features/asistencia/alertas_pagina.dart';
import 'package:areatecnica/features/asistencia/alertas_widgets.dart';
import 'package:areatecnica/features/partido/modelos.dart';
import 'package:areatecnica/features/partido/pagina.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _json(String tipo, int jugador, {String prioridad = 'MEDIA'}) => {
      'tipo': tipo,
      'jugador_id': jugador,
      'nombre': 'Jugador$jugador',
      'dorsal': jugador,
      'minuto': 70,
      'mensaje': '$tipo de #$jugador',
      'justificacion': 'Porque sí ($jugador).',
      'prioridad': prioridad,
      'datos_soporte': [
        {'metrica': 'ritmo_m_min', 'valor': 150.0, 'umbral': 144.0},
      ],
    };

Alerta _alerta(String tipo, int jugador, {String prioridad = 'MEDIA'}) =>
    Alerta.fromJson(_json(tipo, jugador, prioridad: prioridad));

final _expulsion = _alerta('RIESGO_EXPULSION', 2, prioridad: 'ALTA');
final _fatiga = _alerta('FATIGA', 8);

/// Devuelve, en cada consulta, la siguiente respuesta de la lista (la última se repite).
/// Un `null` simula una consulta que falla (red caída).
class _Respuestas {
  _Respuestas(this.respuestas);
  final List<List<Alerta>?> respuestas;
  int consultas = 0;

  Future<List<Alerta>> call(int partidoId) async {
    final i = consultas < respuestas.length ? consultas : respuestas.length - 1;
    consultas++;
    final r = respuestas[i];
    if (r == null) throw Exception('sin red');
    return r;
  }
}

Widget _app(Widget child) => MaterialApp(theme: temaSol, home: child);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('Modelo', () {
    test('lee el contrato del backend', () {
      final a = _alerta('RIESGO_EXPULSION', 2, prioridad: 'ALTA');
      expect(a.tipo, TipoAlerta.riesgoExpulsion);
      expect(a.prioridad, PrioridadAlerta.alta);
      expect(a.quien, '#2 Jugador2');
      expect(a.clave, 'RIESGO_EXPULSION-2');
      expect(a.datosSoporte.single.umbral, 144.0);
    });

    test('ignora lo que no tenga la forma esperada', () {
      expect(Alerta.lista([_json('FATIGA', 1), {'tipo': 'FATIGA'}, 'basura']), hasLength(1));
      expect(Alerta.lista({'detail': 'error'}), isEmpty);
    });
  });

  group('Estado', () {
    test('marca como nuevas solo las que aparecen por primera vez', () async {
      final api = _Respuestas([
        [_expulsion],
        [_expulsion, _fatiga],
      ]);
      final estado = AlertasEstado(partidoId: 1, obtener: api.call);
      await estado.consultar();
      expect(estado.nuevas, {'RIESGO_EXPULSION-2'});
      await estado.consultar();
      expect(estado.alertas.map((a) => a.clave), ['RIESGO_EXPULSION-2', 'FATIGA-8']);
      expect(estado.nuevas, {'FATIGA-8'});
      estado.dispose();
    });

    test('"Entendido" la oculta; si la situación termina y vuelve, se avisa otra vez', () async {
      final api = _Respuestas([
        [_fatiga],
        [_fatiga],
        [],
        [_fatiga],
      ]);
      final estado = AlertasEstado(partidoId: 1, obtener: api.call);
      await estado.consultar();
      estado.descartar(_fatiga);
      expect(estado.alertas, isEmpty);
      await estado.consultar(); // sigue la misma situación: sigue oculta
      expect(estado.alertas, isEmpty);
      await estado.consultar(); // se terminó
      await estado.consultar(); // volvió: es una situación nueva
      expect(estado.alertas.single.clave, 'FATIGA-8');
      estado.dispose();
    });

    test('con la red caída conserva las últimas alertas y avisa (T-097)', () async {
      final api = _Respuestas([
        [_expulsion],
        null,
        [],
      ]);
      final estado = AlertasEstado(partidoId: 1, obtener: api.call);
      await estado.consultar();
      await estado.consultar();
      expect(estado.sinConexion, isTrue);
      expect(estado.alertas, [_expulsion]);
      await estado.consultar();
      expect(estado.sinConexion, isFalse);
      expect(estado.alertas, isEmpty);
      estado.dispose();
    });
  });

  group('Barra superior (HU-46, criterio 3)', () {
    testWidgets('muestra la más urgente, cuántas más hay, y se actualiza sola', (tester) async {
      final api = _Respuestas([
        [],
        [_expulsion, _fatiga],
      ]);
      var abiertas = 0;
      await tester.pumpWidget(_app(Scaffold(
        body: BarraAlertas(
          partidoId: 1,
          obtener: api.call,
          intervalo: const Duration(seconds: 15),
          alVer: () => abiertas++,
        ),
      )));
      await tester.pump();
      expect(find.byKey(const Key('barra-alertas')), findsNothing); // sin alertas no ocupa lugar

      await tester.pump(const Duration(seconds: 15));
      expect(api.consultas, 2);
      expect(find.text('RIESGO_EXPULSION de #2'), findsOneWidget);
      expect(find.text('+1 alerta más'), findsOneWidget);
      final barra = tester.widget<Material>(find.byKey(const Key('barra-alertas')));
      expect(barra.color, rojo);

      await tester.tap(find.byKey(const Key('barra-alertas')));
      expect(abiertas, 1);
    });

    testWidgets('al salir de la pantalla deja de consultar', (tester) async {
      final api = _Respuestas([
        [_fatiga],
      ]);
      await tester.pumpWidget(_app(Scaffold(
        body: BarraAlertas(partidoId: 1, obtener: api.call, alVer: () {}),
      )));
      await tester.pump();
      await tester.pumpWidget(_app(const SizedBox()));
      await tester.pump(const Duration(minutes: 1));
      expect(api.consultas, 1);
    });
  });

  group('Pantalla de alertas', () {
    testWidgets('lista las alertas con su justificación y permite marcarlas', (tester) async {
      final api = _Respuestas([
        [_expulsion, _fatiga],
      ]);
      await tester.pumpWidget(_app(AlertasPagina(partidoId: 1, obtener: api.call)));
      await tester.pump();
      expect(find.text('Riesgo de expulsión'), findsOneWidget);
      expect(find.text('Fatiga'), findsOneWidget);
      expect(find.text('Porque sí (8).'), findsOneWidget);

      await tester.tap(find.byKey(const Key('entendido-FATIGA-8')));
      await tester.pump();
      expect(find.byKey(const Key('alerta-FATIGA-8')), findsNothing);
      expect(find.byKey(const Key('alerta-RIESGO_EXPULSION-2')), findsOneWidget);
    });

    testWidgets('sin alertas lo dice; sin red lo avisa', (tester) async {
      final api = _Respuestas([
        [],
        null,
      ]);
      await tester.pumpWidget(_app(AlertasPagina(
        partidoId: 1,
        obtener: api.call,
        intervalo: const Duration(seconds: 15),
      )));
      await tester.pump();
      expect(find.textContaining('Sin alertas por ahora'), findsOneWidget);
      await tester.pump(const Duration(seconds: 15));
      expect(find.textContaining('Sin conexión'), findsOneWidget);
    });
  });

  group('Pantalla del partido', () {
    Map<String, dynamic> estadoJson({required bool enCurso}) => {
          'partido_id': 10,
          'parte': 2,
          'minuto': 70,
          'segundo': 0,
          'en_curso': enCurso,
          'goles_favor': 0,
          'goles_contra': 0,
          'posesion_local_pct': null,
          'calidad': {
            'worker_conectado': true,
            'fps': 5.0,
            'jugadores_detectados': 20,
            'balon_visible': true,
            'retraso_s': 0.3,
            'degradado': false,
            'motivo': null,
          },
        };

    Widget pagina({required bool enCurso}) => _app(PartidoPagina(
          partidoId: 10,
          obtenerEstado: (_) async => EstadoEnVivo.fromJson(estadoJson(enCurso: enCurso)),
          enCache: (_) async => null,
          listarPartidos: () async => const [],
          partidosEnCache: () async => null,
          barraSuperior: (id) => Text('barra del partido $id', key: const Key('barra-inyectada')),
        ));

    testWidgets('con el partido en curso muestra la barra que inyecta el router', (tester) async {
      await tester.pumpWidget(pagina(enCurso: true));
      await tester.pump();
      expect(find.text('barra del partido 10'), findsOneWidget);
    });

    testWidgets('con el reloj detenido no la muestra', (tester) async {
      await tester.pumpWidget(pagina(enCurso: false));
      await tester.pump();
      expect(find.byKey(const Key('barra-inyectada')), findsNothing);
    });
  });
}
