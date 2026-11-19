/// Estado de las recomendaciones en vivo  —  CU-50 (T-094).
///
/// Carga por REST al abrir y luego se actualiza con el mensaje `recomendacion`
/// del canal /vivo (a través de `ServicioPartidoVivo`, T-080). Nunca hay más de
/// 3 a la vez: una nueva de mayor prioridad desplaza a la de menor.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../shared/api/cliente.dart';
import '../analisis/modelos.dart';
import '../analisis/resumen_estado.dart';
import 'recomendaciones_api.dart';
import 'recomendaciones_modelos.dart';

class RecomendacionesEstado extends ChangeNotifier {
  RecomendacionesEstado({
    required this.partidoId,
    this.api = const RecomendacionesApi(),
    FuenteVivo Function()? crearFuente,
    DateTime Function()? ahora,
  })  : _crearFuente = crearFuente ?? FuenteServicioVivo.new,
        _ahora = ahora ?? DateTime.now;

  final int partidoId;
  final RecomendacionesApi api;
  final FuenteVivo Function() _crearFuente;
  final DateTime Function() _ahora;

  FuenteVivo? _fuente;
  StreamSubscription<Map<String, dynamic>>? _suscripcion;
  final Set<int> _marcadas = {};
  bool _cerrado = false;

  bool cargando = true;
  String? error;

  /// T-095: valoraciones hechas en esta pantalla (la tarjeta queda a la vista
  /// con lo elegido aunque "No útil" o "Aplicada" la saquen de las activas).
  final Map<int, OpcionValoracion> valoradas = {};

  /// T-095: la que se está enviando, para no permitir dos toques.
  int? valorando;

  /// T-095: por qué no se pudo valorar, por recomendación.
  final Map<int, String> erroresValoracion = {};
  List<Recomendacion> activas = const [];
  DateTime? ultimaActualizacion;

  EstadoConexion get conexion =>
      _fuente?.estadoConexion ?? EstadoConexion.desconectado;

  bool get sinConexion => _fuente != null && conexion != EstadoConexion.conectado;

  Future<void> iniciar() async {
    await recargar();
    if (_cerrado) return;
    final fuente = _crearFuente();
    _fuente = fuente;
    fuente.addListener(_alCambiarConexion);
    _suscripcion = fuente.mensajes.listen(procesarMensaje);
    fuente.conectar(partidoId);
    notifyListeners();
  }

  Future<void> recargar() async {
    try {
      final lista = await api.listar(partidoId);
      if (_cerrado) return;
      activas = ordenarActivas(lista);
      error = null;
      ultimaActualizacion = _ahora();
      _marcarVistas();
    } catch (e) {
      error = 'No se pudieron cargar las recomendaciones.';
    } finally {
      cargando = false;
      if (!_cerrado) notifyListeners();
    }
  }

  EstadoConexion? _conexionPrevia;

  void _alCambiarConexion() {
    final actual = conexion;
    // Al volver la conexión se recarga: pudo haber recomendaciones mientras tanto.
    if (_conexionPrevia != null &&
        _conexionPrevia != EstadoConexion.conectado &&
        actual == EstadoConexion.conectado) {
      recargar();
    }
    _conexionPrevia = actual;
    if (!_cerrado) notifyListeners();
  }

  /// Aplica un mensaje del canal /vivo. Público para probarlo directo.
  void procesarMensaje(Map<String, dynamic> mensaje) {
    if (mensaje['tipo'] != 'recomendacion') return;
    final datos = mensaje['datos'];
    if (!Recomendacion.valida(datos)) return;
    final nueva = Recomendacion.fromJson(datos as Map<String, dynamic>);
    if (nueva.partidoId != partidoId) return;
    activas = incorporar(activas, nueva);
    ultimaActualizacion = _ahora();
    _marcarVistas();
    if (!_cerrado) notifyListeners();
  }

  /// T-095: un toque. Una sola valoración por recomendación (el servidor responde
  /// 409 si ya tenía); la tarjeta muestra lo elegido y desactiva los botones.
  Future<void> valorar(Recomendacion recomendacion, OpcionValoracion opcion) async {
    if (valorando != null || valoradas.containsKey(recomendacion.id)) return;
    valorando = recomendacion.id;
    erroresValoracion.remove(recomendacion.id);
    notifyListeners();
    try {
      final actualizada = await api.valorar(recomendacion.id, opcion);
      valoradas[recomendacion.id] = actualizada.valoracion ?? opcion;
      activas = [for (final r in activas) r.id == actualizada.id ? actualizada : r];
    } on ErrorApi catch (e) {
      if (e.codigo == 409) {
        // Ya la valoró alguien (otro dispositivo o la web): se recarga para verla.
        valoradas[recomendacion.id] = recomendacion.valoracion ?? opcion;
        unawaited(recargar());
      } else {
        erroresValoracion[recomendacion.id] = e.codigo == 403
            ? 'Tu rol no puede valorar recomendaciones.'
            : 'No se pudo guardar. Toca de nuevo para reintentar.';
      }
    } catch (_) {
      erroresValoracion[recomendacion.id] =
          'Sin conexión: no se guardó. Toca de nuevo para reintentar.';
    } finally {
      valorando = null;
      if (!_cerrado) notifyListeners();
    }
  }

  /// Las que se muestran por primera vez quedan VISTA en el servidor.
  void _marcarVistas() {
    for (final r in activas) {
      if (r.estado != 'PENDIENTE' || !_marcadas.add(r.id)) continue;
      unawaited(api.marcarVista(r.id).catchError((Object _) {
        _marcadas.remove(r.id); // se reintenta la próxima vez
      }));
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
