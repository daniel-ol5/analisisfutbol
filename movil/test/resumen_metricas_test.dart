/// Resumen de métricas en móvil  —  CU-43 (T-081).
///
/// Criterio: la información esencial entra en una pantalla sin desplazamiento.
library;

import 'dart:async';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/analisis/modelos.dart';
import 'package:areatecnica/features/analisis/resumen_api.dart';
import 'package:areatecnica/features/analisis/resumen_estado.dart';
import 'package:areatecnica/features/analisis/resumen_modelos.dart';
import 'package:areatecnica/features/analisis/resumen_pagina.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

const _partidoId = 42;

Map<String, dynamic> _jugador(int id, String nombre, int dorsal, double m, int sprints) => {
      'jugador_id': id,
      'track_id': id + 100,
      'nombre': nombre,
      'dorsal': dorsal,
      'distancia_m': m,
      'velocidad_max_kmh': 28.4,
      'sprints': sprints,
      'minutos_jugados': 34,
    };

class ApiFalsa implements ResumenApi {
  ApiFalsa({this.estado = 'EN_CURSO'});

  final String estado;
  int llamadasMetricas = 0;
  double distanciaLocal = 12400;

  @override
  Future<PartidoInfo> partido(int partidoId) async => PartidoInfo.fromJson({
        'id': partidoId,
        'equipo_id': 1,
        // Nombre largo a propósito: no puede desbordar en 360 px.
        'rival': 'Club Atlético Deportivo Independiente del Valle',
        'es_local': true,
        'estado': estado,
        'goles_favor': 2,
        'goles_contra': 1,
        'minuto_actual': 34,
      });

  @override
  Future<MetricasPartido> metricas(int partidoId) async {
    llamadasMetricas++;
    return MetricasPartido.fromJson({
      'partido_id': partidoId,
      'acumulado_local': {'equipo': 'LOCAL', 'posesion_pct': 54, 'distancia_m': distanciaLocal},
      'acumulado_visitante': {'equipo': 'VISITANTE', 'posesion_pct': 38, 'distancia_m': 11900},
      'ultimos_5_min_local': {'equipo': 'LOCAL', 'posesion_pct': 60, 'distancia_m': 900},
      'ultimos_5_min_visitante': {'equipo': 'VISITANTE', 'posesion_pct': 30, 'distancia_m': 850},
      'posesion_disputa_pct': 8,
    });
  }

  @override
  Future<List<MetricaJugador>> jugadores(int partidoId, String equipo) async =>
      MetricaJugador.lista(equipo == 'LOCAL'
          ? [
              _jugador(1, 'Maximiliano Fernández Etcheverry', 10, 4210, 7),
              _jugador(2, 'Juan Pérez', 8, 3980, 5),
              _jugador(3, 'Ana Gómez', 4, 3500, 2),
              _jugador(4, 'Otro Cuarto', 5, 3000, 1),
            ]
          : [
              _jugador(11, 'Rival Uno', 9, 4100, 6),
              _jugador(12, 'Rival Dos', 7, 3900, 3),
              _jugador(13, 'Rival Tres', 11, 3700, 4),
            ]);

  @override
  Future<List<IntervaloMetricas>> intervalos(int partidoId) async => const [];
}

class FuenteFalsa extends ChangeNotifier implements FuenteVivo {
  final _mensajes = StreamController<Map<String, dynamic>>.broadcast();
  EstadoConexion _estado = EstadoConexion.conectado;
  int? conectadoA;

  @override
  EstadoConexion get estadoConexion => _estado;

  set estado(EstadoConexion nuevo) {
    _estado = nuevo;
    notifyListeners();
  }

  @override
  Stream<Map<String, dynamic>> get mensajes => _mensajes.stream;

  void emitir(Map<String, dynamic> mensaje) => _mensajes.add(mensaje);

  @override
  void conectar(int partidoId) => conectadoA = partidoId;

  @override
  void dispose() {
    _mensajes.close();
    super.dispose();
  }
}

final _hora = DateTime(2026, 11, 10, 15, 42, 10);

