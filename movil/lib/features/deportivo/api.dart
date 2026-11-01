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

String _claveCacheJugadores(int equipoId) => 'cache.deportivo.jugadores.$equipoId';

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

/// CU-11: Obtener el plantel de un equipo con la misma estrategia de caché
/// que [listarEquipos], para que la búsqueda por nombre o dorsal funcione
/// sin conexión en la cancha una vez sincronizado al menos una vez.
Future<List<Jugador>> listarJugadores(
  int equipoId, {
  bool activos = true,
  bool forzarRed = false,
}) async {
  final prefs = await SharedPreferences.getInstance();
  final clave = _claveCacheJugadores(equipoId);

  if (!forzarRed) {
    final cacheJson = prefs.getString(clave);
    if (cacheJson != null && cacheJson.isNotEmpty) {
      try {
        final listaRaw = jsonDecode(cacheJson) as List<dynamic>;
        final jugadoresCache = listaRaw
            .map((e) => Jugador.fromJson(e as Map<String, dynamic>))
            .toList();
        if (jugadoresCache.isNotEmpty) {
          unawaited(_actualizarCacheJugadoresSilencioso(equipoId, activos));
          return jugadoresCache;
        }
      } catch (_) {
        // Si el caché estuviese corrupto, continuamos a red
      }
    }
  }

  try {
    final r = await cliente
        .get(
          '/deportivo/equipos/$equipoId/jugadores',
          params: {'activos': '$activos', 'orden': 'dorsal'},
        )
        .timeout(const Duration(milliseconds: 2000));

    if (r is List) {
      final jugadores =
          r.map((item) => Jugador.fromJson(item as Map<String, dynamic>)).toList();
      await prefs.setString(clave, jsonEncode(r));
      return jugadores;
    }
    return [];
  } catch (e) {
    final cacheJson = prefs.getString(clave);
    if (cacheJson != null && cacheJson.isNotEmpty) {
      try {
        final listaRaw = jsonDecode(cacheJson) as List<dynamic>;
        return listaRaw
            .map((item) => Jugador.fromJson(item as Map<String, dynamic>))
            .toList();
      } catch (_) {}
    }
    rethrow;
  }
}

/// CU-11 (Criterio 1 y 2): registra un jugador nuevo en el plantel de
/// [equipoId]. La altura en cm es obligatoria; el peso es opcional. Tras
/// persistir en el backend, actualiza el caché local para que la lista y la
/// búsqueda reflejen el alta sin esperar a la próxima sincronización.
Future<Jugador> crearJugador(
  int equipoId, {
  required String nombre,
  required String apellido,
  required int dorsal,
  required String posicion,
  required String pieHabil,
  required int alturaCm,
  double? pesoKg,
}) async {
  final r = await cliente.post('/deportivo/jugadores', cuerpo: {
    'equipo_id': equipoId,
    'nombre': nombre,
    'apellido': apellido,
    'dorsal': dorsal,
    'posicion': posicion,
    'pie_habil': pieHabil,
    'altura_cm': alturaCm,
    'peso_kg': pesoKg,
  }) as Map<String, dynamic>;

  final jugador = Jugador.fromJson(r);

  final prefs = await SharedPreferences.getInstance();
  final clave = _claveCacheJugadores(equipoId);
  final cacheJson = prefs.getString(clave);
  if (cacheJson != null && cacheJson.isNotEmpty) {
    try {
      final lista = (jsonDecode(cacheJson) as List<dynamic>)
          .cast<Map<String, dynamic>>()
        ..add(r);
      await prefs.setString(clave, jsonEncode(lista));
    } catch (_) {
      // Si el caché estuviese corrupto, no bloqueamos el alta por eso.
    }
  }

  return jugador;
}

Future<void> _actualizarCacheJugadoresSilencioso(
  int equipoId,
  bool activos,
) async {
  try {
    final r = await cliente
        .get(
          '/deportivo/equipos/$equipoId/jugadores',
          params: {'activos': '$activos', 'orden': 'dorsal'},
        )
        .timeout(const Duration(milliseconds: 2000));
    if (r is List) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_claveCacheJugadores(equipoId), jsonEncode(r));
    }
  } catch (_) {
    // En actualización silenciosa ignoramos errores de red
  }
}

/// Credenciales de la cuenta demo. Por defecto coinciden con el seed de
/// desarrollo del backend (ver docker-compose.yml / scripts/seed_dev.py):
///   flutter run --dart-define=DEMO_EMAIL=otro@correo.com --dart-define=DEMO_PASSWORD=OtraClave
const String _demoEmail = String.fromEnvironment(
  'DEMO_EMAIL',
  defaultValue: 'admin@club-demo.example.com',
);
const String _demoPassword = String.fromEnvironment(
  'DEMO_PASSWORD',
  defaultValue: 'Demo-Area-Tecnica-2026',
);

/// Inicia sesión rápida con la cuenta demo de prueba si la app no tiene token
Future<void> conectarSesionDemo() async {
  const creds = {
    'email': _demoEmail,
    'password': _demoPassword,
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
