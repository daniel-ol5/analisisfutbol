/// Cliente HTTP único de la aplicación.
///
/// Toda llamada al backend pasa por acá. Adjunta el token automáticamente,
/// así ninguna feature tiene que acordarse de hacerlo.
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

  Future<Map<String, String>> _cabeceras() async {
    final token = await Almacenamiento.leerToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<dynamic> get(String ruta, {Map<String, String>? params}) async {
    final uri = Uri.parse('$urlApi$ruta').replace(queryParameters: params);
    return _procesar(await _http.get(uri, headers: await _cabeceras()));
  }

  Future<dynamic> post(String ruta, {Object? cuerpo}) async {
    final r = await _http.post(
      Uri.parse('$urlApi$ruta'),
      headers: await _cabeceras(),
      body: cuerpo == null ? null : jsonEncode(cuerpo),
    );
    return _procesar(r);
  }

  Future<dynamic> put(String ruta, {Object? cuerpo}) async {
    final r = await _http.put(
      Uri.parse('$urlApi$ruta'),
      headers: await _cabeceras(),
      body: cuerpo == null ? null : jsonEncode(cuerpo),
    );
    return _procesar(r);
  }

  dynamic _procesar(http.Response r) {
    if (r.statusCode == 204) return null;

    final cuerpo = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));

    if (r.statusCode >= 400) {
      final detalle = cuerpo is Map && cuerpo['detail'] != null
          ? cuerpo['detail'].toString()
          : 'Error ${r.statusCode}';
      // TODO Pb-01: renovar con el refresh token en vez de cerrar la sesión.
      if (r.statusCode == 401) Almacenamiento.borrarToken();
      throw ErrorApi(r.statusCode, detalle);
    }
    return cuerpo;
  }
}

final cliente = Cliente();
