/// Llamadas al backend de Gestión Deportiva  —  P2 (CU-09).
///
/// Optimizado para carga rápida (< 2s) con caché local en SharedPreferences
/// para permitir lectura instantánea incluso con baja cobertura celular en la cancha.
library;

import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';
import 'modelos.dart';

const _claveCacheEquipos = 'cache.deportivo.equipos';

Future<dynamic> ping() => cliente.get('/deportivo/ping');

/// CU-09: Obtener listado de equipos optimizado para respuesta en < 2 segundos.
///
/// Estrategia:
/// 1. Si no se fuerza red, lee inmediatamente el caché local (típicamente < 30 ms).
/// 2. Si no hay caché o se pide refrescar, consulta el endpoint `/deportivo/equipos`.
/// 3. Se aplica un timeout de 2 segundos para cumplir el SLA del criterio de aceptación.
Future<List<Equipo>> listarEquipos({
  bool activos = true,
  bool forzarRed = false,
}) async {
  final prefs = await SharedPreferences.getInstance();

  if (!forzarRed) {
    final cacheJson = prefs.getString(_claveCacheEquipos);
    if (cacheJson != null && cacheJson.isNotEmpty) {
      try {
        final listaRaw = jsonDecode(cacheJson) as List<dynamic>;
        final equiposCache =
            listaRaw.map((e) => Equipo.fromJson(e as Map<String, dynamic>)).toList();
        if (equiposCache.isNotEmpty) {
          // Despachamos en segundo plano la actualización del caché sin bloquear la UI
          unawaited(_actualizarCacheSilencioso(activos));
          return equiposCache;
        }
      } catch (_) {
        // Si el caché estuviese corrupto, continuamos a red
      }
    }
  }

  // Consulta por red con timeout estricto de 2000 ms
  try {
    final r = await cliente
        .get('/deportivo/equipos', params: {'activos': '$activos'})
        .timeout(const Duration(milliseconds: 2000));

    if (r is List) {
      final equipos = r
          .map((item) => Equipo.fromJson(item as Map<String, dynamic>))
          .toList();

      // Guardamos copia en caché local
      await prefs.setString(_claveCacheEquipos, jsonEncode(r));
      return equipos;
    }
    return [];
  } catch (e) {
    // Si falla la red o excede 2s, intentamos fallback a caché previo si existe
    final cacheJson = prefs.getString(_claveCacheEquipos);
    if (cacheJson != null && cacheJson.isNotEmpty) {
      try {
        final listaRaw = jsonDecode(cacheJson) as List<dynamic>;
        return listaRaw
            .map((item) => Equipo.fromJson(item as Map<String, dynamic>))
            .toList();
      } catch (_) {}
    }
    rethrow;
  }
}

Future<void> _actualizarCacheSilencioso(bool activos) async {
  try {
    final r = await cliente
        .get('/deportivo/equipos', params: {'activos': '$activos'})
        .timeout(const Duration(milliseconds: 2000));
    if (r is List) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_claveCacheEquipos, jsonEncode(r));
    }
  } catch (_) {
    // En actualización silenciosa ignoramos errores de red
  }
}

/// Inicia sesión rápida con la cuenta demo de prueba si la app no tiene token
Future<void> conectarSesionDemo() async {
  const creds = {
    'email': 'demo_admin@areatecnica.com',
    'password': 'Password123!',
  };

  try {
    final r = await cliente.post('/seguridad/login', cuerpo: creds);
    if (r is Map && r['access_token'] != null) {
      await Almacenamiento.guardarSesion(
        r['access_token'].toString(),
        r['refresh_token']?.toString() ?? '',
      );
      return;
    }
  } catch (e) {
    // Si el usuario demo no existe, lo registramos
    if (e is ErrorApi && (e.codigo == 401 || e.codigo == 404)) {
      final reg = await cliente.post('/seguridad/registro', cuerpo: {
        'nombre_club': 'Club Bolívar Demo',
        'ciudad': 'La Paz',
        'email': creds['email'],
        'password': creds['password'],
        'nombre': 'Daniel',
        'apellido': 'DT',
      });
      if (reg is Map && reg['access_token'] != null) {
        await Almacenamiento.guardarSesion(
          reg['access_token'].toString(),
          reg['refresh_token']?.toString() ?? '',
        );
        return;
      }
    }
    rethrow;
  }
}
