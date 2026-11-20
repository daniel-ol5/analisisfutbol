/// Notificaciones push en el móvil  —  CU-53 (T-096).
///
/// Criterio de T-096: la notificación llega con la app cerrada y, al tocarla,
/// abre la recomendación correcta. El envío lo hace el backend (T-087, Susana):
/// solo para recomendaciones CRITICAS del club. Ver docs/NOTIFICACIONES-PUSH.md.
///
/// Sin `google-services.json` en el repositorio: Firebase se configura con
/// cuatro valores al compilar, igual que `API_URL`:
///
///     flutter build apk --release \
///       --dart-define=API_URL=https://<servidor>/api \
///       --dart-define=FIREBASE_API_KEY=... \
///       --dart-define=FIREBASE_APP_ID=... \
///       --dart-define=FIREBASE_MESSAGING_SENDER_ID=... \
///       --dart-define=FIREBASE_PROJECT_ID=...
///
/// Sin esos valores (pruebas, CI, web, compañeros sin Firebase) el push queda
/// apagado y el resto de la app funciona igual.
library;

import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/cliente.dart';

// ---------------- Configuración ----------------

class ConfigPush {
  static const apiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const appId = String.fromEnvironment('FIREBASE_APP_ID');
  static const senderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');
  static const projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');

  static bool get completa =>
      apiKey.isNotEmpty && appId.isNotEmpty && senderId.isNotEmpty && projectId.isNotEmpty;

  /// Solo Android: es la plataforma del proyecto (T-097 prueba en Android).
  static bool get disponible =>
      completa && !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
}

// ---------------- Destino al tocar la notificación ----------------

/// Payload de T-087: {"tipo": "recomendacion_tactica", "partido_id": "10",
/// "recomendacion_id": "42", ...}. Devuelve la ruta de la app, o null si no es
/// una notificación que se sepa abrir.
String? rutaDeNotificacion(Map<String, dynamic> datos) {
  final tipo = datos['tipo'];
  if (tipo == 'recomendacion_tactica') {
    final partido = int.tryParse('${datos['partido_id']}');
    if (partido == null) return null;
    final recomendacion = int.tryParse('${datos['recomendacion_id']}');
    return recomendacion == null
        ? '/partidos/$partido/recomendaciones'
        : '/partidos/$partido/recomendaciones?recomendacion=$recomendacion';
  }
  if (tipo == 'partido_programado') return '/partidos';
  if (tipo == 'video_subido') return '/analisis';
  if (tipo == 'video_procesado') {
    final partido = int.tryParse('${datos['partido_id']}');
    return partido == null ? '/analisis' : '/partidos/$partido/resumen';
  }
  return null;
}

// ---------------- Lo que se necesita de Firebase ----------------

/// Un mensaje recibido: sus datos y, si trae, el título visible.
typedef MensajePush = ({Map<String, dynamic> datos, String? titulo});

/// Lo que el servicio usa de Firebase Messaging. Las pruebas pasan uno falso.
abstract interface class Mensajeria {
  Future<bool> pedirPermiso();
  Future<String?> token();
  Stream<String> get tokenRenovado;

  /// Llegó con la app abierta (Android no muestra nada solo: lo avisa la app).
  Stream<MensajePush> get enPrimerPlano;

  /// Se tocó la notificación con la app en segundo plano.
  Stream<MensajePush> get tocadas;

  /// La notificación que abrió la app cuando estaba cerrada, si fue así.
  Future<MensajePush?> tocadaAlAbrir();
}

class MensajeriaFirebase implements Mensajeria {
  final FirebaseMessaging _fcm = FirebaseMessaging.instance;

  static MensajePush _de(RemoteMessage m) => (datos: m.data, titulo: m.notification?.title);

  @override
  Future<bool> pedirPermiso() async {
    final ajustes = await _fcm.requestPermission();
    return ajustes.authorizationStatus == AuthorizationStatus.authorized ||
        ajustes.authorizationStatus == AuthorizationStatus.provisional;
  }

  // Se usa el token FCM clásico a propósito: el backend (T-087) envía con
  // `messaging.MulticastMessage(tokens=...)` de Firebase Admin, que espera ese
  // token. `register()`/`onRegistered` entregan un ID de instalación para el
  // envío directo, que ese backend no sabe usar: los push dejarían de llegar.
  @override
  // ignore: deprecated_member_use
  Future<String?> token() => _fcm.getToken();

  @override
  // ignore: deprecated_member_use
  Stream<String> get tokenRenovado => _fcm.onTokenRefresh;

  @override
  Stream<MensajePush> get enPrimerPlano => FirebaseMessaging.onMessage.map(_de);

  @override
  Stream<MensajePush> get tocadas => FirebaseMessaging.onMessageOpenedApp.map(_de);

