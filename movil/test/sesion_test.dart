import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:areatecnica/shared/api/almacenamiento.dart';
import 'package:areatecnica/shared/api/cliente.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

http.Response _json(Object cuerpo, int codigo) => http.Response(
      jsonEncode(cuerpo),
      codigo,
      headers: {'content-type': 'application/json'},
    );

Map<String, dynamic> _sesion(String acceso, String refresco) => {
      'access_token': acceso,
      'refresh_token': refresco,
      'token_type': 'bearer',
      'usuario': {'id': 1},
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
    SharedPreferences.setMockInitialValues({});
  });

  group('T-024 · Persistencia local', () {
    test('los tokens quedan en el almacenamiento seguro, no en texto plano',
        () async {
      await Almacenamiento.guardarSesion('acceso-1', 'refresco-1');

      expect(await Almacenamiento.leerToken(), 'acceso-1');
      expect(await Almacenamiento.leerRefresco(), 'refresco-1');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getKeys().where((k) => k.contains('token')), isEmpty);
    });

    test('migra los tokens que una versión anterior dejó en texto plano',
        () async {
      SharedPreferences.setMockInitialValues({
        'areatecnica.access_token': 'viejo-acceso',
        'areatecnica.refresh_token': 'viejo-refresco',
      });

      expect(await Almacenamiento.leerToken(), 'viejo-acceso');
      expect(await Almacenamiento.leerRefresco(), 'viejo-refresco');
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('areatecnica.access_token'), isNull);
      expect(prefs.getString('areatecnica.refresh_token'), isNull);
    });

    test('cerrar sesión borra tokens y perfil, pero conserva las preferencias',
        () async {
      await Almacenamiento.guardarSesion('a', 'r');
      await Almacenamiento.guardarUsuario({'id': 1, 'nombre': 'Ana'});
      await Almacenamiento.guardarTema('sol');

      await Almacenamiento.borrarToken();

      expect(await Almacenamiento.haySesion(), isFalse);
      expect(await Almacenamiento.leerRefresco(), isNull);
      expect(await Almacenamiento.leerUsuario(), isNull);
      expect(await Almacenamiento.leerTema(), 'sol');
    });

    test('el perfil en caché sobrevive a un reinicio de la app', () async {
      await Almacenamiento.guardarUsuario({'id': 7, 'club_nombre': 'Club Demo'});
      expect(await Almacenamiento.leerUsuario(),
          {'id': 7, 'club_nombre': 'Club Demo'});
    });
  });

  group('T-026 · Renovación automática de sesión', () {
    test('ante un 401 renueva con el refresh token y reintenta la petición',
        () async {
      await Almacenamiento.guardarSesion('vencido', 'refresco-1');
      final llamadas = <String>[];

      final c = Cliente(http_: MockClient((req) async {
        final auth = req.headers['authorization'];
        llamadas.add('${req.method} ${req.url.path} $auth');
        if (req.url.path.endsWith('/seguridad/refresh')) {
          expect(jsonDecode(req.body), {'refresh_token': 'refresco-1'});
          return _json(_sesion('nuevo', 'refresco-2'), 200);
        }
        return auth == 'Bearer nuevo'
            ? _json({'ok': true}, 200)
            : _json({'detail': 'Token inválido o expirado'}, 401);
      }));

      expect(await c.get('/partido/1'), {'ok': true});
      expect(llamadas, [
        'GET /api/partido/1 Bearer vencido',
        'POST /api/seguridad/refresh null',
        'GET /api/partido/1 Bearer nuevo',
      ]);
      expect(await Almacenamiento.leerToken(), 'nuevo');
      expect(await Almacenamiento.leerRefresco(), 'refresco-2');
    });

    test('varias peticiones vencidas a la vez comparten una sola renovación',
        () async {
      await Almacenamiento.guardarSesion('vencido', 'refresco-1');
      var renovaciones = 0;
      final liberarRefresh = Completer<void>();

      final c = Cliente(http_: MockClient((req) async {
        if (req.url.path.endsWith('/seguridad/refresh')) {
          renovaciones++;
          await liberarRefresh.future;
          return _json(_sesion('nuevo', 'refresco-2'), 200);
        }
        return req.headers['authorization'] == 'Bearer nuevo'
            ? _json({'ruta': req.url.path}, 200)
            : _json({'detail': 'vencido'}, 401);
      }));

      final pedidos = [c.get('/a'), c.get('/b'), c.get('/c')];
      await Future<void>.delayed(const Duration(milliseconds: 10));
      liberarRefresh.complete();
      final respuestas = await Future.wait(pedidos);

      expect(renovaciones, 1);
      expect(respuestas.map((r) => r['ruta']), ['/api/a', '/api/b', '/api/c']);
    });

    test('si el refresh es rechazado, borra la sesión y avisa', () async {
      await Almacenamiento.guardarSesion('vencido', 'revocado');
      var avisos = 0;

      final c = Cliente(http_: MockClient((req) async {
        return _json({'detail': 'La sesión fue cerrada'}, 401);
      }))
        ..alSesionCaida = () => avisos++;

      await expectLater(
        c.get('/seguridad/yo'),
        throwsA(isA<ErrorApi>().having((e) => e.codigo, 'codigo', 401)),
      );
      expect(avisos, 1);
      expect(await Almacenamiento.haySesion(), isFalse);
    });

    test('sin conexión durante la renovación no cierra la sesión', () async {
      await Almacenamiento.guardarSesion('vencido', 'refresco-1');
      var avisos = 0;

      final c = Cliente(http_: MockClient((req) async {
        if (req.url.path.endsWith('/seguridad/refresh')) {
          throw const SocketException('sin red');
        }
        return _json({'detail': 'vencido'}, 401);
      }))
        ..alSesionCaida = () => avisos++;

      await expectLater(c.get('/seguridad/yo'), throwsA(isA<SocketException>()));
      expect(avisos, 0);
      expect(await Almacenamiento.leerRefresco(), 'refresco-1');
    });

    test('un 401 en el login es «credenciales inválidas»: no renueva', () async {
      await Almacenamiento.guardarSesion('a', 'r');
      final rutas = <String>[];

      final c = Cliente(http_: MockClient((req) async {
        rutas.add(req.url.path);
        return _json({'detail': 'Credenciales inválidas'}, 401);
      }));

      await expectLater(
        c.post('/seguridad/login', cuerpo: {'email': 'x@x.com', 'password': 'y'}),
        throwsA(isA<ErrorApi>()),
      );
      expect(rutas, ['/api/seguridad/login']);
      expect(await Almacenamiento.haySesion(), isTrue);
    });

    test('PATCH adjunta el token y envía el cuerpo en JSON', () async {
      await Almacenamiento.guardarSesion('valido', 'r');
      late http.Request recibida;

      final c = Cliente(http_: MockClient((req) async {
        recibida = req;
        return _json({'nombre': 'José'}, 200);
      }));

      expect(await c.patch('/seguridad/yo', cuerpo: {'nombre': 'José'}),
          {'nombre': 'José'});
      expect(recibida.method, 'PATCH');
      expect(recibida.headers['authorization'], 'Bearer valido');
      expect(jsonDecode(recibida.body), {'nombre': 'José'});
    });
  });
}
