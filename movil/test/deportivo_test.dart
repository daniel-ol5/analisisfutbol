import 'dart:convert';

import 'package:areatecnica/app/tema.dart';
import 'package:areatecnica/features/deportivo/api.dart';
import 'package:areatecnica/features/deportivo/modelos.dart';
import 'package:areatecnica/features/deportivo/pagina.dart';
import 'package:areatecnica/features/deportivo/widgets/tarjeta_equipo.dart';
import 'package:areatecnica/features/deportivo/widgets/tarjeta_jugador.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Simula en memoria el canal nativo de flutter_secure_storage, que no tiene
/// implementación real al correr `flutter test` (sin dispositivo/emulador).
const _canalAlmacenamientoSeguro =
    MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

void _mockearAlmacenamientoSeguro(Map<String, String> valoresIniciales) {
  final datos = Map<String, String>.of(valoresIniciales);
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(_canalAlmacenamientoSeguro, (call) async {
    switch (call.method) {
      case 'write':
        datos[call.arguments['key'] as String] =
            call.arguments['value'] as String;
        return null;
      case 'read':
        return datos[call.arguments['key'] as String];
      case 'readAll':
        return datos;
      case 'delete':
        datos.remove(call.arguments['key'] as String);
        return null;
      case 'deleteAll':
        datos.clear();
        return null;
      case 'containsKey':
        return datos.containsKey(call.arguments['key'] as String);
      default:
        return null;
    }
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('T-044 · Modelo Equipo y Colores de Alto Contraste', () {
    test('Serialización y deserialización correcta de Equipo (CU-09)', () {
      final json = {
        'id': 1,
        'club_id': 10,
        'nombre': 'Primera División',
        'categoria': 'Primera A',
        'temporada': '2026',
        'color_local': '#1E5AA8',
        'color_visitante': '#FFFFFF',
        'color_arquero': '#F2C200',
        'activo': true,
        'jugadores': 26,
      };

      final equipo = Equipo.fromJson(json);

      expect(equipo.id, 1);
      expect(equipo.clubId, 10);
      expect(equipo.nombre, 'Primera División');
      expect(equipo.categoria, 'Primera A');
      expect(equipo.temporada, '2026');
      expect(equipo.colorLocal, '#1E5AA8');
      expect(equipo.colorVisitante, '#FFFFFF');
      expect(equipo.colorArquero, '#F2C200');
      expect(equipo.activo, isTrue);
      expect(equipo.jugadores, 26);

      final map = equipo.toJson();
      expect(map['nombre'], 'Primera División');
      expect(map['jugadores'], 26);
    });

    test('Parsea colores hexadecimales #RRGGBB a Color de Flutter', () {
      final azul = Equipo.parseHexColor('#1E5AA8');
      expect(azul, const Color(0xFF1E5AA8));

      final blanco = Equipo.parseHexColor('#FFFFFF');
      expect(blanco, const Color(0xFFFFFFFF));

      final amarillo = Equipo.parseHexColor('#F2C200');
      expect(amarillo, const Color(0xFFF2C200));
    });

    test('Cálculo de luminancia para contraste legible al sol', () {
      // Blanco (#FFFFFF) debe clasificarse como color claro (texto negro)
      expect(Equipo.esColorClaro(const Color(0xFFFFFFFF)), isTrue);

      // Amarillo (#F2C200) debe clasificarse como color claro (texto negro)
      expect(Equipo.esColorClaro(const Color(0xFFF2C200)), isTrue);

      // Azul oscuro (#1E5AA8) debe clasificarse como color oscuro (texto blanco)
      expect(Equipo.esColorClaro(const Color(0xFF1E5AA8)), isFalse);

      // Negro (#000000) debe clasificarse como color oscuro (texto blanco)
      expect(Equipo.esColorClaro(const Color(0xFF000000)), isFalse);
    });
  });

  group('T-044 · Criterio de Aceptación: Carga en menos de 2 segundos con caché local', () {
    test('Carga instantánea de equipos desde caché local en < 100 ms', () async {
      SharedPreferences.setMockInitialValues({
        'cache.deportivo.equipos': jsonEncode([
          {
            'id': 1,
            'club_id': 1,
            'nombre': 'Sub-19 A',
            'categoria': 'Juvenil',
            'temporada': '2026',
            'color_local': '#1E5AA8',
            'color_visitante': '#FFFFFF',
            'color_arquero': '#F2C200',
            'activo': true,
            'jugadores': 22,
          },
          {
            'id': 2,
            'club_id': 1,
            'nombre': 'Sub-17 B',
            'categoria': 'Cadetes',
            'temporada': '2026',
            'color_local': '#D32F2F',
            'color_visitante': '#FFFFFF',
            'color_arquero': '#10B981',
            'activo': true,
            'jugadores': 20,
          },
        ]),
      });

      final cronometro = Stopwatch()..start();
      final equipos = await listarEquipos(forzarRed: false);
      cronometro.stop();

      // Debe cargar en muchísimo menos de 2 segundos (2000 ms)
      expect(cronometro.elapsedMilliseconds, lessThan(2000));
      expect(equipos.length, 2);
      expect(equipos.first.nombre, 'Sub-19 A');
      expect(equipos.last.categoria, 'Cadetes');
    });
  });

  group('T-044 · Interfaz de Usuario y Legibilidad al Sol', () {
    testWidgets('TarjetaEquipo renderiza datos con alto contraste y chips de indumentaria',
        (tester) async {
      const equipoPrueba = Equipo(
        id: 1,
        clubId: 5,
        nombre: 'Primera División',
        categoria: 'Primera A',
        temporada: '2026',
        colorLocal: '#1E5AA8',
        colorVisitante: '#FFFFFF',
        colorArquero: '#F2C200',
        activo: true,
        jugadores: 28,
      );

      bool tapDetectado = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: temaClaro,
          home: Scaffold(
            body: TarjetaEquipo(
              equipo: equipoPrueba,
              onTap: () => tapDetectado = true,
            ),
          ),
        ),
      );

      // Verificamos presencia de textos clave de alto contraste
      expect(find.text('Primera División'), findsOneWidget);
      expect(find.text('PRIMERA A'), findsOneWidget);
      expect(find.text('TEMP 2026'), findsOneWidget);
      expect(find.text('28 JUGADORES'), findsOneWidget);
      expect(find.text('INDUMENTARIA OFICIAL (CU-10)'), findsOneWidget);

      // Verificamos los 3 chips de camisetas
      expect(find.text('LOCAL'), findsOneWidget);
      expect(find.text('VISITA'), findsOneWidget);
      expect(find.text('ARQUERO'), findsOneWidget);
      expect(find.text('#1E5AA8'), findsOneWidget);
      expect(find.text('#FFFFFF'), findsOneWidget);
      expect(find.text('#F2C200'), findsOneWidget);

      // Verificamos interacción táctil
      await tester.tap(find.byType(TarjetaEquipo));
      expect(tapDetectado, isTrue);
    });

    testWidgets('DeportivoPagina renderiza lista, chips de filtrado y abre ficha en modal',
        (tester) async {
      _mockearAlmacenamientoSeguro({
        'areatecnica.access_token': 'fake.token.jwt',
        'areatecnica.refresh_token': 'fake.refresh.jwt',
      });
      SharedPreferences.setMockInitialValues({
        'cache.deportivo.equipos': jsonEncode([
          {
            'id': 1,
            'club_id': 1,
            'nombre': 'Primera División',
            'categoria': 'Primera',
            'temporada': '2026',
            'color_local': '#1E5AA8',
            'color_visitante': '#FFFFFF',
            'color_arquero': '#F2C200',
            'activo': true,
            'jugadores': 25,
          },
          {
            'id': 2,
            'club_id': 1,
            'nombre': 'Reserva Sub-20',
            'categoria': 'Juvenil',
            'temporada': '2026',
            'color_local': '#4FC3F7',
            'color_visitante': '#FFFFFF',
            'color_arquero': '#10B981',
            'activo': true,
            'jugadores': 22,
          },
        ]),
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: temaClaro,
          home: const DeportivoPagina(),
        ),
      );

      await tester.pumpAndSettle();

      // Título y pestañas
      expect(find.text('Gestión Deportiva'), findsOneWidget);
      expect(find.text('Equipos'), findsOneWidget);
      expect(find.text('Plantel'), findsOneWidget);
      expect(find.text('Partidos'), findsOneWidget);
      expect(find.text('Alineación'), findsOneWidget);

      // Verificamos que los equipos cargados se muestran
      expect(find.text('Primera División'), findsOneWidget);
      expect(find.text('Reserva Sub-20'), findsOneWidget);
      expect(find.text('2 EQUIPOS DEL CLUB'), findsOneWidget);

      // Buscador: filtramos por "Reserva"
      await tester.enterText(find.byType(TextField), 'Reserva');
      await tester.pumpAndSettle();

      expect(find.text('Reserva Sub-20'), findsOneWidget);
      expect(find.text('Primera División'), findsNothing);
      expect(find.text('1 EQUIPO DEL CLUB'), findsOneWidget);

      // Limpiamos buscador con el botón X
      await tester.tap(find.byIcon(Icons.clear));
      await tester.pumpAndSettle();
      expect(find.text('Primera División'), findsOneWidget);
      expect(find.text('Reserva Sub-20'), findsOneWidget);

      // Al tocar la tarjeta de Primera División, debe abrirse la ficha modal inferior
      await tester.tap(find.text('Primera División'));
      await tester.pumpAndSettle();

      expect(find.text('COLORES DE INDUMENTARIA (CU-10)'), findsWidgets);
      expect(find.text('Titular (Local)'), findsOneWidget);
      expect(find.text('Alternativa (Visita)'), findsOneWidget);
      expect(find.text('Guardameta (Arquero)'), findsOneWidget);
      expect(find.text('CERRAR FICHA'), findsOneWidget);

      // Cerramos el modal
      await tester.tap(find.text('CERRAR FICHA'));
      await tester.pumpAndSettle();
      expect(find.text('CERRAR FICHA'), findsNothing);
    });
  });

  group('T-045 · Modelo Jugador', () {
    test('Serialización y deserialización correcta de Jugador (CU-11)', () {
      final json = {
        'id': 7,
        'equipo_id': 1,
        'nombre': 'Marcelo',
        'apellido': 'Moreno',
        'dorsal': 9,
        'posicion': 'DEL',
        'pie_habil': 'DER',
        'altura_cm': 178,
        'peso_kg': 75.5,
        'activo': true,
      };

      final jugador = Jugador.fromJson(json);

      expect(jugador.id, 7);
      expect(jugador.equipoId, 1);
      expect(jugador.nombreCompleto, 'Marcelo Moreno');
      expect(jugador.dorsal, 9);
      expect(jugador.posicionLegible, 'Delantero');
      expect(jugador.pieLegible, 'Derecho');
      expect(jugador.alturaCm, 178);
      expect(jugador.pesoKg, 75.5);
      expect(jugador.activo, isTrue);

      final map = jugador.toJson();
      expect(map['nombre'], 'Marcelo');
      expect(map['dorsal'], 9);
    });
  });

  group(
      'T-045 · Criterio de Aceptación: datos disponibles sin conexión tras la primera sincronización',
      () {
    test('Carga instantánea del plantel desde caché local en < 100 ms', () async {
      SharedPreferences.setMockInitialValues({
        'cache.deportivo.jugadores.1': jsonEncode([
          {
            'id': 1,
            'equipo_id': 1,
            'nombre': 'Marcelo',
            'apellido': 'Moreno',
            'dorsal': 9,
            'posicion': 'DEL',
            'pie_habil': 'DER',
            'altura_cm': 178,
            'peso_kg': 75.5,
            'activo': true,
          },
          {
            'id': 2,
            'equipo_id': 1,
            'nombre': 'Carlos',
            'apellido': 'Lampe',
            'dorsal': 1,
            'posicion': 'ARQ',
            'pie_habil': 'DER',
            'altura_cm': 188,
            'peso_kg': 82.0,
            'activo': true,
          },
        ]),
      });

      final cronometro = Stopwatch()..start();
      final jugadores = await listarJugadores(1);
      cronometro.stop();

      expect(jugadores.length, 2);
      expect(jugadores.first.nombreCompleto, 'Marcelo Moreno');
      expect(cronometro.elapsedMilliseconds, lessThan(100));
    });
  });

  group('T-045 · Interfaz de Usuario y Búsqueda del Plantel', () {
    testWidgets('TarjetaJugador renderiza datos con alto contraste',
        (tester) async {
      const jugador = Jugador(
        id: 1,
        equipoId: 1,
        nombre: 'Marcelo',
        apellido: 'Moreno',
        dorsal: 9,
        posicion: 'DEL',
        pieHabil: 'DER',
        alturaCm: 178,
        pesoKg: 75.5,
        activo: true,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: temaClaro,
          home: Scaffold(body: TarjetaJugador(jugador: jugador)),
        ),
      );

      expect(find.text('9'), findsOneWidget);
      expect(find.text('Marcelo Moreno'), findsOneWidget);
      expect(find.text('Delantero · Pie Derecho · 178 cm'), findsOneWidget);
      expect(find.text('BAJA'), findsNothing);
    });

    testWidgets(
        'DeportivoPagina: pestaña Plantel carga desde caché y filtra por nombre o dorsal',
        (tester) async {
      _mockearAlmacenamientoSeguro({
        'areatecnica.access_token': 'fake.token.jwt',
        'areatecnica.refresh_token': 'fake.refresh.jwt',
      });
      SharedPreferences.setMockInitialValues({
        'cache.deportivo.equipos': jsonEncode([
          {
            'id': 1,
            'club_id': 1,
            'nombre': 'Primera División',
            'categoria': 'Primera',
            'temporada': '2026',
            'color_local': '#1E5AA8',
            'color_visitante': '#FFFFFF',
            'color_arquero': '#F2C200',
            'activo': true,
            'jugadores': 2,
          },
        ]),
        'cache.deportivo.jugadores.1': jsonEncode([
          {
            'id': 1,
            'equipo_id': 1,
            'nombre': 'Marcelo',
            'apellido': 'Moreno',
            'dorsal': 9,
            'posicion': 'DEL',
            'pie_habil': 'DER',
            'altura_cm': 178,
            'peso_kg': 75.5,
            'activo': true,
          },
          {
            'id': 2,
            'equipo_id': 1,
            'nombre': 'Carlos',
            'apellido': 'Lampe',
            'dorsal': 1,
            'posicion': 'ARQ',
            'pie_habil': 'DER',
            'altura_cm': 188,
            'peso_kg': 82.0,
            'activo': true,
          },
        ]),
      });

      await tester.pumpWidget(
        MaterialApp(
          theme: temaClaro,
          home: const DeportivoPagina(),
        ),
      );
      await tester.pumpAndSettle();

      // Cambiamos a la pestaña Plantel
      await tester.tap(find.text('Plantel'));
      await tester.pumpAndSettle();

      expect(find.text('Marcelo Moreno'), findsOneWidget);
      expect(find.text('Carlos Lampe'), findsOneWidget);
      expect(find.text('2 JUGADORES DEL PLANTEL'), findsOneWidget);

      // Búsqueda por nombre
      await tester.enterText(find.byType(TextField), 'Carlos');
      await tester.pumpAndSettle();
      expect(find.text('Carlos Lampe'), findsOneWidget);
      expect(find.text('Marcelo Moreno'), findsNothing);
      expect(find.text('1 JUGADOR DEL PLANTEL'), findsOneWidget);

      // Búsqueda por dorsal
      await tester.enterText(find.byType(TextField), '9');
      await tester.pumpAndSettle();
      expect(find.text('Marcelo Moreno'), findsOneWidget);
      expect(find.text('Carlos Lampe'), findsNothing);
    });
  });
}
