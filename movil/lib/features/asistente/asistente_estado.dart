/// Estado de la pantalla del asistente: progreso del club y chat.
///
/// El historial del chat vive solo en memoria mientras la app está abierta;
/// no se guarda en el teléfono.
library;

import 'package:flutter/foundation.dart';

import '../../shared/api/cliente.dart';
import 'asistente_api.dart';
import 'asistente_modelos.dart';

const mensajeSinConexion =
    'Sin conexión. Revisa tu señal: cuando vuelva, toca «Reintentar».';

class AsistenteEstado extends ChangeNotifier {
  AsistenteEstado({this.api = const AsistenteApi(), this.pantalla = ''});

  final AsistenteApi api;
  final String pantalla;

  /// Conversación de esta ejecución de la app (compartida entre aperturas).
  static final List<MensajeChat> _historialSesion = [];

  /// Para pruebas y al cerrar sesión.
  static void borrarHistorial() => _historialSesion.clear();

  List<MensajeChat> get mensajes => List.unmodifiable(_historialSesion);

  Progreso? progreso;
  bool cargando = true;
  String? errorProgreso;
  bool sinConexion = false;

  bool enviando = false;
  String? errorEnvio;
  bool _cerrado = false;

  bool get chatActivo => progreso?.asistenteActivo ?? true;

  Future<void> cargarProgreso() async {
    cargando = true;
    errorProgreso = null;
    _avisar();
    try {
      progreso = await api.progreso();
      sinConexion = false;
    } on ErrorApi catch (e) {
      errorProgreso = e.detalle;
    } catch (_) {
      // Sin respuesta del servidor: red caída o tiempo agotado.
      sinConexion = true;
    }
    cargando = false;
    _avisar();
  }

  /// Envía la pregunta. Devuelve false si no se pudo (vacía o ya enviando).
  Future<bool> enviar(String texto) async {
    final pregunta = texto.trim();
    if (pregunta.isEmpty || enviando) return false;
    final historial = List<MensajeChat>.of(_historialSesion);
    _historialSesion.add(MensajeChat(pregunta, deUsuario: true));
    enviando = true;
    errorEnvio = null;
    _avisar();
    try {
      final r = await api.preguntar(
        pregunta.length > largoMaxPregunta ? pregunta.substring(0, largoMaxPregunta) : pregunta,
        pantalla: pantalla,
        historial: historial,
      );
      _historialSesion.add(MensajeChat(r.texto, deUsuario: false, acciones: r.acciones));
      sinConexion = false;
    } on ErrorApi catch (e) {
      errorEnvio = e.detalle;
    } catch (_) {
      sinConexion = true;
      errorEnvio = mensajeSinConexion;
    }
    enviando = false;
    _avisar();
    return true;
  }

  void _avisar() {
    if (!_cerrado) notifyListeners();
  }

  @override
  void dispose() {
    _cerrado = true;
    super.dispose();
  }
}