  @override
  Future<MensajePush?> tocadaAlAbrir() async {
    final inicial = await _fcm.getInitialMessage();
    return inicial == null ? null : _de(inicial);
  }
}

// ---------------- Servicio ----------------

typedef RegistrarDispositivo = Future<void> Function(
    String instalacionId, String token, String plataforma);

/// POST /asistencia/dispositivos (T-087). Idempotente: sirve también para rotar el token.
Future<void> registrarEnBackend(String instalacionId, String token, String plataforma) =>
    cliente.post('/asistencia/dispositivos', cuerpo: {
      'instalacion_id': instalacionId,
      'token': token,
      'plataforma': plataforma,
    });

const _claveInstalacion = 'push_instalacion_id';

/// Identificador estable de esta instalación (sobrevive a cerrar sesión).
Future<String> instalacionLocal() async {
  final prefs = await SharedPreferences.getInstance();
  final guardado = prefs.getString(_claveInstalacion);
  if (guardado != null) return guardado;
  final nuevo = const Uuid().v4();
  await prefs.setString(_claveInstalacion, nuevo);
  return nuevo;
}

class ServicioPush {
  ServicioPush({
    required this.mensajeria,
    required this.navegar,
    this.avisar,
    RegistrarDispositivo? registrar,
    Future<String> Function()? instalacion,
  })  : _registrar = registrar ?? registrarEnBackend,
        _instalacion = instalacion ?? instalacionLocal;

  final Mensajeria mensajeria;

  /// Abre una ruta de la app (en producción, `router.go`).
  final void Function(String ruta) navegar;

  /// Muestra un aviso con la app abierta; `ruta` es adónde lleva "Ver".
  final void Function(String texto, String ruta)? avisar;

  final RegistrarDispositivo _registrar;
  final Future<String> Function() _instalacion;
  final List<StreamSubscription<Object>> _suscripciones = [];
  bool _escuchandoToken = false;

  /// Al arrancar la app: escucha los toques y abre la que despertó a la app cerrada.
  Future<void> iniciar() async {
    _suscripciones
      ..add(mensajeria.tocadas.listen(_abrir))
      ..add(mensajeria.enPrimerPlano.listen(_alRecibir));
    final inicial = await mensajeria.tocadaAlAbrir();
    if (inicial != null) _abrir(inicial);
  }

  /// Con sesión iniciada: permiso, token y registro en el backend.
  /// Se puede llamar más de una vez (el backend es idempotente).
  Future<void> registrar() async {
    try {
      if (!await mensajeria.pedirPermiso()) return;
      final token = await mensajeria.token();
      if (token == null || token.isEmpty) return;
      await _enviar(token);
      if (!_escuchandoToken) {
        _escuchandoToken = true;
        _suscripciones.add(mensajeria.tokenRenovado.listen((t) => unawaited(_enviar(t))));
      }
    } catch (e) {
      // Sin red o sin sesión: se reintenta la próxima vez que se abra la app.
      debugPrint('No se pudo registrar el dispositivo para push: $e');
    }
  }

  Future<void> _enviar(String token) async =>
      _registrar(await _instalacion(), token, 'ANDROID');

  void _abrir(MensajePush mensaje) {
    final ruta = rutaDeNotificacion(mensaje.datos);
    if (ruta != null) navegar(ruta);
  }

  void _alRecibir(MensajePush mensaje) {
    final ruta = rutaDeNotificacion(mensaje.datos);
    if (ruta == null) return;
    avisar?.call(mensaje.titulo ?? 'Nueva recomendación crítica', ruta);
  }

  void dispose() {
    for (final s in _suscripciones) {
      s.cancel();
    }
  }
}

/// El servicio de la app, o null si el push está apagado.
ServicioPush? servicioPush;

/// Desde `main`: inicializa Firebase y el servicio solo si hay configuración.
Future<void> iniciarPush({
  required void Function(String ruta) navegar,
  required void Function(String texto, String ruta) avisar,
}) async {
  if (!ConfigPush.disponible) return;
  try {
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: ConfigPush.apiKey,
        appId: ConfigPush.appId,
        messagingSenderId: ConfigPush.senderId,
        projectId: ConfigPush.projectId,
      ),
    );
    final servicio = ServicioPush(
      mensajeria: MensajeriaFirebase(),
      navegar: navegar,
      avisar: avisar,
    );
    await servicio.iniciar();
    servicioPush = servicio;
    // Si ya había sesión, el marco pudo montarse antes de terminar esto.
    if (await Almacenamiento.haySesion()) unawaited(servicio.registrar());
  } catch (e) {
    // Un problema de Firebase no puede impedir que la app arranque.
    debugPrint('Push desactivado: $e');
  }
}
