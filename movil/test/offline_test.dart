import 'dart:convert';

import 'package:areatecnica/features/deportivo/agenda/api.dart';
import 'package:areatecnica/features/deportivo/alineacion/api.dart';
import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _partido() => {
  'id': 21,
  'equipo_id': 4,
  'competicion_id': null,
  'rival': 'Club Visitante',
  'es_local': true,
  'fecha_hora': '2026-11-15T20:00:00Z',
  'sede': 'Cancha municipal',
  'estado': 'PROGRAMADO',
  'ataca_hacia': null,
  'goles_favor': 0,
  'goles_contra': 0,
  'parte': 0,
  'minuto_actual': 0,
};

Map<String, dynamic> _alineacion() => {
  'id': 8,
  'partido_id': 21,
  'formacion': '4-3-3',
  'jugadores': <Map<String, dynamic>>[],
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('T-054 · Persistencia offline', () {
    test(
      'agenda y alineación sobreviven al reinicio de la aplicación',
      () async {
        await Almacenamiento.guardarCache('agenda.partidos', {
          'guardado': '2026-11-08T14:30:00Z',
          'partidos': [_partido()],
        });
        await Almacenamiento.guardarCache('alineacion.21', _alineacion());

        final preferencias = await SharedPreferences.getInstance();
        final agendaCruda = preferencias.getString(
          'areatecnica.cache.agenda.partidos',
        );
        final alineacionCruda = preferencias.getString(
          'areatecnica.cache.alineacion.21',
        );

        // Una nueva instancia de SharedPreferences simula cerrar y abrir la app.
        SharedPreferences.setMockInitialValues({
          'areatecnica.cache.agenda.partidos': agendaCruda!,
          'areatecnica.cache.alineacion.21': alineacionCruda!,
        });

        final agenda = await agendaEnCache();
        final alineacion = await alineacionEnCache(21);

        expect(agenda?.partidos.single.rival, 'Club Visitante');
        expect(
          agenda?.guardado,
          DateTime.parse('2026-11-08T14:30:00Z').toLocal(),
        );
        expect(alineacion?.partidoId, 21);
        expect(alineacion?.formacion, '4-3-3');
      },
    );

    test(
      'renovar tokens conserva los datos descargados de la misma cuenta',
      () async {
        await Almacenamiento.guardarCache('agenda.partidos', {
          'guardado': '2026-11-08T14:30:00Z',
          'partidos': [_partido()],
        });

        await Almacenamiento.guardarSesion(
          'acceso-renovado',
          'refresco-renovado',
        );

        expect((await agendaEnCache())?.partidos, hasLength(1));
        expect(await Almacenamiento.leerToken(), 'acceso-renovado');
      },
    );
  });

  group('T-054 · Separación entre cuentas y clubes', () {
    test(
      'un login nuevo elimina cachés modernas, históricas y el perfil anterior',
      () async {
        await Almacenamiento.guardarUsuario({
          'id': 7,
          'club_id': 1,
          'email': 'anterior@club.test',
        });
        await Almacenamiento.guardarCache('agenda.partidos', {
          'guardado': '2026-11-08T14:30:00Z',
          'partidos': [_partido()],
        });
        await Almacenamiento.guardarCache('alineacion.21', _alineacion());
        await Almacenamiento.guardarTema('oscuro');

        final preferencias = await SharedPreferences.getInstance();
        await preferencias.setString(
          'cache.deportivo.equipos',
          jsonEncode([
            {'id': 4, 'club_id': 1, 'nombre': 'Equipo del club anterior'},
          ]),
        );
        await preferencias.setString(
          'cache.deportivo.jugadores.4',
          jsonEncode([
            {'id': 99, 'equipo_id': 4, 'nombre': 'Jugador anterior'},
          ]),
        );

        await Almacenamiento.guardarNuevaSesion(
          'acceso-nuevo',
          'refresco-nuevo',
        );

        expect(await Almacenamiento.leerUsuario(), isNull);
        expect(await agendaEnCache(), isNull);
        expect(await alineacionEnCache(21), isNull);
        expect(preferencias.getString('cache.deportivo.equipos'), isNull);
        expect(preferencias.getString('cache.deportivo.jugadores.4'), isNull);
        expect(await Almacenamiento.leerTema(), 'oscuro');
        expect(await Almacenamiento.leerToken(), 'acceso-nuevo');
        expect(await Almacenamiento.leerRefresco(), 'refresco-nuevo');
      },
    );

    test('cerrar sesión también elimina las cachés históricas', () async {
      final preferencias = await SharedPreferences.getInstance();
      await preferencias.setString('cache.deportivo.equipos', '[]');
      await Almacenamiento.guardarCache('agenda.partidos', {
        'guardado': '2026-11-08T14:30:00Z',
        'partidos': [_partido()],
      });

      await Almacenamiento.borrarToken();

      expect(preferencias.getString('cache.deportivo.equipos'), isNull);
      expect(await agendaEnCache(), isNull);
    });
  });
}