Future<FuenteFalsa?> _abrir(
  WidgetTester tester, {
  ApiFalsa? api,
  ThemeData? tema,
  List<FuenteFalsa>? creadas,
}) async {
  // Teléfono pequeño: 360 × 640 puntos lógicos.
  tester.view.physicalSize = const Size(360, 640);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  FuenteFalsa? fuente;
  await tester.pumpWidget(MaterialApp(
    theme: tema ?? temaSol,
    home: ResumenPagina(
      partidoId: _partidoId,
      api: api ?? ApiFalsa(),
      crearFuente: () {
        fuente = FuenteFalsa();
        creadas?.add(fuente!);
        return fuente!;
      },
      ahora: () => _hora,
    ),
  ));
  await tester.pumpAndSettle();
  return fuente;
}

/// El widget se ve completo dentro de la pantalla.
void _visible(WidgetTester tester, Finder finder) {
  expect(finder, findsOneWidget);
  final rect = tester.getRect(finder);
  const pantalla = Rect.fromLTWH(0, 0, 360, 640);
  expect(pantalla.contains(rect.topLeft) && pantalla.contains(rect.bottomRight - const Offset(0.01, 0.01)),
      isTrue, reason: '$finder fuera de la pantalla: $rect');
}

void _textoVisible(WidgetTester tester, String texto) =>
    _visible(tester, find.text(texto));

