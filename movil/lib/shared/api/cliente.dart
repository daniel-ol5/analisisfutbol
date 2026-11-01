/// Cliente HTTP único de la aplicación.
///
/// Toda llamada al backend pasa por acá. Adjunta el token automáticamente,
/// así ninguna feature tiene que acordarse de hacerlo.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'almacenamiento.dart';
import 'entorno.dart';

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
