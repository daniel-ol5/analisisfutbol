/// Recomendaciones en vivo en móvil  —  CU-50 (T-094).
///
/// Criterio: se muestran como máximo 3 a la vez, priorizadas.
library;

import 'dart:async';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/analisis/modelos.dart';
import 'package:areatecnica/features/analisis/resumen_estado.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_api.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_modelos.dart';
import 'package:areatecnica/features/asistencia/recomendaciones_pagina.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

const _partidoId = 42;

Map<String, dynamic> _rec(int id, String prioridad,
        {double t = 600, String? mensaje, int? partido, String estado = 'PENDIENTE'}) =>
    {
      'id': id,
      'partido_id': partido ?? _partidoId,
      'regla_id': id,
      't': t + id,
      'minuto': 10,
      'mensaje': mensaje ?? 'Recomendación $id',
      'justificacion': 'Justificación $id',
      'prioridad': prioridad,
      'datos_soporte': [
        {'metrica': 'posesion_rival_pct', 'valor': 68.4, 'umbral': 65},
      ],
      'estado': estado,
      'util': null,
      'comentario': null,
      'vista_en': null,
    };

class ApiFalsa implements RecomendacionesApi {
  ApiFalsa(this.iniciales);

  final List<Map<String, dynamic>> iniciales;
  final List<int> vistas = [];

  @override
  Future<List<Recomendacion>> listar(int partidoId) async =>
      iniciales.map(Recomendacion.fromJson).toList();

  @override
  Future<void> marcarVista(int recomendacionId) async => vistas.add(recomendacionId);

  /// T-095: estas pruebas no valoran; las de la valoración están en valoracion_test.dart.
  @override
  Future<Recomendacion> valorar(int recomendacionId, OpcionValoracion opcion) =>
      throw UnimplementedError();
}

class FuenteFalsa extends ChangeNotifier implements FuenteVivo {
  final _mensajes = StreamController<Map<String, dynamic>>.broadcast();
  EstadoConexion _estado = EstadoConexion.conectado;

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
  void conectar(int partidoId) {}

  @override
  void dispose() {
    _mensajes.close();
    super.dispose();
  }
}

Future<FuenteFalsa> _abrir(WidgetTester tester, ApiFalsa api) async {
  tester.view.physicalSize = const Size(360, 640);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  late FuenteFalsa fuente;
  await tester.pumpWidget(MaterialApp(
    theme: temaSol,
    home: RecomendacionesPagina(
      partidoId: _partidoId,
      api: api,
      crearFuente: () => fuente = FuenteFalsa(),
      ahora: () => DateTime(2026, 11, 18, 20, 15, 7),
    ),
  ));
  await tester.pumpAndSettle();
  return fuente;
}

/// Mensajes visibles en pantalla, de arriba hacia abajo.
List<String> _mensajesEnOrden(WidgetTester tester) {
  final textos = tester
      .widgetList<Text>(find.byWidgetPredicate(
          (w) => w is Text && w.key is ValueKey<String> &&
              (w.key! as ValueKey<String>).value.startsWith('mensaje-'),
          skipOffstage: false))
      .toList();
  final conPosicion = [
    for (final t in textos) (tester.getTopLeft(find.byWidget(t, skipOffstage: false)).dy, t.data!),
  ]..sort((a, b) => a.$1.compareTo(b.$1));
  return conPosicion.map((e) => e.$2).toList();
}

void main() {
  testWidgets('nunca muestra más de 3, aunque el servidor mande más', (tester) async {
    await _abrir(tester, ApiFalsa([
      _rec(1, 'BAJA'),
      _rec(2, 'MEDIA'),
      _rec(3, 'ALTA'),
      _rec(4, 'CRITICA'),
      _rec(5, 'MEDIA', estado: 'APLICADA'),   // ya valorada: no es activa
    ]));
    // Se cuentan las tarjetas construidas, no solo las visibles: así no depende del alto.
    expect(find.byWidgetPredicate(
        (w) => w.key is ValueKey<String> &&
            (w.key! as ValueKey<String>).value.startsWith('recomendacion-'),
        skipOffstage: false), findsNWidgets(3));
    expect(find.text('Recomendación 1', skipOffstage: false), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('ordenadas por prioridad, con mensaje, justificación y cifras', (tester) async {
    final api = ApiFalsa([_rec(1, 'BAJA'), _rec(2, 'CRITICA'), _rec(3, 'MEDIA')]);
    await _abrir(tester, api);

    expect(_mensajesEnOrden(tester), ['Recomendación 2', 'Recomendación 3', 'Recomendación 1']);
    expect(find.text('CRÍTICA'), findsOneWidget);
    expect(find.text('Justificación 2'), findsOneWidget);
    expect(find.text('• Posesión rival: 68,4 % (umbral 65 %)'), findsWidgets);
    // Al mostrarse, quedan vistas en el servidor (una sola vez cada una).
    expect(api.vistas..sort(), [1, 2, 3]);
  });

  testWidgets('una nueva por WebSocket desplaza a la de menor prioridad', (tester) async {
    final fuente = await _abrir(tester, ApiFalsa([
      _rec(1, 'ALTA'),
      _rec(2, 'MEDIA'),
      _rec(3, 'BAJA'),
    ]));
    expect(_mensajesEnOrden(tester), ['Recomendación 1', 'Recomendación 2', 'Recomendación 3']);

    fuente.emitir({'tipo': 'recomendacion', 'datos': _rec(9, 'CRITICA', mensaje: 'Reorganiza el bloque')});
    fuente.emitir({'tipo': 'recomendacion', 'datos': _rec(8, 'CRITICA', partido: 99)}); // otro partido
    fuente.emitir({'tipo': 'posesion', 'datos': {'t': 1}}); // otro tipo: se ignora
    await tester.pumpAndSettle();

    expect(_mensajesEnOrden(tester), ['Reorganiza el bloque', 'Recomendación 1', 'Recomendación 2']);
    expect(find.text('Recomendación 3', skipOffstage: false), findsNothing);
    expect(find.text('Recomendación 8', skipOffstage: false), findsNothing);
  });

  testWidgets('sin conexión: aviso claro con la hora y quedan las últimas', (tester) async {
    final fuente = await _abrir(tester, ApiFalsa([_rec(1, 'ALTA')]));
    expect(find.byKey(const Key('recomendaciones-sin-conexion')), findsNothing);

    fuente.estado = EstadoConexion.reconectando;
    await tester.pumpAndSettle();
    expect(find.text('Sin conexión'), findsOneWidget);
    expect(find.text('Datos de las 20:15:07'), findsOneWidget);
    expect(find.text('Recomendación 1'), findsOneWidget);
  });

  testWidgets('sin recomendaciones, lo dice', (tester) async {
    await _abrir(tester, ApiFalsa([]));
    expect(find.byKey(const Key('recomendaciones-vacio')), findsOneWidget);
  });

  testWidgets('ningún texto por debajo de 16 puntos', (tester) async {
    await _abrir(tester, ApiFalsa([_rec(1, 'CRITICA'), _rec(2, 'BAJA')]));
    for (final p in tester.renderObjectList<RenderParagraph>(find.descendant(
        of: find.byType(RecomendacionesPagina), matching: find.byType(RichText)))) {
      final estilo = p.text.style;
      if (estilo?.fontFamily == 'MaterialIcons') continue;
      expect(estilo?.fontSize ?? 0, greaterThanOrEqualTo(16),
          reason: '«${p.text.toPlainText()}» mide ${estilo?.fontSize}');
    }
  });
}
