/// Guardado local del token de sesión.
///
/// Usa flutter_secure_storage (Keystore en Android, Keychain en iOS): el
/// token no queda legible en el dispositivo (criterio de aceptación de CU-02).
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Almacenamiento {
  static const _claveAcceso = 'areatecnica.access_token';
  static const _claveRefresco = 'areatecnica.refresh_token';

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static Future<void> guardarSesion(String acceso, String refresco) async {
    await _storage.write(key: _claveAcceso, value: acceso);
    await _storage.write(key: _claveRefresco, value: refresco);
  }

  static Future<String?> leerToken() => _storage.read(key: _claveAcceso);

  static Future<String?> leerRefresco() => _storage.read(key: _claveRefresco);

  static Future<void> borrarToken() async {
    await _storage.delete(key: _claveAcceso);
    await _storage.delete(key: _claveRefresco);
  }

  static Future<bool> haySesion() async => await leerToken() != null;
}
