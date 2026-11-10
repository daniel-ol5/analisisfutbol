/// Estado del resumen de métricas  —  CU-43 (T-081).
///
/// Sin widgets: junta la carga inicial por REST y los mensajes del canal /vivo.
///
/// - Posesión: SIEMPRE la del servidor (REST al abrir, luego el mensaje
///   `posesion`). Nunca la estimación local de `ServicioPartidoVivo`.
/// - Jugadores: REST al abrir, luego `metricas_jugadores` (cada 60 s).
/// - Intervalos: uno con el mismo `minuto_desde` reemplaza al anterior.
/// - Partido finalizado: solo REST, sin WebSocket.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'modelos.dart';
import 'resumen_api.dart';
import 'resumen_modelos.dart';
import 'servicio_vivo.dart';

/// Lo que el resumen necesita del canal en vivo. Las pruebas usan una fuente falsa.
abstract interface class FuenteVivo implements Listenable {
  EstadoConexion get estadoConexion;
  Stream<Map<String, dynamic>> get mensajes;
  void conectar(int partidoId);
  void dispose();
}

/// Adaptador sobre el servicio de T-080 (reconexión y latido incluidos).
class FuenteServicioVivo implements FuenteVivo {
  FuenteServicioVivo([ServicioPartidoVivo? servicio])
      : servicio = servicio ?? ServicioPartidoVivo();
  final ServicioPartidoVivo servicio;

  @override
  EstadoConexion get estadoConexion => servicio.estadoConexion;
  @override
  Stream<Map<String, dynamic>> get mensajes => servicio.mensajesAnalisis;
  @override
  void conectar(int partidoId) => servicio.conectar(partidoId);
  @override
  void dispose() => servicio.dispose();
  @override
  void addListener(VoidCallback listener) => servicio.addListener(listener);
  @override
  void removeListener(VoidCallback listener) =>
      servicio.removeListener(listener);
}

class ResumenEstado extends ChangeNotifier {
  ResumenEstado({
    required this.partidoId,
    this.api = const ResumenApi(),
    FuenteVivo Function()? crearFuente,
    DateTime Function()? ahora,
  })  : _crearFuente = crearFuente ?? FuenteServicioVivo.new,
        _ahora = ahora ?? DateTime.now;

  final int partidoId;
  final ResumenApi api;
  final FuenteVivo Function() _crearFuente;
  final DateTime Function() _ahora;

  FuenteVivo? _fuente;
  StreamSubscription<Map<String, dynamic>>? _suscripcion;
  bool _cerrado = false;

  bool cargando = true;
  String? error;
  PartidoInfo? partido;
  int golesFavor = 0;
  int golesContra = 0;
  int? minuto;

  Posesion posesion = Posesion.vacia;

  /// Segunda lectura de la posesión: «Últimos 5 min» (REST) o el intervalo en curso (vivo).
  Posesion? posesionReciente;
  String etiquetaReciente = 'Últimos 5 min';

  double distanciaLocalM = 0;
  double distanciaVisitanteM = 0;
  List<MetricaJugador> topLocal = const [];
  List<MetricaJugador> topVisitante = const [];
  final List<IntervaloMetricas> intervalos = [];

  DateTime? ultimaActualizacion;

  bool get finalizado => partido?.estado == 'FINALIZADO';
  bool get enVivo => _fuente != null;

  EstadoConexion get conexion =>
      _fuente?.estadoConexion ?? EstadoConexion.desconectado;

  /// En vivo, todo lo que no sea «conectado» se muestra como sin conexión.
  bool get sinConexion => enVivo && conexion != EstadoConexion.conectado;

  Future<void> iniciar() async {
    await recargar();
    if (_cerrado || partido == null || finalizado) return;
    final fuente = _crearFuente();
    _fuente = fuente;
    fuente.addListener(_alCambiarConexion);
    _suscripcion = fuente.mensajes.listen(procesarMensaje);
    fuente.conectar(partidoId);
    notifyListeners();
  }

