/// Llamadas al backend de Seguridad y Administración  —  P1.
///
/// Endpoints bajo /seguridad. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'modelos.dart';

Future<dynamic> ping() => cliente.get('/seguridad/ping');

/// CU-02 · Inicia sesión y guarda el token de forma segura.
Future<Map<String, dynamic>> iniciarSesion(String email, String password) async {
  final respuesta = await cliente.post(
    '/seguridad/login',
    cuerpo: {'email': email, 'password': password},
  ) as Map<String, dynamic>;

  await _guardar(respuesta);
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
  } catch (_) {
    // Sin conexión o sesión ya vencida: no hay nada más que revocar.
  } finally {
    await Almacenamiento.borrarToken();
  }
}

/// CU-05 · Perfil propio. Lo deja en caché para mostrarlo sin conexión.
Future<Perfil> obtenerPerfil() async {
  final json = await cliente.get('/seguridad/yo') as Map<String, dynamic>;
  await Almacenamiento.guardarUsuario(json);
  return Perfil.fromJson(json);
}

/// CU-05 · Último perfil descargado, o null si nunca se descargó.
Future<Perfil?> perfilEnCache() async {
  final json = await Almacenamiento.leerUsuario();
  if (json == null) return null;
  try {
    return Perfil.fromJson(json);
  } catch (_) {
    return null; // caché de otra versión de la app
  }
}

/// CU-05 · Editar nombre y apellido propios.
Future<Perfil> editarPerfil({
  required String nombre,
  required String apellido,
}) async {
  final json = await cliente.patch('/seguridad/yo', cuerpo: {
    'nombre': nombre,
    'apellido': apellido,
  }) as Map<String, dynamic>;
  await Almacenamiento.guardarUsuario(json);
  return Perfil.fromJson(json);
}

/// CU-05 · Cambiar la contraseña propia. ErrorApi 403 si la actual no coincide.
///
/// El servidor cierra todas las sesiones, también esta, y devuelve una nueva
/// que se guarda para seguir conectado.
Future<void> cambiarPassword({
  required String actual,
  required String nueva,
}) async {
  final sesion = await cliente.post('/seguridad/yo/password', cuerpo: {
    'password_actual': actual,
    'password_nueva': nueva,
  }) as Map<String, dynamic>;
  await _guardar(sesion);
}

Future<void> _guardar(Map<String, dynamic> sesion) => Almacenamiento.guardarSesion(
      sesion['access_token'] as String,
      sesion['refresh_token'] as String,
    );