void main() {
  group('Criterio de T-081: todo en una pantalla de 360 × 640', () {
    for (final (nombre, tema) in [('Sol', temaSol), ('Claro', temaClaro), ('Oscuro', temaOscuro)]) {
      testWidgets('sin desplazamiento ni desbordes (tema $nombre)', (tester) async {
        await _abrir(tester, tema: tema);

        expect(tester.takeException(), isNull, reason: 'no debe haber desbordes');
        expect(
          find.descendant(of: find.byType(ResumenPagina), matching: find.byType(Scrollable)),
          findsNothing,
          reason: 'la pantalla no se desplaza',
        );

        // 1. Marcador y estado
        _visible(tester, find.byKey(const Key('resumen-marcador')));
        expect(find.textContaining('Nosotros 2 – 1 Club', findRichText: true), findsOneWidget);
        _visible(tester, find.byKey(const Key('resumen-estado')));
        // 2. Posesión acumulada y de los últimos 5 min
        _textoVisible(tester, '54%');
        _textoVisible(tester, '38%');
        _textoVisible(tester, 'Disputa 8%');
        _textoVisible(tester, 'Últimos 5 min: 60% · 10% · 30%');
        // 3. Distancia por equipo
        _textoVisible(tester, '12,4 km');
        _textoVisible(tester, '11,9 km');
        // 4. Top 3 de cada equipo, con sprints (el cuarto no aparece)
        _textoVisible(tester, '10 Fernández Etcheverry');
        _textoVisible(tester, '4,2 km · 7 spr');
        _textoVisible(tester, '4 Gómez');
        _textoVisible(tester, '11 Tres');
        _textoVisible(tester, '3,7 km · 4 spr');
        expect(find.text('5 Cuarto'), findsNothing);
      });
    }

    testWidgets('ningún texto por debajo de 16 puntos', (tester) async {
      await _abrir(tester);
      final parrafos = tester.renderObjectList<RenderParagraph>(
        find.descendant(of: find.byType(ResumenPagina), matching: find.byType(RichText)),
      );
      for (final p in parrafos) {
        final estilo = p.text.style;
        if (estilo?.fontFamily == 'MaterialIcons') continue; // íconos
        expect(estilo?.fontSize ?? 0, greaterThanOrEqualTo(16),
            reason: '«${p.text.toPlainText()}» mide ${estilo?.fontSize}');
      }
    });
  });

  group('Actualización en vivo', () {
    testWidgets('el mensaje posesion actualiza la posesión', (tester) async {
      final fuente = await _abrir(tester);
      expect(fuente!.conectadoA, _partidoId);

      fuente.emitir({
        'tipo': 'posesion',
        'datos': {
          'partido_id': _partidoId,
          't': 2160.4,
          'acumulado': {'local_pct': 61.2, 'visitante_pct': 30.3, 'disputa_pct': 8.5},
          'intervalo': {
            'minuto_desde': 35, 'minuto_hasta': 40,
            'local_pct': 70.0, 'visitante_pct': 20.0, 'disputa_pct': 10.0,
          },
          'estado': 'LOCAL',
          'poseedor': {'equipo': 'LOCAL', 'track_id': 101},
        },
      });
      await tester.pumpAndSettle();

      expect(find.text('61%'), findsOneWidget);
      expect(find.text('30%'), findsOneWidget);
      expect(find.text('Disputa 9%'), findsOneWidget);
      expect(find.text('Min 35–40: 70% · 10% · 20%'), findsOneWidget);
      expect(find.text("EN VIVO 36'"), findsOneWidget);
      expect(find.text('54%'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('el mensaje metricas_jugadores actualiza el top 3 y la distancia',
        (tester) async {
      final api = ApiFalsa();
      final fuente = await _abrir(tester, api: api);
      final antes = api.llamadasMetricas;
      api.distanciaLocal = 13050;

      fuente!.emitir({
        'tipo': 'metricas_jugadores',
        'datos': {
          'partido_id': _partidoId,
          't': 2220.0,
          'local': [
            _jugador(2, 'Juan Pérez', 8, 4500, 9),
            _jugador(1, 'Maximiliano Fernández Etcheverry', 10, 4400, 7),
            _jugador(5, 'Nuevo Ingreso', 19, 1200, 1),
          ],
          'visitante': [_jugador(11, 'Rival Uno', 9, 4300, 6)],
        },
      });
      await tester.pumpAndSettle();

      expect(find.text('8 Pérez'), findsOneWidget);
      expect(find.text('4,5 km · 9 spr'), findsOneWidget);
      expect(find.text('19 Ingreso'), findsOneWidget);
      expect(find.text('4 Gómez'), findsNothing);
      expect(find.text('7 Dos'), findsNothing);
      // La distancia por equipo no viaja por el WebSocket: se pide por REST.
      expect(api.llamadasMetricas, antes + 1);
      expect(find.text('13,1 km'), findsOneWidget);
      // Y la posesión no se pisa con ese REST.
      expect(find.text('54%'), findsOneWidget);
    });

    test('un intervalo con el mismo minuto_desde reemplaza al anterior', () {
      final estado = ResumenEstado(partidoId: _partidoId, api: ApiFalsa());
      Map<String, dynamic> intervalo(int desde, double local) => {
            'tipo': 'intervalo',
            'datos': {
              'minuto_desde': desde,
              'minuto_hasta': desde + 5,
              'local': {'equipo': 'LOCAL', 'posesion_pct': local},
              'visitante': {'equipo': 'VISITANTE', 'posesion_pct': 90 - local},
              'posesion_disputa_pct': 10,
            },
          };

      estado.procesarMensaje(intervalo(5, 40));
      estado.procesarMensaje(intervalo(0, 50));
      estado.procesarMensaje(intervalo(5, 45)); // corregido (sprint tardío)

      expect(estado.intervalos.map((i) => i.minutoDesde), [0, 5]);
      expect(estado.intervalos[1].posesion.local, 45);
      expect(estado.intervalos[1].posesion.visitante, 45);
      estado.dispose();
    });
  });

  group('Sin conexión y partido finalizado', () {
    testWidgets('sin conexión: quedan los últimos datos con su hora y el indicador',
        (tester) async {
      final fuente = await _abrir(tester);
      expect(find.byKey(const Key('resumen-sin-conexion')), findsNothing);

      fuente!.estado = EstadoConexion.reconectando;
      await tester.pumpAndSettle();

      _visible(tester, find.byKey(const Key('resumen-sin-conexion')));
      expect(find.text('Sin conexión'), findsOneWidget);
      expect(find.text('Datos de las 15:42:10'), findsOneWidget);
      expect(find.text('SIN CONEXIÓN'), findsOneWidget);
      // Los últimos datos siguen a la vista.
      _textoVisible(tester, '54%');
      _textoVisible(tester, '12,4 km');
      _textoVisible(tester, '4 Gómez');
      expect(tester.takeException(), isNull);

      // Al reconectar (lo hace sola el servicio), el indicador desaparece.
      fuente.estado = EstadoConexion.conectado;
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('resumen-sin-conexion')), findsNothing);
    });

    testWidgets('partido finalizado: datos finales por REST, sin WebSocket', (tester) async {
      final creadas = <FuenteFalsa>[];
      final fuente =
          await _abrir(tester, api: ApiFalsa(estado: 'FINALIZADO'), creadas: creadas);

      expect(fuente, isNull);
      expect(creadas, isEmpty);
      expect(find.text('FINAL'), findsOneWidget);
      _textoVisible(tester, '54%');
      _textoVisible(tester, '12,4 km');
      expect(find.byKey(const Key('resumen-sin-conexion')), findsNothing);
    });
  });
}
