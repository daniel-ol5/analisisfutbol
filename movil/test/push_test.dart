/// Notificaciones push en el móvil  —  CU-53 (T-096).
///
/// Criterio de T-096: la notificación llega con la app cerrada y abre la
/// recomendación correcta. Firebase se reemplaza por una mensajería falsa: la
/// entrega real se prueba en dispositivos (T-097, casos F1 a F5).
library;

import 'dart:async';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/analisis/modelos.dart';
import 'package:areatecnica/features/analisis/resumen_estado.dart';
import 'package:areatecnica/features/asistencia/push.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_api.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_modelos.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_pagina.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Payload que manda el backend (docs/NOTIFICACIONES-PUSH.md, T-087).
Map<String, dynamic> _payload({String partido = '10', String recomendacion = '42'}) => {
      'tipo': 'recomendacion_tactica',
      'recomendacion_id': recomendacion,
      'partido_id': partido,
      'prioridad': 'CRITICA',
      'ruta': '/asistencia?partido_id=$partido&recomendacion_id=$recomendacion',
    };

class MensajeriaFalsa implements Mensajeria {
  MensajeriaFalsa({this.permiso = true, this.tokenInicial = 'token-fcm-1', this.alAbrir});

  bool permiso;
  String? tokenInicial;
  MensajePush? alAbrir;
  final renovados = StreamController<String>.broadcast();
  final abiertos = StreamController<MensajePush>.broadcast();
  final tocadasCtrl = StreamController<MensajePush>.broadcast();

  @override
  Future<bool> pedirPermiso() async => permiso;
  @override
  Future<String?> token() async => tokenInicial;
  @override
  Stream<String> get tokenRenovado => renovados.stream;
  @override
  Stream<MensajePush> get enPrimerPlano => abiertos.stream;
  @override
  Stream<MensajePush> get tocadas => tocadasCtrl.stream;
  @override
  Future<MensajePush?> tocadaAlAbrir() async => alAbrir;
}

class _Registro {
  final llamadas = <(String, String, String)>[];
  Object? falla;
  Future<void> call(String instalacion, String token, String plataforma) async {
    final error = falla;
    if (error != null) throw error;
    llamadas.add((instalacion, token, plataforma));
  }
}

({ServicioPush servicio, List<String> rutas, List<(String, String)> avisos, _Registro registro})
    _servicio(MensajeriaFalsa mensajeria) {
  final rutas = <String>[];
  final avisos = <(String, String)>[];
  final registro = _Registro();
  final servicio = ServicioPush(
    mensajeria: mensajeria,
    navegar: rutas.add,
    avisar: (texto, ruta) => avisos.add((texto, ruta)),
    registrar: registro.call,
    instalacion: () async => 'instalacion-abc-123',
  );
  return (servicio: servicio, rutas: rutas, avisos: avisos, registro: registro);
}

