/// Guardado local del token de sesión.
///
/// En el Sprint 1 usa SharedPreferences. Antes de producción hay que pasar a
/// flutter_secure_storage: SharedPreferences no cifra, y el token no debería
/// quedar legible en el dispositivo (criterio de aceptación de CU-02).
library;

import 'package:shared_preferences/shared_preferences.dart';

class Almacenamiento {
  static const _claveAcceso = 'areatecnica.access_token';
  static const _claveRefresco = 'areatecnica.refresh_token';

  static Future<void> guardarSesion(String acceso, String refresco) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_claveAcceso, acceso);
    await p.setString(_claveRefresco, refresco);
  }

  static Future<String?> leerToken() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_claveAcceso);
  }

  static Future<String?> leerRefresco() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_claveRefresco);
  }

  static Future<void> borrarToken() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_claveAcceso);
    await p.remove(_claveRefresco);
  }

  static Future<bool> haySesion() async => await leerToken() != null;
}
