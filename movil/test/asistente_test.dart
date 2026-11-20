/// Asistente de uso en el móvil: progreso, chat y falta de conexión.
library;

import 'dart:async';
import 'dart:io';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/asistente/asistente_api.dart';
import 'package:areatecnica/features/asistente/asistente_estado.dart';
import 'package:areatecnica/features/asistente/asistente_modelos.dart';
import 'package:areatecnica/features/asistente/asistente_pagina.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

final _progresoBase = Progreso.fromJson({
  'plataforma': 'movil',
  'partido_id': 42,
  'asistente_activo': true,
  'pasos': [
    {'clave': 'club', 'titulo': 'Registrar el club', 'estado': 'hecho', 'ruta': null,
      'solo_web': false, 'disponible': true, 'tu_rol_puede': true, 'nota': null},
    {'clave': 'equipo', 'titulo': 'Crear el equipo y sus colores', 'estado': 'hecho',
      'ruta': '/deportivo', 'solo_web': false, 'disponible': true, 'tu_rol_puede': true,
      'nota': null},
    {'clave': 'calibracion', 'titulo': 'Calibrar la cámara', 'estado': 'pendiente',
      'ruta': null, 'solo_web': true, 'disponible': true, 'tu_rol_puede': true,
      'nota': 'Este paso solo se puede hacer en la web.'},
    {'clave': 'informe', 'titulo': 'Informe del partido', 'estado': 'pendiente', 'ruta': null,
      'solo_web': false, 'disponible': false, 'tu_rol_puede': false, 'nota': null},
  ],
  'siguiente': {'clave': 'calibracion', 'titulo': 'Calibrar la cámara', 'estado': 'pendiente',
    'ruta': null, 'solo_web': true, 'disponible': true, 'tu_rol_puede': true,
    'nota': 'Este paso solo se puede hacer en la web.'},
});

class ApiFalsa implements AsistenteApi {
  ApiFalsa({this.progresoFalla, this.respuesta, this.preguntaFalla, Progreso? progreso})
      : _progreso = progreso;

  Object? progresoFalla;
  Respuesta? respuesta;
  Object? preguntaFalla;
  final Progreso? _progreso;
  final preguntas = <(String, String, int)>[];
  Completer<void>? demora;

  @override
  Future<Progreso> progreso() async {
    if (progresoFalla != null) throw progresoFalla!;
    return _progreso ?? _progresoBase;
  }

  @override
  Future<Respuesta> preguntar(String pregunta,
      {required String pantalla, required List<MensajeChat> historial}) async {
    preguntas.add((pregunta, pantalla, historial.length));
    if (demora != null) await demora!.future;
    if (preguntaFalla != null) throw preguntaFalla!;
    return respuesta ?? const Respuesta('Sin respuesta', []);
  }
}

Future<GoRouter> _montar(WidgetTester tester, ApiFalsa api, {ThemeData? tema}) async {
  tester.view.physicalSize = const Size(400, 860);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    initialLocation: '/asistente',
    routes: [
      GoRoute(path: '/', builder: (_, _) => const Scaffold(body: Text('Inicio'))),
      GoRoute(
        path: '/asistente',
        builder: (_, _) => AsistentePagina(pantalla: 'partido_en_vivo', api: api),
      ),
      GoRoute(
        path: '/partidos/:id/resumen',
        builder: (_, e) => Scaffold(body: Text('Resumen ${e.pathParameters['id']}')),
      ),
    ],
  );
  await tester.pumpWidget(MaterialApp.router(theme: tema ?? temaClaro, routerConfig: router));
  await tester.pumpAndSettle();
  return router;
}