  /// Carga (o recarga) todo por REST.
  Future<void> recargar() async {
    try {
      final datos = await Future.wait([
        api.partido(partidoId),
        api.metricas(partidoId),
        api.jugadores(partidoId, 'LOCAL'),
        api.jugadores(partidoId, 'VISITANTE'),
        api.intervalos(partidoId),
      ]);
      if (_cerrado) return;
      final p = datos[0] as PartidoInfo;
      final m = datos[1] as MetricasPartido;
      partido = p;
      golesFavor = p.golesFavor;
      golesContra = p.golesContra;
      minuto ??= p.minutoActual;
      posesion = m.posesion;
      posesionReciente = m.posesionUltimos;
      etiquetaReciente = 'Últimos 5 min';
      distanciaLocalM = m.local.distanciaM;
      distanciaVisitanteM = m.visitante.distanciaM;
      topLocal = _top3(datos[2] as List<MetricaJugador>);
      topVisitante = _top3(datos[3] as List<MetricaJugador>);
      intervalos
        ..clear()
        ..addAll(datos[4] as List<IntervaloMetricas>);
      error = null;
      ultimaActualizacion = _ahora();
    } catch (e) {
      error = 'No se pudieron cargar las métricas. $e';
    } finally {
      cargando = false;
      if (!_cerrado) notifyListeners();
    }
  }

  static List<MetricaJugador> _top3(List<MetricaJugador> lista) =>
      lista.take(3).toList();

  void _alCambiarConexion() {
    if (!_cerrado) notifyListeners();
  }

  /// Aplica un mensaje del canal /vivo. Público para poder probarlo directo.
  void procesarMensaje(Map<String, dynamic> mensaje) {
    final datos = mensaje['datos'];
    if (datos is! Map<String, dynamic>) return;
    switch (mensaje['tipo']) {
      case 'posesion':
        final acumulado = datos['acumulado'];
        if (acumulado is Map<String, dynamic>) {
          posesion = Posesion.desdePct(acumulado);
        }
        final intervalo = datos['intervalo'];
        if (intervalo is Map<String, dynamic>) {
          posesionReciente = Posesion.desdePct(intervalo);
          etiquetaReciente =
              'Min ${intervalo['minuto_desde']}–${intervalo['minuto_hasta']}';
        }
        final t = datos['t'];
        if (t is num) minuto = t ~/ 60;
      case 'metricas_jugadores':
        topLocal = _top3(MetricaJugador.lista(datos['local']));
        topVisitante = _top3(MetricaJugador.lista(datos['visitante']));
        _refrescarDistancias();
      case 'intervalo':
        reemplazarIntervalo(IntervaloMetricas.fromJson(datos));
      case 'estado':
        golesFavor = (datos['goles_favor'] as num?)?.toInt() ?? golesFavor;
        golesContra = (datos['goles_contra'] as num?)?.toInt() ?? golesContra;
        minuto = (datos['minuto'] as num?)?.toInt() ?? minuto;
      default:
        return;
    }
    ultimaActualizacion = _ahora();
    if (!_cerrado) notifyListeners();
  }

  /// Un intervalo con el mismo `minuto_desde` reemplaza al anterior (sprint confirmado tarde).
  void reemplazarIntervalo(IntervaloMetricas nuevo) {
    final i = intervalos.indexWhere((x) => x.minutoDesde == nuevo.minutoDesde);
    if (i >= 0) {
      intervalos[i] = nuevo;
    } else {
      intervalos
        ..add(nuevo)
        ..sort((a, b) => a.minutoDesde.compareTo(b.minutoDesde));
    }
  }

  /// La distancia por equipo no viaja por el WebSocket: se pide junto con
  /// cada `metricas_jugadores` (una vez por minuto). La posesión NO se toca:
  /// la del mensaje `posesion` es más reciente.
  Future<void> _refrescarDistancias() async {
    try {
      final m = await api.metricas(partidoId);
      if (_cerrado) return;
      distanciaLocalM = m.local.distanciaM;
      distanciaVisitanteM = m.visitante.distanciaM;
      notifyListeners();
    } catch (_) {
      // Sin red: quedan los últimos valores; el indicador ya lo avisa.
    }
  }

  @override
  void dispose() {
    _cerrado = true;
    _suscripcion?.cancel();
    _fuente?.removeListener(_alCambiarConexion);
    _fuente?.dispose();
    super.dispose();
  }
}
