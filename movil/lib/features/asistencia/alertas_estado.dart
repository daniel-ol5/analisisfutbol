/// Estado de las alertas de un partido en vivo  —  CU-52 (T-095).
///
/// Sin widgets. Consulta el backend cada [AlertasEstado.intervaloPorDefecto]:
/// las alertas se calculan con bloques de 5 minutos y con las tarjetas que
/// carga el asistente, así que no hace falta más seguido.
///
/// - Red inestable (T-097): si una consulta falla se conservan las últimas
///   alertas y se marca `sinConexion`; la siguiente consulta lo corrige.
/// - "Entendido": el DT descarta una alerta y deja de verla. Si la situación
///   desaparece y vuelve a darse (otra vez fatiga del mismo jugador), reaparece.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'alertas_api.dart' as api;
import 'alertas_modelos.dart';

class AlertasEstado extends ChangeNotifier {
  AlertasEstado({
    required this.partidoId,
    api.ObtenerAlertas? obtener,
    this.intervalo = intervaloPorDefecto,
  }) : _obtener = obtener ?? api.obtenerAlertas;

  static const intervaloPorDefecto = Duration(seconds: 15);

  final int partidoId;
  final Duration intervalo;
  final api.ObtenerAlertas _obtener;

  Timer? _timer;
  bool _consultando = false;
  bool _cerrado = false;
  final Set<String> _descartadas = {};
  Set<String> _anteriores = {};
  List<Alerta> _recibidas = const [];

  bool cargando = true;
  bool sinConexion = false;

  /// Claves que aparecieron en la última consulta (para destacarlas).
  Set<String> nuevas = const {};

  /// Vigentes y no descartadas, en el orden del backend (más urgente primero).
  List<Alerta> get alertas =>
      _recibidas.where((a) => !_descartadas.contains(a.clave)).toList();

  void iniciar() {
    unawaited(consultar());
    _timer ??= Timer.periodic(intervalo, (_) => unawaited(consultar()));
  }

  Future<void> consultar() async {
    if (_consultando || _cerrado) return;
    _consultando = true;
    try {
      final recibidas = await _obtener(partidoId);
      if (_cerrado) return;
      final claves = {for (final a in recibidas) a.clave};
      // Una situación que ya no está deja de estar descartada: si vuelve, se avisa.
      _descartadas.retainWhere(claves.contains);
      nuevas = claves.difference(_anteriores);
      _anteriores = claves;
      _recibidas = recibidas;
      sinConexion = false;
    } catch (_) {
      if (_cerrado) return;
      sinConexion = true;
    } finally {
      _consultando = false;
      if (!_cerrado) {
        cargando = false;
        notifyListeners();
      }
    }
  }

  void descartar(Alerta alerta) {
    if (_descartadas.add(alerta.clave)) notifyListeners();
  }

  @override
  void dispose() {
    _cerrado = true;
    _timer?.cancel();
    super.dispose();
  }
}
