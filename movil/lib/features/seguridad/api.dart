/// Llamadas al backend de Seguridad y Administración  —  P1.
///
/// Endpoints bajo /seguridad. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/cliente.dart';
import '../../shared/api/almacenamiento.dart';

Future<dynamic> ping() => cliente.get('/seguridad/ping');

/// CU-02 · Inicia sesión y guarda el token de forma segura.
Future<Map<String, dynamic>> iniciarSesion(String email, String password) async {
  final respuesta = await cliente.post(
    '/seguridad/login',
    cuerpo: {'email': email, 'password': password},
  ) as Map<String, dynamic>;

  await Almacenamiento.guardarSesion(
    respuesta['access_token'] as String,
    respuesta['refresh_token'] as String,
  );

  return respuesta;
}

/// CU-03 · Invalida el refresh token en el servidor y borra el token local.
///
/// El refresh token se lee ANTES de borrar el almacenamiento y se envía en el
/// body para que el backend lo agregue a la lista negra (`TokenRevocado`).
/// Si la llamada falla (sin red, token ya vencido), igual se limpia el
/// almacenamiento local: el usuario no debe quedar atrapado en una sesión
/// que ya no puede cerrar.
Future<void> cerrarSesion() async {
  final refresco = await Almacenamiento.leerRefresco();
  try {
    await cliente.post(
      '/seguridad/logout',
      cuerpo: refresco == null ? null : {'refresh_token': refresco},
    );
  } finally {
    await Almacenamiento.borrarToken();
  }
}
