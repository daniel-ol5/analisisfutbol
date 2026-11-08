/// Guardado local en el dispositivo  —  T-024.
///
/// Dos lugares según lo sensible del dato:
///  - Tokens de sesión: flutter_secure_storage (Keystore en Android, Keychain
///    en iOS). Nunca quedan legibles en el dispositivo (criterio de CU-02).
///  - Perfil en caché y preferencias de la app: SharedPreferences. No son
///    secretos y así el perfil se muestra aunque no haya conexión.
library;

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class Almacenamiento {
  static const _seguro = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _claveAcceso = 'areatecnica.access_token';
  static const _claveRefresco = 'areatecnica.refresh_token';
  static const _claveUsuario = 'areatecnica.usuario';
  static const _claveTema = 'areatecnica.tema';

  static Future<void> guardarSesion(String acceso, String refresco) async {
    await _seguro.write(key: _claveAcceso, value: acceso);
    await _seguro.write(key: _claveRefresco, value: refresco);
  }

  /// Guarda una sesión iniciada con credenciales nuevas.
  ///
  /// A diferencia de una renovación del token, un login puede pertenecer a
  /// otra persona o club. Antes de guardar los tokens elimina el perfil y
  /// todas las respuestas descargadas por la cuenta anterior.
  static Future<void> guardarNuevaSesion(String acceso, String refresco) async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_claveUsuario);
    await _borrarCaches(p);
    await guardarSesion(acceso, refresco);
  }

  static Future<String?> leerToken() async {
    await _migrarDesdeTextoPlano();
    return _seguro.read(key: _claveAcceso);
  }

  static Future<String?> leerRefresco() async {
    await _migrarDesdeTextoPlano();
    return _seguro.read(key: _claveRefresco);
  }

  /// Cierra la sesión local: tokens y perfil en caché. Las preferencias quedan.
  static Future<void> borrarToken() async {
    await _seguro.delete(key: _claveAcceso);
    await _seguro.delete(key: _claveRefresco);
    final p = await SharedPreferences.getInstance();
    await p.remove(_claveUsuario);
    await _borrarCaches(p);
  }

  static Future<bool> haySesion() async => await leerToken() != null;

  // ---------- Caché de respuestas para usar sin conexión ----------

  static const _prefijoCache = 'areatecnica.cache.';
  static const _prefijoCacheLegado = 'cache.';

  /// Borra datos descargados de la cuenta, pero conserva preferencias como el tema.
  /// Incluye las claves históricas de Deportivo para impedir que nombres de
  /// equipos o planteles de un club aparezcan al iniciar sesión en otro.
  static Future<void> borrarCaches() async {
    final p = await SharedPreferences.getInstance();
    await _borrarCaches(p);
  }

  static Future<void> _borrarCaches(SharedPreferences p) async {
    final claves = p.getKeys().where(
      (clave) =>
          clave.startsWith(_prefijoCache) ||
          clave.startsWith(_prefijoCacheLegado),
    );
    for (final clave in claves.toList()) {
      await p.remove(clave);
    }
  }

  static Future<void> guardarCache(
    String clave,
    Map<String, dynamic> datos,
  ) async {
    final p = await SharedPreferences.getInstance();
    await p.setString('$_prefijoCache$clave', jsonEncode(datos));
  }

  static Future<Map<String, dynamic>?> leerCache(String clave) async {
    final p = await SharedPreferences.getInstance();
    final crudo = p.getString('$_prefijoCache$clave');
    if (crudo == null) return null;
    try {
      final valor = jsonDecode(crudo);
      return valor is Map<String, dynamic> ? valor : null;
    } on FormatException {
      return null;
    }
  }

  // ---------- Perfil en caché (respuesta de GET /seguridad/yo) ----------

  static Future<void> guardarUsuario(Map<String, dynamic> usuario) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_claveUsuario, jsonEncode(usuario));
  }

  static Future<Map<String, dynamic>?> leerUsuario() async {
    final p = await SharedPreferences.getInstance();
    final crudo = p.getString(_claveUsuario);
    if (crudo == null) return null;
    try {
      final valor = jsonDecode(crudo);
      return valor is Map<String, dynamic> ? valor : null;
    } on FormatException {
      return null;
    }
  }

  // ---------- Preferencias ----------

  static Future<String?> leerTema() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_claveTema);
  }

  static Future<void> guardarTema(String tema) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_claveTema, tema);
  }

  /// Hasta el Sprint 2 los tokens se guardaban en SharedPreferences sin cifrar.
  /// Si quedó alguno, se mueve al almacenamiento seguro y se borra el original,
  /// así nadie tiene que volver a iniciar sesión al actualizar la app.
  static Future<void> _migrarDesdeTextoPlano() async {
    final p = await SharedPreferences.getInstance();
    for (final clave in [_claveAcceso, _claveRefresco]) {
      final viejo = p.getString(clave);
      if (viejo == null) continue;
      if (await _seguro.read(key: clave) == null) {
        await _seguro.write(key: clave, value: viejo);
      }
      await p.remove(clave);
    }
  }
}
