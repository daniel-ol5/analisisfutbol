/// Valorar recomendaciones con un toque en el móvil  —  CU-51 (T-095).
///
/// T-095: "Valorar con un toque". Una sola valoración por recomendación (el
/// backend responde 409 si ya tenía). Útil la deja activa; No útil y Aplicada la
/// sacan de las activas (backend/app/asistencia/valoracion.py, Alejandra).
library;

import 'dart:async';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/analisis/modelos.dart';
import 'package:areatecnica/features/analisis/resumen_estado.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_api.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_modelos.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_pagina.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _partidoId = 42;

Map<String, dynamic> _rec(int id, {String estado = 'VISTA', bool? util}) => {
      'id': id,
      'partido_id': _partidoId,
      'regla_id': id,
      't': 600.0 + id,
      'minuto': 10,
      'mensaje': 'Recomendación $id',
      'justificacion': 'Justificación $id',
      'prioridad': 'ALTA',
      'datos_soporte': const [],
      'estado': estado,
      'util': util,
      'comentario': null,
      'vista_en': null,
    };

/// Responde como el backend de CU-51; `falla` simula un error al valorar.
class ApiValoracion implements RecomendacionesApi {
  ApiValoracion(this.iniciales, {this.falla});

  final List<Map<String, dynamic>> iniciales;
  Object? falla;
  final List<(int, Map<String, Object?>)> enviadas = [];
  Completer<void>? espera;

  @override
  Future<List<Recomendacion>> listar(int partidoId) async =>
      iniciales.map(Recomendacion.fromJson).toList();

  @override
  Future<void> marcarVista(int recomendacionId) async {}

  @override
  Future<Recomendacion> valorar(int recomendacionId, OpcionValoracion opcion) async {
    enviadas.add((recomendacionId, opcion.cuerpo));
    await espera?.future;
    final error = falla;
    if (error != null) throw error;
    return Recomendacion.fromJson(_rec(
      recomendacionId,
      estado: switch (opcion) {
        OpcionValoracion.util => 'VISTA',
        OpcionValoracion.noUtil => 'DESCARTADA',
        OpcionValoracion.aplicada => 'APLICADA',
      },
      util: switch (opcion) {
        OpcionValoracion.util || OpcionValoracion.aplicada => true,
        OpcionValoracion.noUtil => false,
      },
    ));
  }
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

Future<void> _abrir(WidgetTester tester, ApiValoracion api) async {
  tester.view.physicalSize = const Size(360, 900);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MaterialApp(
    theme: temaSol,
    home: RecomendacionesPagina(
      partidoId: _partidoId,
      api: api,
      crearFuente: _FuenteQuieta.new,
      ahora: () => DateTime(2026, 11, 19, 20, 0),
    ),
  ));
  await tester.pumpAndSettle();
}

Finder _boton(OpcionValoracion o, int id) => find.byKey(Key('valorar-${o.valor}-$id'));

