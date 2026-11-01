/// Cliente HTTP único de la aplicación.
///
/// Toda llamada al backend pasa por acá. Adjunta el token automáticamente,
/// así ninguna feature tiene que acordarse de hacerlo, y lo renueva solo
/// cuando vence (T-026).
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'almacenamiento.dart';
import 'entorno.dart';

/// Rutas donde un 401 significa «credenciales inválidas» y no «sesión caída»:
/// no se intenta renovar ni se cierra la sesión.
const _rutasPublicas = [
  '/seguridad/login',
  '/seguridad/registro',
  '/seguridad/refresh',
];

class ErrorApi implements Exception {
  ErrorApi(this.codigo, this.detalle);
  final int codigo;
  final String detalle;

  /// 501 significa que el caso de uso está declarado en el contrato pero
  /// todavía no implementado. El detalle dice quién lo tiene y en qué sprint.
  bool get pendiente => codigo == 501;

  @override
  String toString() => 'ErrorApi($codigo): $detalle';
}

class Cliente {
  Cliente({http.Client? http_}) : _http = http_ ?? http.Client();
  final http.Client _http;

  /// Se invoca cuando la sesión no se pudo renovar y quedó cerrada. La app la
  /// usa para volver al login; `shared/` no conoce las rutas.
  void Function()? alSesionCaida;

  /// Renovación en curso. Si varias peticiones vencen a la vez, todas esperan
  /// la misma: el refresh token rota y solo sirve una vez.
  Future<bool>? _renovacion;

  Future<dynamic> get(String ruta, {Map<String, String>? params}) {
    final uri = Uri.parse('$urlApi$ruta').replace(queryParameters: params);
    return _enviar(ruta, (cab) => _http.get(uri, headers: cab));
  }

  Future<dynamic> post(String ruta, {Object? cuerpo}) => _enviar(
      ruta,
      (cab) => _http.post(Uri.parse('$urlApi$ruta'),
          headers: cab, body: _json(cuerpo)));

  Future<dynamic> put(String ruta, {Object? cuerpo}) => _enviar(
      ruta,
      (cab) => _http.put(Uri.parse('$urlApi$ruta'),
          headers: cab, body: _json(cuerpo)));

  Future<dynamic> patch(String ruta, {Object? cuerpo}) => _enviar(
      ruta,
      (cab) => _http.patch(Uri.parse('$urlApi$ruta'),
          headers: cab, body: _json(cuerpo)));

  static String? _json(Object? cuerpo) =>
      cuerpo == null ? null : jsonEncode(cuerpo);

  Future<dynamic> _enviar(
    String ruta,
    Future<http.Response> Function(Map<String, String> cabeceras) peticion,
  ) async {
    final token = await Almacenamiento.leerToken();
    var r = await peticion(_cabeceras(token));

    if (r.statusCode == 401 && !_esPublica(ruta) && token != null) {
      // Si otra petición ya renovó mientras esta viajaba, alcanza con reintentar.
      final vigente = await Almacenamiento.leerToken();
      final renovado = vigente != token || await _renovar();
      if (!renovado) {
        await Almacenamiento.borrarToken();
        alSesionCaida?.call();
      } else {
        r = await peticion(_cabeceras(await Almacenamiento.leerToken()));
      }
    }
    return _procesar(r);
  }

  Map<String, String> _cabeceras(String? token) => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  static bool _esPublica(String ruta) =>
      _rutasPublicas.any((publica) => ruta.startsWith(publica));

  Future<bool> _renovar() =>
      _renovacion ??= _pedirRenovacion().whenComplete(() => _renovacion = null);

  /// true si se obtuvo una sesión nueva. Un error de red se propaga tal cual:
  /// sin conexión no se sabe si la sesión sigue viva, así que no se la cierra.
  Future<bool> _pedirRenovacion() async {
    final refresco = await Almacenamiento.leerRefresco();
    if (refresco == null || refresco.isEmpty) return false;

    final r = await _http.post(
      Uri.parse('$urlApi/seguridad/refresh'),
      headers: _cabeceras(null),
      body: jsonEncode({'refresh_token': refresco}),
    );
    if (r.statusCode != 200) return false;

    final sesion = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    await Almacenamiento.guardarSesion(
      sesion['access_token'] as String,
      sesion['refresh_token'] as String,
    );
    return true;
  Future<dynamic> get(String ruta, {Map<String, String>? params}) {
    final uri = Uri.parse('$urlApi$ruta').replace(queryParameters: params);
    return _conReintento(() async => _http.get(uri, headers: await _cabeceras()));
  }

  Future<dynamic> post(String ruta, {Object? cuerpo}) {
    return _conReintento(() async => _http.post(
          Uri.parse('$urlApi$ruta'),
          headers: await _cabeceras(),
          body: cuerpo == null ? null : jsonEncode(cuerpo),
        ));
  }

  Future<dynamic> put(String ruta, {Object? cuerpo}) {
    return _conReintento(() async => _http.put(
          Uri.parse('$urlApi$ruta'),
          headers: await _cabeceras(),
          body: cuerpo == null ? null : jsonEncode(cuerpo),
        ));
  }

  /// Ejecuta [solicitud] y, si el servidor responde 401, intenta renovar la
  /// sesión una sola vez con el refresh token (CU-02) antes de reintentar.
  ///
  /// Si la renovación falla (no hay refresh token, o también está vencido o
  /// revocado), se propaga el 401 original: ahí es cuando `_procesar` limpia
  /// el almacenamiento local, no antes.
  Future<dynamic> _conReintento(
    Future<http.Response> Function() solicitud,
  ) async {
    final respuesta = await solicitud();
    if (respuesta.statusCode != 401) return _procesar(respuesta);
    if (!await _renovarSesion()) return _procesar(respuesta);
    return _procesar(await solicitud());
  }

  /// Llama a /seguridad/refresh directo con _http (no con get/post/put) para
  /// no reentrar en _conReintento: ese endpoint es público (no requiere
  /// Authorization) y nunca debe disparar, a su vez, otro intento de renovar.
  Future<bool> _renovarSesion() async {
    final refresco = await Almacenamiento.leerRefresco();
    if (refresco == null) return false;

    try {
      final r = await _http.post(
        Uri.parse('$urlApi/seguridad/refresh'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': refresco}),
      );
      if (r.statusCode != 200) return false;

      final cuerpo = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
      await Almacenamiento.guardarSesion(
        cuerpo['access_token'] as String,
        cuerpo['refresh_token'] as String,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<dynamic> _procesar(http.Response r) async {
    if (r.statusCode == 204) return null;

    final cuerpo = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));

    if (r.statusCode >= 400) {
      final detalle = cuerpo is Map && cuerpo['detail'] != null
          ? cuerpo['detail'].toString()
          : 'Error ${r.statusCode}';
      if (r.statusCode == 401) await Almacenamiento.borrarToken();
      throw ErrorApi(r.statusCode, detalle);
    }
    return cuerpo;
  }
}

final cliente = Cliente();
