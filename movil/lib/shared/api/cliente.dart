/// Cliente HTTP único de la aplicación.
///
/// Toda llamada al backend pasa por acá. Adjunta el token automáticamente,
/// así ninguna feature tiene que acordarse de hacerlo, y lo renueva solo
/// cuando vence (T-026).
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'almacenamiento.dart';

/// URL de la API. Se pasa al compilar:
///   flutter run --dart-define=API_URL=http://10.0.2.2:8000/api
///
/// 10.0.2.2 es el alias del emulador de Android hacia el localhost de la
/// máquina anfitriona. Para un dispositivo físico, usar la IP de la red local.
/// Mientras el caso de uso devuelva 501, apuntar al mock en el puerto 4010.
const String urlApi = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2:8000/api',
);

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
  }

  dynamic _procesar(http.Response r) {
    if (r.statusCode == 204) return null;

    final cuerpo = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));

    if (r.statusCode >= 400) {
      final detalle = cuerpo is Map && cuerpo['detail'] != null
          ? cuerpo['detail'].toString()
          : 'Error ${r.statusCode}';
      throw ErrorApi(r.statusCode, detalle);
    }
    return cuerpo;
  }
}

final cliente = Cliente();