void main() {
  group('Modelo', () {
    test('el cuerpo de cada opción es el mismo que manda la web (T-091)', () {
      expect(OpcionValoracion.util.cuerpo, {'util': true, 'aplicada': false, 'comentario': ''});
      expect(OpcionValoracion.noUtil.cuerpo, {'util': false, 'aplicada': false, 'comentario': ''});
      expect(OpcionValoracion.aplicada.cuerpo, {'util': null, 'aplicada': true, 'comentario': ''});
    });

    test('lee la valoración que ya tiene en el servidor', () {
      Recomendacion r(String estado, bool? util) => Recomendacion.fromJson(_rec(1, estado: estado, util: util));
      expect(r('VISTA', null).valoracion, isNull);
      expect(r('VISTA', true).valoracion, OpcionValoracion.util);
      expect(r('DESCARTADA', false).valoracion, OpcionValoracion.noUtil);
      expect(r('APLICADA', true).valoracion, OpcionValoracion.aplicada);
    });
  });

  testWidgets('un toque valora y la tarjeta muestra lo elegido', (tester) async {
    final api = ApiValoracion([_rec(1), _rec(2)]);
    await _abrir(tester, api);
    expect(_boton(OpcionValoracion.util, 1), findsOneWidget);

    await tester.tap(_boton(OpcionValoracion.util, 1));
    await tester.pumpAndSettle();

    final (id, cuerpo) = api.enviadas.single;
    expect(id, 1);
    expect(cuerpo, OpcionValoracion.util.cuerpo);
    expect(find.text('Marcada como Útil'), findsOneWidget);
    expect(_boton(OpcionValoracion.util, 1), findsNothing);   // ya no se puede volver a tocar
    expect(_boton(OpcionValoracion.util, 2), findsOneWidget);  // la otra sigue igual
  });

  testWidgets('"Aplicada" y "No útil" también quedan a la vista hasta la próxima actualización',
      (tester) async {
    final api = ApiValoracion([_rec(1), _rec(2)]);
    await _abrir(tester, api);
    await tester.tap(_boton(OpcionValoracion.aplicada, 1));
    await tester.pumpAndSettle();
    await tester.tap(_boton(OpcionValoracion.noUtil, 2));
    await tester.pumpAndSettle();
    expect(find.text('Marcada como Aplicada'), findsOneWidget);
    expect(find.text('Marcada como No útil'), findsOneWidget);
  });

  testWidgets('mientras se envía, un segundo toque no manda otra valoración', (tester) async {
    final api = ApiValoracion([_rec(1), _rec(2)])..espera = Completer<void>();
    await _abrir(tester, api);
    await tester.tap(_boton(OpcionValoracion.util, 1));
    await tester.pump();
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await tester.tap(_boton(OpcionValoracion.noUtil, 1));
    await tester.tap(_boton(OpcionValoracion.util, 2));
    await tester.pump();
    expect(api.enviadas, hasLength(1));
    api.espera!.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('una ya valorada en el servidor no muestra botones', (tester) async {
    await _abrir(tester, ApiValoracion([_rec(1, util: true)]));
    expect(find.text('Marcada como Útil'), findsOneWidget);
    expect(_boton(OpcionValoracion.util, 1), findsNothing);
  });

  testWidgets('sin conexión avisa y permite reintentar', (tester) async {
    final api = ApiValoracion([_rec(1)], falla: Exception('sin red'));
    await _abrir(tester, api);
    await tester.tap(_boton(OpcionValoracion.util, 1));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('error-valoracion-1')), findsOneWidget);
    expect(find.textContaining('Sin conexión'), findsOneWidget);

    api.falla = null;
    await tester.tap(_boton(OpcionValoracion.util, 1));
    await tester.pumpAndSettle();
    expect(find.text('Marcada como Útil'), findsOneWidget);
    expect(find.byKey(const Key('error-valoracion-1')), findsNothing);
  });

  testWidgets('si ya estaba valorada (409) no insiste: la marca y recarga', (tester) async {
    final api = ApiValoracion([_rec(1)], falla: ErrorApi(409, 'La recomendacion ya fue valorada'));
    await _abrir(tester, api);
    await tester.tap(_boton(OpcionValoracion.noUtil, 1));
    await tester.pumpAndSettle();
    expect(find.text('Marcada como No útil'), findsOneWidget);
    expect(find.byKey(const Key('error-valoracion-1')), findsNothing);
  });

  testWidgets('un rol sin permiso (403) lo dice', (tester) async {
    final api = ApiValoracion([_rec(1)], falla: ErrorApi(403, 'Requiere rol ADMIN, DT o ANALISTA'));
    await _abrir(tester, api);
    await tester.tap(_boton(OpcionValoracion.util, 1));
    await tester.pumpAndSettle();
    expect(find.text('Tu rol no puede valorar recomendaciones.'), findsOneWidget);
  });

  testWidgets('los tres botones entran en 360 dp sin desbordar (tema Sol)', (tester) async {
    await _abrir(tester, ApiValoracion([_rec(1)]));
    expect(tester.takeException(), isNull);
    for (final o in OpcionValoracion.values) {
      final caja = tester.getSize(_boton(o, 1));
      expect(caja.height, greaterThanOrEqualTo(48));   // objetivo táctil
      expect(caja.width, greaterThan(80));
    }
  });
}