void main() {
  group('Destino de la notificación', () {
    test('abre las recomendaciones del partido con la de la notificación resaltada', () {
      expect(rutaDeNotificacion(_payload()), '/partidos/10/recomendaciones?recomendacion=42');
    });

    test('sin id de recomendación abre igual las del partido', () {
      expect(rutaDeNotificacion(_payload(recomendacion: '')), '/partidos/10/recomendaciones');
    });

    test('lo que no sabe abrir lo ignora', () {
      expect(rutaDeNotificacion({'tipo': 'otra_cosa', 'partido_id': '10'}), isNull);
      expect(rutaDeNotificacion(_payload(partido: 'x')), isNull);
      expect(rutaDeNotificacion(const {}), isNull);
    });
  });

  group('Criterio de T-096: abrir la recomendación correcta', () {
    test('con la app CERRADA: la notificación que la abrió lleva a su recomendación', () async {
      final m = MensajeriaFalsa(alAbrir: (datos: _payload(recomendacion: '7'), titulo: 'Crítica'));
      final s = _servicio(m);
      await s.servicio.iniciar();
      expect(s.rutas, ['/partidos/10/recomendaciones?recomendacion=7']);
    });

    test('con la app en SEGUNDO PLANO: al tocarla navega', () async {
      final m = MensajeriaFalsa();
      final s = _servicio(m);
      await s.servicio.iniciar();
      expect(s.rutas, isEmpty);
      m.tocadasCtrl.add((datos: _payload(recomendacion: '9'), titulo: null));
      await Future<void>.delayed(Duration.zero);
      expect(s.rutas, ['/partidos/10/recomendaciones?recomendacion=9']);
    });

    test('con la app ABIERTA: avisa con su título y no navega solo', () async {
      final m = MensajeriaFalsa();
      final s = _servicio(m);
      await s.servicio.iniciar();
      m.abiertos.add((datos: _payload(), titulo: 'Reorganización tras una expulsión'));
      await Future<void>.delayed(Duration.zero);
      expect(s.rutas, isEmpty);
      expect(s.avisos, [
        ('Reorganización tras una expulsión', '/partidos/10/recomendaciones?recomendacion=42'),
      ]);
    });
  });

  group('Registro del dispositivo (POST /asistencia/dispositivos)', () {
    test('con permiso registra el token de esta instalación como ANDROID', () async {
      final s = _servicio(MensajeriaFalsa());
      await s.servicio.registrar();
      expect(s.registro.llamadas, [('instalacion-abc-123', 'token-fcm-1', 'ANDROID')]);
    });

    test('sin permiso de notificaciones no registra nada', () async {
      final s = _servicio(MensajeriaFalsa(permiso: false));
      await s.servicio.registrar();
      expect(s.registro.llamadas, isEmpty);
    });

    test('si Firebase rota el token, lo vuelve a registrar (una sola suscripción)', () async {
      final m = MensajeriaFalsa();
      final s = _servicio(m);
      await s.servicio.registrar();
      await s.servicio.registrar(); // el marco puede montarse más de una vez
      m.renovados.add('token-fcm-2');
      await Future<void>.delayed(Duration.zero);
      expect(s.registro.llamadas.map((l) => l.$2), ['token-fcm-1', 'token-fcm-1', 'token-fcm-2']);
    });

    test('sin red o sin sesión no rompe la app: se reintenta la próxima vez', () async {
      final s = _servicio(MensajeriaFalsa());
      s.registro.falla = Exception('sin red');
      await s.servicio.registrar(); // no lanza
      s.registro.falla = null;
      await s.servicio.registrar();
      expect(s.registro.llamadas, hasLength(1));
    });
  });

  test('sin la configuración de Firebase el push queda apagado (CI, web, pruebas)', () async {
    expect(ConfigPush.completa, isFalse);
    await iniciarPush(navegar: (_) {}, avisar: (_, _) {});
    expect(servicioPush, isNull);
  });

  group('Pantalla de recomendaciones al llegar por una notificación', () {
    Future<void> abrir(WidgetTester tester, {required int destacar}) async {
      tester.view.physicalSize = const Size(360, 900);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(MaterialApp(
        theme: temaSol,
        home: RecomendacionesPagina(
          partidoId: 10,
          destacarId: destacar,
          api: _ApiFija(),
          crearFuente: _FuenteQuieta.new,
          ahora: () => DateTime(2026, 11, 19, 21),
        ),
      ));
      await tester.pumpAndSettle();
    }

    BoxDecoration borde(WidgetTester tester, int id) =>
        tester.widget<Container>(find.byKey(Key('recomendacion-$id'))).decoration! as BoxDecoration;

    testWidgets('resalta la recomendación de la notificación', (tester) async {
      await abrir(tester, destacar: 42);
      expect((borde(tester, 42).border! as Border).top.width, 5);
      expect((borde(tester, 43).border! as Border).top.width, 2);
      expect(find.byKey(const Key('destacada-no-activa')), findsNothing);
    });

    testWidgets('si ya no está activa lo avisa y muestra las demás', (tester) async {
      await abrir(tester, destacar: 99);
      expect(find.byKey(const Key('destacada-no-activa')), findsOneWidget);
      expect(find.byKey(const Key('recomendacion-42')), findsOneWidget);
    });
  });
}

Map<String, dynamic> _rec(int id) => {
      'id': id,
      'partido_id': 10,
      'regla_id': id,
      't': 600.0 + id,
      'minuto': 10,
      'mensaje': 'Recomendación $id',
      'justificacion': 'Justificación $id',
      'prioridad': 'CRITICA',
      'datos_soporte': const [],
      'estado': 'VISTA',
      'util': null,
    };

class _ApiFija implements RecomendacionesApi {
  @override
  Future<List<Recomendacion>> listar(int partidoId) async =>
      [_rec(42), _rec(43)].map(Recomendacion.fromJson).toList();
  @override
  Future<void> marcarVista(int recomendacionId) async {}
  @override
  Future<Recomendacion> valorar(int recomendacionId, OpcionValoracion opcion) =>
      throw UnimplementedError();
}

class _FuenteQuieta extends ChangeNotifier implements FuenteVivo {
  final _mensajes = StreamController<Map<String, dynamic>>.broadcast();
  @override
  EstadoConexion get estadoConexion => EstadoConexion.conectado;
  @override
  Stream<Map<String, dynamic>> get mensajes => _mensajes.stream;
  @override
  void conectar(int partidoId) {}
  @override
  void dispose() {
    _mensajes.close();
    super.dispose();
  }
}
