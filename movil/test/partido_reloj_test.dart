import 'dart:io';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/partido/api.dart';
import 'package:areatecnica/features/partido/modelos.dart';
import 'package:areatecnica/features/partido/pagina.dart';
import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _estadoJson({
  int partidoId = 10,
  int parte = 1,
  int minuto = 12,
  int segundo = 34,
  bool enCurso = true,
  int gf = 1,
  int gc = 0,
}) =>
    {
      'partido_id': partidoId,
      'parte': parte,
      'minuto': minuto,
      'segundo': segundo,
      'en_curso': enCurso,
      'goles_favor': gf,
      'goles_contra': gc,
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

Map<String, dynamic> _partidoAgendaJson(
  int id,
  String rival,
  String estado,
  String fechaUtc,
) =>
    {
      'id': id,
      'equipo_id': 1,
      'rival': rival,
      'es_local': true,
      'fecha_hora': fechaUtc,
      'sede': 'Estadio Tahuichi',
      'estado': estado,
      'ataca_hacia': 'DER',
      'goles_favor': 1,
      'goles_contra': 0,
    };

Future<EstadoGuardado?> _sinCacheEstado(int _) async => null;
Future<List<ResumenPartidoVivo>?> _sinCachePartidos() async => null;
Future<List<ResumenPartidoVivo>> _sinListaPartidos() async => const [];

Widget _app(Widget child) => MaterialApp(theme: temaSol, home: child);

Future<void> _pantallaAlta(WidgetTester tester) async {
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('T-071 · Lógica pura del cronómetro y fases', () {
    test('formatea MM:SS, 45:00 +MM:SS en 1.er tiempo y 90:00 +MM:SS en 2.º',
        () {
      expect(formatearCronometroPartido(0, 0), '00:00');
      expect(formatearCronometroPartido(754, 1), '12:34');
      expect(formatearCronometroPartido(2700, 1), '45:00');
      expect(formatearCronometroPartido(2705, 1), '45:00 +00:05');
      expect(formatearCronometroPartido(2835, 1), '45:00 +02:15');

      // En el 2.º tiempo, entre 45:00 y 90:00 es tiempo reglamentario normal
      expect(formatearCronometroPartido(2705, 2), '45:05');
      expect(formatearCronometroPartido(5400, 2), '90:00');
      expect(formatearCronometroPartido(5401, 2), '90:00 +00:01');
      expect(formatearCronometroPartido(5590, 2), '90:00 +03:10');
    });

    test('calcularSegundosActuales avanza si enCurso=true y congela si false',
        () {
      expect(calcularSegundosActuales(null, 5000), 0);

      const corriendo = AnclaReloj(
        partidoId: 10,
        parte: 1,
        enCurso: true,
        baseSegundos: 600,
        marcaMonotonicaMs: 1000,
      );
      expect(calcularSegundosActuales(corriendo, 1000), 600);
      expect(calcularSegundosActuales(corriendo, 1999), 600);
      expect(calcularSegundosActuales(corriendo, 2000), 601);
      expect(calcularSegundosActuales(corriendo, 6500), 605);

      const pausado = AnclaReloj(
        partidoId: 10,
        parte: 1,
        enCurso: false,
        baseSegundos: 2700,
        marcaMonotonicaMs: 1000,
      );
      expect(calcularSegundosActuales(pausado, 99000), 2700);
    });

    test('reconciliarAnclaReloj no retrocede el segundero por truncamiento (1 s)',
        () {
      final inicial = EstadoEnVivo.fromJson(
        _estadoJson(parte: 1, minuto: 10, segundo: 0, enCurso: true),
      );
      final ancla0 = reconciliarAnclaReloj(null, inicial, 1000);
      expect(ancla0.baseSegundos, 600);
      expect(ancla0.marcaMonotonicaMs, 1000);

      // A los 1500 ms siguen siendo 600 s; si el servidor responde 10:00,
      // conserva la misma marcaMonotonicaMs (1000) para no perder los 500 ms.
      final mismoSegundo = reconciliarAnclaReloj(ancla0, inicial, 1500);
      expect(identical(mismoSegundo, ancla0), isTrue);

      // A los 2100 ms el reloj local ya marcó 601 s (10:01), pero el servidor
      // todavía devuelve 10:00 (600 s) por truncamiento entero: no retrocede.
      final sinRetroceso = reconciliarAnclaReloj(ancla0, inicial, 2100);
      expect(sinRetroceso.baseSegundos, 601);
      expect(sinRetroceso.marcaMonotonicaMs, 2100);

      // Si la diferencia supera 1 s (p. ej. el servidor salta a 10:05 = 605 s),
      // re-ancla al valor del servidor.
      final adelantado = EstadoEnVivo.fromJson(
        _estadoJson(parte: 1, minuto: 10, segundo: 5, enCurso: true),
      );
      final reanclado = reconciliarAnclaReloj(sinRetroceso, adelantado, 2500);
      expect(reanclado.baseSegundos, 605);
      expect(reanclado.marcaMonotonicaMs, 2500);

      // Al pasar a entretiempo (enCurso = false), re-ancla de inmediato.
      final entretiempo = EstadoEnVivo.fromJson(
        _estadoJson(parte: 1, minuto: 45, segundo: 12, enCurso: false),
      );
      final anclaPausa = reconciliarAnclaReloj(reanclado, entretiempo, 3000);
      expect(anclaPausa.enCurso, isFalse);
      expect(anclaPausa.baseSegundos, 2712);
    });

    test('determinarFasePartido distingue cada fase del encuentro', () {
      expect(determinarFasePartido(null), FasePartido.noIniciado);
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 0, enCurso: false)),
        ),
        FasePartido.noIniciado,
      );
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 1, enCurso: true)),
        ),
        FasePartido.primerTiempo,
      );
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 1, enCurso: false)),
        ),
        FasePartido.entretiempo,
      );
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 2, enCurso: true)),
        ),
        FasePartido.segundoTiempo,
      );
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 2, enCurso: false)),
        ),
        FasePartido.finalizado,
      );
      expect(
        determinarFasePartido(
          EstadoEnVivo.fromJson(_estadoJson(parte: 1, enCurso: true)),
          estadoPartido: 'CANCELADO',
        ),
        FasePartido.cancelado,
      );
    });

    test('ordenarPartidosParaVivo prioriza EN_CURSO y luego PROGRAMADO', () {
      final lista = [
        ResumenPartidoVivo.fromJson(
          _partidoAgendaJson(1, 'Bolívar', 'FINALIZADO', '2026-11-01T18:00:00Z'),
        ),
        ResumenPartidoVivo.fromJson(
          _partidoAgendaJson(2, 'Oriente', 'PROGRAMADO', '2026-11-12T20:00:00Z'),
        ),
        ResumenPartidoVivo.fromJson(
          _partidoAgendaJson(
            3,
            'Always Ready',
            'EN_CURSO',
            '2026-11-09T20:00:00Z',
          ),
        ),
      ];
      final ordenados = ordenarPartidosParaVivo(lista);
      expect(ordenados.map((p) => p.id).toList(), [3, 2, 1]);
    });

    test('el estado descargado se guarda en caché y se borra al cerrar sesión',
        () async {
      await Almacenamiento.guardarSesion('token-a', 'token-r');
      await Almacenamiento.guardarCache('partido.estado.10', {
        'guardado': '2026-11-09T20:15:00Z',
        'estado': _estadoJson(partidoId: 10, minuto: 23, segundo: 45),
      });

      final enCache = await estadoPartidoEnCache(10);
      expect(enCache?.estado.minuto, 23);
      expect(enCache?.estado.segundo, 45);

      await Almacenamiento.borrarToken();
      expect(await estadoPartidoEnCache(10), isNull);
    });
  });

  group('T-071 · Widget PartidoPagina en móvil', () {
    testWidgets(
      'muestra el cronómetro, avanza con el reloj monótono y reconcilia cada 5 s',
      (tester) async {
        await _pantallaAlta(tester);
        var relojMs = 1000;
        var consultas = 0;

        Future<EstadoEnVivo> obtener(int id) async {
          consultas++;
          // En la 1.ª consulta va en 12:34; a los 5 s (2.ª consulta) va en 12:39.
          return EstadoEnVivo.fromJson(
            _estadoJson(
              partidoId: id,
              parte: 1,
              minuto: 12,
              segundo: consultas == 1 ? 34 : 39,
              enCurso: true,
              gf: 2,
              gc: 1,
            ),
          );
        }

        await tester.pumpWidget(
          _app(
            PartidoPagina(
              partidoId: 10,
              obtenerEstado: obtener,
              enCache: _sinCacheEstado,
              listarPartidos: _sinListaPartidos,
              partidosEnCache: _sinCachePartidos,
              ahoraMonotonoMs: () => relojMs,
            ),
          ),
        );
        await tester.pump();

        expect(find.byKey(const Key('cronometro-texto')), findsOneWidget);
        expect(find.text('12:34'), findsOneWidget);
        expect(find.text('1.ER TIEMPO EN CURSO'), findsOneWidget);
        expect(find.byKey(const Key('goles-favor')), findsOneWidget);
        expect(find.text('2'), findsOneWidget);
        expect(find.text('1'), findsOneWidget);
        expect(consultas, 1);

        // Avanzamos 3 segundos en el reloj monótono sin llamadas de red
        relojMs += 3000;
        await tester.pump(const Duration(seconds: 1));
        expect(find.text('12:37'), findsOneWidget);

        // Al cumplirse los 5 s del sondeo periódico se consulta de nuevo
        relojMs += 2000;
        await tester.pump(const Duration(seconds: 4));
        await tester.pump();
        expect(consultas, 2);
        expect(find.text('12:39'), findsOneWidget);
      },
    );

    testWidgets(
      'muestra ENTRETIEMPO y congela el cronómetro cuando parte=1 y en_curso=false',
      (tester) async {
        await _pantallaAlta(tester);
        var relojMs = 5000;

        Future<EstadoEnVivo> obtener(int id) async => EstadoEnVivo.fromJson(
              _estadoJson(
                partidoId: id,
                parte: 1,
                minuto: 45,
                segundo: 0,
                enCurso: false,
              ),
            );

        await tester.pumpWidget(
          _app(
            PartidoPagina(
              partidoId: 10,
              obtenerEstado: obtener,
              enCache: _sinCacheEstado,
              listarPartidos: _sinListaPartidos,
              partidosEnCache: _sinCachePartidos,
              ahoraMonotonoMs: () => relojMs,
            ),
          ),
        );
        await tester.pump();

        expect(find.text('ENTRETIEMPO'), findsOneWidget);
        expect(
          find.textContaining('ENTRETIEMPO: cronómetro en pausa'),
          findsOneWidget,
        );
        expect(find.text('45:00'), findsOneWidget);

        // Aunque pasen 10 s en el reloj monótono, sigue congelado en 45:00
        relojMs += 10000;
        await tester.pump(const Duration(seconds: 2));
        expect(find.text('45:00'), findsOneWidget);
      },
    );

    testWidgets(
      'al volver de segundo plano actualiza el reloj y consulta al servidor',
      (tester) async {
        await _pantallaAlta(tester);
        var relojMs = 1000;
        var consultas = 0;

        Future<EstadoEnVivo> obtener(int id) async {
          consultas++;
          return EstadoEnVivo.fromJson(
            _estadoJson(
              partidoId: id,
              parte: 2,
              minuto: consultas == 1 ? 50 : 51,
              segundo: 0,
              enCurso: true,
            ),
          );
        }

        await tester.pumpWidget(
          _app(
            PartidoPagina(
              partidoId: 10,
              obtenerEstado: obtener,
              enCache: _sinCacheEstado,
              listarPartidos: _sinListaPartidos,
              partidosEnCache: _sinCachePartidos,
              ahoraMonotonoMs: () => relojMs,
            ),
          ),
        );
        await tester.pump();
        expect(find.text('50:00'), findsOneWidget);
        expect(consultas, 1);

        // La app pasa a segundo plano durante 60 s
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        relojMs += 60000;

        // Al volver a primer plano (resumed), recalcula y lanza consulta inmediata
        tester.binding
            .handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await tester.pump();

        expect(consultas, 2);
        expect(find.text('51:00'), findsOneWidget);
      },
    );

    testWidgets(
      'sin conexión muestra el último estado en caché y ofrece Reintentar',
      (tester) async {
        await _pantallaAlta(tester);
        Future<EstadoEnVivo> sinRed(int _) =>
            throw const SocketException('sin red');
        Future<EstadoGuardado?> desdeCache(int id) async => EstadoGuardado(
              estado: EstadoEnVivo.fromJson(
                _estadoJson(
                  partidoId: id,
                  parte: 1,
                  minuto: 33,
                  segundo: 10,
                  enCurso: true,
                  gf: 3,
                  gc: 1,
                ),
              ),
              guardado: DateTime(2026, 11, 9, 16, 30),
            );

        await tester.pumpWidget(
          _app(
            PartidoPagina(
              partidoId: 10,
              obtenerEstado: sinRed,
              enCache: desdeCache,
              listarPartidos: _sinListaPartidos,
              partidosEnCache: _sinCachePartidos,
              ahoraMonotonoMs: () => 1000,
            ),
          ),
        );
        await tester.pump();

        expect(
          find.text('Sin conexión: se muestra el último estado guardado.'),
          findsOneWidget,
        );
        expect(find.text('33:10'), findsOneWidget);
        expect(find.widgetWithText(OutlinedButton, 'Reintentar'), findsOneWidget);
      },
    );

    testWidgets('muestra aviso claro cuando el partido devuelve 404',
        (tester) async {
      await _pantallaAlta(tester);
      Future<EstadoEnVivo> noExiste(int _) =>
          throw ErrorApi(404, 'Partido no encontrado');

      await tester.pumpWidget(
        _app(
          PartidoPagina(
            partidoId: 999,
            obtenerEstado: noExiste,
            enCache: _sinCacheEstado,
            listarPartidos: _sinListaPartidos,
            partidosEnCache: _sinCachePartidos,
            ahoraMonotonoMs: () => 1000,
          ),
        ),
      );
      await tester.pump();

      expect(find.text('Partido no encontrado.'), findsOneWidget);
      expect(find.widgetWithText(OutlinedButton, 'Reintentar'), findsOneWidget);
    });
  });
}