void main() {
  tearDown(AsistenteEstado.borrarHistorial);

  testWidgets('muestra el progreso y avisa que el siguiente paso es solo en la web',
      (tester) async {
    await _montar(tester, ApiFalsa(), tema: temaSol);
    expect(find.text('Tu progreso'), findsOneWidget);
    expect(find.text('2 de 3'), findsOneWidget);
    expect(find.text('Siguiente paso: Calibrar la cámara'), findsOneWidget);
    expect(find.text('Este paso solo se puede hacer en la web.'), findsOneWidget);
    expect(find.text('Solo en la web'), findsOneWidget);
    expect(find.byKey(const Key('asistente-ir-siguiente')), findsNothing);
    expect(find.text(avisoAlcance), findsOneWidget);
  });

  testWidgets('envía una pregunta, muestra la respuesta y su acción lleva a la pantalla',
      (tester) async {
    final api = ApiFalsa(
      respuesta: const Respuesta(
        '1. Abre el resumen del partido.',
        [Accion('Ver resumen', '/partidos/42/resumen')],
      ),
    )..demora = Completer<void>();
    await _montar(tester, api);

    await tester.enterText(find.byKey(const Key('asistente-campo')), '¿Dónde veo la posesión?');
    await tester.tap(find.byKey(const Key('asistente-enviar')));
    await tester.pump();
    expect(find.text('El asistente está escribiendo…'), findsOneWidget);
    expect(api.preguntas.single, ('¿Dónde veo la posesión?', 'partido_en_vivo', 0));

    api.demora!.complete();
    await tester.pumpAndSettle();
    expect(find.text('¿Dónde veo la posesión?'), findsOneWidget);
    expect(find.text('1. Abre el resumen del partido.'), findsOneWidget);
    expect(find.text('El asistente está escribiendo…'), findsNothing);

    await tester.tap(find.text('Ver resumen'));
    await tester.pumpAndSettle();
    expect(find.text('Resumen 42'), findsOneWidget);
  });

  testWidgets('los textos del asistente miden 16 pt o más', (tester) async {
    await _montar(tester, ApiFalsa(), tema: temaSol);
    for (final w in tester.widgetList<Text>(find.byType(Text))) {
      final estilo = DefaultTextStyle.of(tester.element(find.byWidget(w))).style.merge(w.style);
      expect(estilo.fontSize ?? 14, greaterThanOrEqualTo(16), reason: w.data);
    }
  });

  testWidgets('sin conexión al abrir muestra el aviso y se recupera al reintentar',
      (tester) async {
    final api = ApiFalsa(progresoFalla: const SocketException('sin red'));
    await _montar(tester, api);
    expect(find.byKey(const Key('asistente-sin-conexion')), findsOneWidget);
    expect(find.text(mensajeSinConexion), findsOneWidget);
    expect(find.text('Tu progreso'), findsNothing);

    api.progresoFalla = null;
    await tester.tap(find.text('Reintentar'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('asistente-sin-conexion')), findsNothing);
    expect(find.text('Tu progreso'), findsOneWidget);
  });

  testWidgets('sin conexión al preguntar avisa sin perder la pregunta', (tester) async {
    final api = ApiFalsa(preguntaFalla: TimeoutException('lento'));
    await _montar(tester, api);
    await tester.enterText(find.byKey(const Key('asistente-campo')), '¿Cómo calibro?');
    await tester.tap(find.byKey(const Key('asistente-enviar')));
    await tester.pumpAndSettle();
    expect(find.text('¿Cómo calibro?'), findsOneWidget);
    expect(find.byKey(const Key('asistente-error')), findsOneWidget);
    expect(find.byKey(const Key('asistente-sin-conexion')), findsOneWidget);
  });

  testWidgets('el error del servidor (límite diario) se muestra tal cual', (tester) async {
    final api = ApiFalsa(
      preguntaFalla: ErrorApi(429, 'Llegaste al límite de 30 preguntas por hoy.'),
    );
    await _montar(tester, api);
    await tester.enterText(find.byKey(const Key('asistente-campo')), '¿Siguiente paso?');
    await tester.tap(find.byKey(const Key('asistente-enviar')));
    await tester.pumpAndSettle();
    expect(find.text('Llegaste al límite de 30 preguntas por hoy.'), findsOneWidget);
    expect(find.byKey(const Key('asistente-sin-conexion')), findsNothing);
  });
}
