/// Servicio de conexión en tiempo real con WebSocket  —  CU-40 (T-080).
///
/// Implementa:
/// - Handshake inicial autenticado por Bearer token (tipo: "auth")
/// - Latido / Heartbeat cada 20 segundos (tipo: "ping")
/// - Reintento automático con reconexión persistente ante caídas de red
/// - Estimador continuo de posesión rodante
///
/// Criterio de aceptación:
/// Tras cortar la red 2 minutos la app se reconecta sola y recupera el estado.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../shared/api/almacenamiento.dart';
import '../../shared/api/entorno.dart';
import 'modelos.dart';

class ServicioPartidoVivo extends ChangeNotifier {
  int? _partidoId;
  WebSocketChannel? _canal;
  Timer? _latidoTimer;
  Timer? _reintentoTimer;
  bool _disposed = false;
  bool _activo = false;

  EstadoConexion _estadoConexion = EstadoConexion.desconectado;
  MensajeWorker? _ultimoMensaje;
  String? _error;

  double _posesionLocalPct = 50.0;
  double _posesionVisitantePct = 50.0;
  final List<PuntoTrayectoria> _estelaBalon = [];
  final List<EquipoDetectado> _posesionMuestras = [];

  // Parámetros de reconexión con respaldo exponencial
  int _reintentosConsecutivos = 0;
  static const int _reintentoBaseSegundos = 2;
  static const int _reintentoMaxSegundos = 10;

  EstadoConexion get estadoConexion => _estadoConexion;
  MensajeWorker? get ultimoMensaje => _ultimoMensaje;
  String? get error => _error;
  double get posesionLocalPct => _posesionLocalPct;
  double get posesionVisitantePct => _posesionVisitantePct;
  List<PuntoTrayectoria> get estelaBalon => List.unmodifiable(_estelaBalon);
  int? get partidoId => _partidoId;

  /// Inicia la escucha en vivo para el partido indicado.
  void conectar(int partidoId) {
    if (_partidoId == partidoId && _estadoConexion == EstadoConexion.conectado) {
      return;
    }
    _partidoId = partidoId;
    _activo = true;
    _reintentosConsecutivos = 0;
    _limpiarConexion();
    _iniciarConexion();
  }

  /// Desconecta activamente el canal y detiene reintentos.
  void desconectar() {
    _activo = false;
    _partidoId = null;
    _limpiarConexion();
    _actualizarEstado(EstadoConexion.desconectado);
  }

  /// Fuerza un intento inmediato de reconexión.
  void forzarReconexion() {
    if (_partidoId == null) return;
    _limpiarConexion();
    _reintentosConsecutivos = 0;
    _iniciarConexion();
  }

  void _actualizarEstado(EstadoConexion nuevoEstado, [String? nuevoError]) {
    _estadoConexion = nuevoEstado;
    _error = nuevoError;
    if (!_disposed) {
      notifyListeners();
    }
  }

  Future<void> _iniciarConexion() async {
    if (!_activo || _disposed || _partidoId == null) return;

    _actualizarEstado(
      _reintentosConsecutivos == 0
          ? EstadoConexion.conectando
          : EstadoConexion.reconectando,
    );

    try {
      final token = await Almacenamiento.leerToken();
      if (token == null || token.isEmpty) {
        _actualizarEstado(
          EstadoConexion.error,
          'Sesión no iniciada. Inicie sesión para ver el partido en vivo.',
        );
        _programarReintento();
        return;
      }

      final uriApi = Uri.parse(urlApi);
      final esquemaWs = uriApi.scheme == 'https' ? 'wss' : 'ws';
      final basePath = uriApi.path.endsWith('/')
          ? uriApi.path.substring(0, uriApi.path.length - 1)
          : uriApi.path;
      final urlWs = uriApi
          .replace(
            scheme: esquemaWs,
            path: '$basePath/partido/$_partidoId/vivo',
          )
          .toString();

      final wsUri = Uri.parse(urlWs);
      final canal = WebSocketChannel.connect(wsUri);
      _canal = canal;

      // 1. Handshake inicial obligatorio: enviar token antes de 5 segundos
      canal.sink.add(jsonEncode({
        'tipo': 'auth',
        'token': token,
      }));

      // 2. Iniciar timer de latidos / heartbeat (cada 20s)
      _iniciarLatido();

      // 3. Escuchar flujo de mensajes
      canal.stream.listen(
        (mensajeRaw) {
          _alRecibirMensaje(mensajeRaw);
        },
        onError: (err) {
          _alCaerConexion('Error en la conexión WebSocket: $err');
        },
        onDone: () {
          _alCaerConexion('Conexión cerrada por el servidor o la red.');
        },
        cancelOnError: true,
      );
    } catch (e) {
      _alCaerConexion('No se pudo establecer la conexión: $e');
    }
  }

