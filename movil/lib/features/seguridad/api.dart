/// Llamadas al backend de Seguridad y Administración  —  P1.
///
/// Endpoints bajo /seguridad. Mientras el caso de uso devuelva 501, apuntar el
/// cliente al mock con --dart-define=API_URL=http://10.0.2.2:4010/api
library;

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'modelos.dart';

Future<dynamic> ping() => cliente.get('/seguridad/ping');

/// CU-02 · Iniciar sesión y guardar los tokens en el dispositivo.
Future<void> iniciarSesion(String email, String password) async {
  final sesion = await cliente.post('/seguridad/login', cuerpo: {
    'email': email,
    'password': password,
  }) as Map<String, dynamic>;
  await _guardar(sesion);
}

/// CU-03 · Cerrar sesión. Aunque el servidor no responda, la sesión local se
/// borra igual: el usuario pidió salir.
Future<void> cerrarSesion() async {
  try {
    final refresco = await Almacenamiento.leerRefresco();
    await cliente.post('/seguridad/logout', cuerpo: {'refresh_token': refresco});
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