  void _alRecibirMensaje(dynamic mensajeRaw) {
    try {
      final texto = mensajeRaw is String ? mensajeRaw : utf8.decode(mensajeRaw);
      final dynamic datos = jsonDecode(texto);

      if (datos is! Map<String, dynamic>) return;

      final tipo = datos['tipo'] as String?;

      if (tipo == 'listo') {
        _reintentosConsecutivos = 0;
        _actualizarEstado(EstadoConexion.conectado, null);
        return;
      }

      if (tipo == 'pong') {
        // Latido confirmado
        return;
      }

      // Procesar mensaje con datos de posiciones de tracking
      Map<String, dynamic>? cuerpoWorker;
      if (tipo == 'posiciones' && datos['datos'] is Map<String, dynamic>) {
        cuerpoWorker = datos['datos'] as Map<String, dynamic>;
      } else if (datos.containsKey('jugadores')) {
        cuerpoWorker = datos;
      }

      if (cuerpoWorker != null) {
        _procesarFrame(cuerpoWorker);
      }
    } catch (_) {
      // Ignorar mensajes con formato imprevisto para robustez
    }
  }

  void _procesarFrame(Map<String, dynamic> raw) {
    try {
      final frame = MensajeWorker.fromJson(raw);
      _ultimoMensaje = frame;

      // Actualizar estela del balón
      if (frame.balon != null) {
        _estelaBalon.add(PuntoTrayectoria(
          x: frame.balon!.x,
          y: frame.balon!.y,
          t: frame.t,
        ));
        if (_estelaBalon.length > 15) {
          _estelaBalon.removeAt(0);
        }

        // Estimar posesión por proximidad al balón (< 2.2 metros)
        EquipoDetectado? equipoCercano;
        double minDistSq = 2.2 * 2.2;
        for (final j in frame.jugadores) {
          if (j.equipo == EquipoDetectado.local ||
              j.equipo == EquipoDetectado.visitante) {
            final dx = j.x - frame.balon!.x;
            final dy = j.y - frame.balon!.y;
            final dSq = dx * dx + dy * dy;
            if (dSq < minDistSq) {
              minDistSq = dSq;
              equipoCercano = j.equipo;
            }
          }
        }

        if (equipoCercano != null) {
          _posesionMuestras.add(equipoCercano);
          if (_posesionMuestras.length > 60) {
            _posesionMuestras.removeAt(0);
          }

          int locales = 0;
          int visitantes = 0;
          for (final m in _posesionMuestras) {
            if (m == EquipoDetectado.local) locales++;
            if (m == EquipoDetectado.visitante) visitantes++;
          }
          final total = locales + visitantes;
          if (total > 0) {
            _posesionLocalPct = (locales / total) * 100.0;
            _posesionVisitantePct = (visitantes / total) * 100.0;
          }
        }
      }

      if (_estadoConexion != EstadoConexion.conectado) {
        _actualizarEstado(EstadoConexion.conectado, null);
      } else if (!_disposed) {
        notifyListeners();
      }
    } catch (_) {}
  }

  void _iniciarLatido() {
    _latidoTimer?.cancel();
    _latidoTimer = Timer.periodic(const Duration(seconds: 20), (timer) {
      if (_estadoConexion == EstadoConexion.conectado && _canal != null) {
        try {
          _canal!.sink.add(jsonEncode({'tipo': 'ping'}));
        } catch (_) {}
      }
    });
  }

  void _alCaerConexion(String motivo) {
    _limpiarCanal();
    if (!_activo || _disposed) return;

    _reintentosConsecutivos++;
    _actualizarEstado(
      EstadoConexion.reconectando,
      'Conexión interrumpida. Reintentando automáticamente...',
    );
    _programarReintento();
  }

  void _programarReintento() {
    _reintentoTimer?.cancel();
    if (!_activo || _disposed) return;

    // Respaldo exponencial: 2s, 4s, 8s, capped at 10s
    final retrasoSegundos = math.min(
      _reintentoMaxSegundos,
      _reintentoBaseSegundos * math.pow(1.5, _reintentosConsecutivos - 1).round(),
    );

    _reintentoTimer = Timer(Duration(seconds: retrasoSegundos), () {
      if (_activo && !_disposed) {
        _iniciarConexion();
      }
    });
  }

  void _limpiarCanal() {
    _latidoTimer?.cancel();
    _latidoTimer = null;
    try {
      _canal?.sink.close();
    } catch (_) {}
    _canal = null;
  }

  void _limpiarConexion() {
    _limpiarCanal();
    _reintentoTimer?.cancel();
    _reintentoTimer = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _activo = false;
    _limpiarConexion();
    super.dispose();
  }
}

