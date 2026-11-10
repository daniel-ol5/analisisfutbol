/// Operación del Partido en vivo — T-069, T-070 y T-071 (CU-30, CU-36, CU-37 y CU-38).
///
/// Integra:
/// - Cronómetro sincronizado (CU-30 · T-071): consulta `GET /partido/{id}/estado`
///   cada 5 s (`intervaloSondeoEstado`) y mantiene un reloj monótono local
///   (`Stopwatch`) que avanza segundo a segundo sin retroceder el segundero.
/// - Botonera de eventos en vivo y cola offline (T-069 / T-070): registro en
///   máximo 2 toques (gol, amarilla, roja, cambio) con opción de deshacer y
///   sincronización automática de eventos pendientes.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../../shared/api/cliente.dart';
import '../deportivo/agenda/api.dart' as agenda_api;
import '../deportivo/agenda/modelos.dart';
import '../deportivo/alineacion/api.dart' as alineacion_api;
import '../deportivo/alineacion/modelos.dart';
import 'api.dart' as partido_api;
import 'cola_eventos.dart';
import 'modelos.dart';

typedef ObtenerPartidos = Future<List<Partido>> Function();
typedef ObtenerAlineacion = Future<Alineacion> Function(int partidoId);
typedef RegistrarEvento =
    Future<EventoManual> Function(int partidoId, EventoCrear evento);
typedef DeshacerEvento = Future<void> Function(int eventoId);
typedef ContarPendientes = Future<int> Function(int partidoId);
typedef SincronizarPendientes =
    Future<ResultadoSincronizacion> Function(int partidoId);
typedef DescartarPendiente = Future<void> Function(String uuid);

class PartidoPagina extends StatefulWidget {
  const PartidoPagina({
    super.key,
    this.partidoId,
    this.obtenerPartidos = agenda_api.listarPartidos,
    this.obtenerAlineacion = alineacion_api.obtenerAlineacion,
    this.registrar = partido_api.registrarEvento,
    this.deshacer = partido_api.deshacerEvento,
    this.contarPendientes = partido_api.contarPendientes,
    this.sincronizarPendientes = partido_api.sincronizarPendientes,
    this.descartarPendiente = partido_api.descartarPendiente,
    this.obtenerEstado = partido_api.obtenerEstadoPartido,
    this.enCache = partido_api.estadoPartidoEnCache,
    this.listarPartidos = partido_api.listarPartidosVivo,
    this.partidosEnCache = partido_api.partidosVivoEnCache,
    this.ahoraMonotonoMs,
    this.intervaloSondeo = intervaloSondeoEstado,
    this.intervaloTick = intervaloTickReloj,
  });

  /// Identificador del partido si se navega a `/partido/:id` o
  /// `/partidos/:id/eventos`. Si es `null` (`/partido`), se selecciona el
  /// partido en curso o priorizado.
  final int? partidoId;

  /// Funciones inyectables de la botonera y cola offline (T-069 / T-070).
  final ObtenerPartidos obtenerPartidos;
  final ObtenerAlineacion obtenerAlineacion;
  final RegistrarEvento registrar;
  final DeshacerEvento deshacer;
  final ContarPendientes contarPendientes;
  final SincronizarPendientes sincronizarPendientes;
  final DescartarPendiente descartarPendiente;

  /// Funciones inyectables del cronómetro sincronizado (T-071).
  final Future<EstadoEnVivo> Function(int partidoId) obtenerEstado;
  final Future<EstadoGuardado?> Function(int partidoId) enCache;
  final Future<List<ResumenPartidoVivo>> Function() listarPartidos;
  final Future<List<ResumenPartidoVivo>?> Function() partidosEnCache;
  final int Function()? ahoraMonotonoMs;
  final Duration intervaloSondeo;
  final Duration intervaloTick;

  @override
  State<PartidoPagina> createState() => _PartidoPaginaState();
}

class _PartidoPaginaState extends State<PartidoPagina>
    with WidgetsBindingObserver {
  final Stopwatch _stopwatch = Stopwatch()..start();

  // Estado del cronómetro sincronizado (T-071)
  List<ResumenPartidoVivo> _partidos = const [];
  int? _partidoIdActivo;
  EstadoEnVivo? _estado;
  AnclaReloj? _ancla;
  int _segundosVisibles = 0;
  bool _sinConexion = false;
  bool _noEncontrado = false;
  Timer? _timerSondeo;
  Timer? _timerTick;

  // Estado de la botonera y cola offline (T-069 / T-070)
  Partido? _partido;
  Alineacion? _alineacion;
  final Set<int> _enCancha = {};
  TipoEvento? _tipoElegido;
  String? _equipoEvento;
  EventoManual? _ultimoEvento;
  bool _puedeDeshacer = false;
  bool _cargando = true;
  bool _enviando = false;
  String? _error;
  Timer? _venceDeshacer;
  Timer? _reintentoSincronizacion;
  int _golesFavor = 0;
  int _golesContra = 0;
  int _pendientes = 0;
  bool _sincronizando = false;

  int _leerAhoraMs() =>
      widget.ahoraMonotonoMs?.call() ?? _stopwatch.elapsedMilliseconds;

  /// Activa el sondeo del cronómetro cuando se usa en producción (ambos por
  /// defecto) o cuando una prueba inyecta `obtenerEstado`.
  bool get _usarRelojVivo =>
      !identical(widget.obtenerEstado, partido_api.obtenerEstadoPartido) ||
      identical(widget.obtenerPartidos, agenda_api.listarPartidos);

  /// Activa la carga de botonera/cola cuando se usa en producción (ambos por
  /// defecto) o cuando una prueba inyecta `obtenerPartidos`.
  bool get _usarBotonera =>
      !identical(widget.obtenerPartidos, agenda_api.listarPartidos) ||
      identical(widget.obtenerEstado, partido_api.obtenerEstadoPartido);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _partidoIdActivo = widget.partidoId;

    if (_usarRelojVivo) {
      _inicializarReloj();
    }
    if (_usarBotonera) {
      _cargar().then((_) => _actualizarPendientes());
      _reintentoSincronizacion = Timer.periodic(
        const Duration(seconds: 15),
        (_) => _sincronizar(),
      );
    }
  }

  @override
  void didUpdateWidget(covariant PartidoPagina oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.partidoId != oldWidget.partidoId && widget.partidoId != null) {
      _cambiarPartido(widget.partidoId!);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _detenerTimers();
    _stopwatch.stop();
    _venceDeshacer?.cancel();
    _reintentoSincronizacion?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      if (_usarRelojVivo) {
        _detenerTimers();
      }
      return;
    }
    if (state == AppLifecycleState.resumed) {
      if (_usarRelojVivo) {
        _actualizarSegundero();
        _iniciarTimers();
        if (_partidoIdActivo != null) {
          _consultarEstado(silencioso: true);
        }
      }
      if (_usarBotonera) {
        _sincronizar();
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Cronómetro sincronizado (T-071)
  // ---------------------------------------------------------------------------

  void _iniciarTimers() {
    _detenerTimers();
    _timerSondeo = Timer.periodic(widget.intervaloSondeo, (_) {
      if (_partidoIdActivo != null && !_noEncontrado) {
        _consultarEstado(silencioso: true);
      }
    });
    _timerTick = Timer.periodic(widget.intervaloTick, (_) {
      _actualizarSegundero();
    });
  }

  void _detenerTimers() {
    _timerSondeo?.cancel();
    _timerSondeo = null;
    _timerTick?.cancel();
    _timerTick = null;
  }

  void _actualizarSegundero() {
    final ancla = _ancla;
    if (ancla == null || !mounted) return;
    final calculados = calcularSegundosActuales(ancla, _leerAhoraMs());
    if (calculados != _segundosVisibles) {
      setState(() => _segundosVisibles = calculados);
    }
  }

  Future<void> _inicializarReloj() async {
    _iniciarTimers();
    if (_partidoIdActivo != null) {
      unawaited(_cargarListaPartidos());
      await _consultarEstado(silencioso: false);
      return;
    }
    await _cargarListaPartidos();
    if (!mounted) return;
    if (_partidoIdActivo != null) {
      await _consultarEstado(silencioso: false);
    } else if (!_usarBotonera) {
      setState(() => _cargando = false);
    }
  }

  Future<void> _cargarListaPartidos() async {
    final enCache = await widget.partidosEnCache();
    if (mounted && enCache != null && _partidos.isEmpty) {
      final ordenados = ordenarPartidosParaVivo(enCache);
      setState(() {
        _partidos = ordenados;
        if (_partidoIdActivo == null && ordenados.isNotEmpty) {
          _partidoIdActivo = ordenados.first.id;
        }
      });
    }
    try {
      final frescos = await widget.listarPartidos();
      if (!mounted) return;
      final ordenados = ordenarPartidosParaVivo(frescos);
      setState(() {
        _partidos = ordenados;
        if (_partidoIdActivo == null && ordenados.isNotEmpty) {
          _partidoIdActivo = ordenados.first.id;
        }
      });
    } catch (_) {
      // Si falla la agenda, conservamos la caché o el partidoId explícito.
    }
  }

  void _cambiarPartido(int nuevoId) {
    if (_partidoIdActivo == nuevoId) return;
    setState(() {
      _partidoIdActivo = nuevoId;
      _estado = null;
      _ancla = null;
      _segundosVisibles = 0;
      _cargando = true;
      _sinConexion = false;
      _noEncontrado = false;
      _error = null;
    });
    if (_usarRelojVivo) {
      _iniciarTimers();
      _consultarEstado(silencioso: false);
    }
    if (_usarBotonera) {
      _cargar().then((_) => _actualizarPendientes());
    }
  }

  Future<void> _consultarEstado({required bool silencioso}) async {
    final id = _partidoIdActivo;
    if (id == null) return;

    if (!silencioso && mounted) {
      setState(() => _cargando = true);
    }

    if (_estado == null) {
      final guardado = await widget.enCache(id);
      if (mounted && guardado != null && _estado == null) {
        final ahora = _leerAhoraMs();
        final anclaCache = AnclaReloj(
          partidoId: guardado.estado.partidoId,
          parte: guardado.estado.parte,
          enCurso: false,
          baseSegundos: guardado.estado.segundosRemotos,
          marcaMonotonicaMs: ahora,
        );
        setState(() {
          _estado = guardado.estado;
          _ancla = anclaCache;
          _segundosVisibles = guardado.estado.segundosRemotos;
          _sinConexion = true;
        });
      }
    }

    try {
      final remoto = await widget.obtenerEstado(id);
      if (!mounted || _partidoIdActivo != id) return;
      final ahora = _leerAhoraMs();
      final nuevaAncla = reconciliarAnclaReloj(_ancla, remoto, ahora);
      final segundos = calcularSegundosActuales(nuevaAncla, ahora);
      setState(() {
        _estado = remoto;
        _ancla = nuevaAncla;
        _segundosVisibles = segundos;
        _sinConexion = false;
        _noEncontrado = false;
        _error = null;
      });
    } on ErrorApi catch (e) {
      if (!mounted || _partidoIdActivo != id) return;
      setState(() {
        _sinConexion = false;
        if (e.codigo == 404) {
          _noEncontrado = true;
          _estado = null;
          _ancla = null;
          _error = null;
        } else if (_partido == null) {
          _error = e.detalle;
        }
      });
    } catch (_) {
      if (!mounted || _partidoIdActivo != id) return;
      setState(() {
        _sinConexion = _estado != null;
        if (_estado == null && _partido == null) {
          _error = 'Sin conexión con el servidor.';
        }
      });
    } finally {
      if (mounted && !silencioso && _partidoIdActivo == id) {
        setState(() => _cargando = false);
      }
    }
  }

  ResumenPartidoVivo? get _partidoSeleccionado {
    final id = _partidoIdActivo;
    if (id == null) return null;
    for (final p in _partidos) {
      if (p.id == id) return p;
    }
    return null;
  }

  // ---------------------------------------------------------------------------
  // Botonera de eventos y cola offline (T-069 / T-070)
  // ---------------------------------------------------------------------------

  Future<void> _cargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final partidos = await widget.obtenerPartidos();
      final partido = _buscarActivo(partidos);
      if (partido == null) {
        if (!mounted) return;
        setState(() {
          _partido = null;
          _alineacion = null;
          if (_estado == null && !_noEncontrado) {
            _error = widget.partidoId == null
                ? 'No hay un partido en curso.'
                : 'Este partido no está en curso.';
          }
        });
        return;
      }
      final alineacion = await widget.obtenerAlineacion(partido.id);
      if (!mounted) return;
      final habiaPartidoId = _partidoIdActivo != null;
      setState(() {
        _partido = partido;
        _partidoIdActivo ??= partido.id;
        _alineacion = alineacion;
        _enCancha
          ..clear()
          ..addAll(alineacion.titulares.map((j) => j.jugadorId));
        _equipoEvento = partido.esLocal ? 'LOCAL' : 'VISITANTE';
        _golesFavor = partido.golesFavor;
        _golesContra = partido.golesContra;
      });
      if (_usarRelojVivo && !habiaPartidoId && _partidoIdActivo != null) {
        unawaited(_consultarEstado(silencioso: true));
      }
    } on ErrorApi catch (e) {
      if (mounted && _estado == null && !_noEncontrado) {
        setState(() => _error = e.detalle);
      }
    } catch (_) {
      if (mounted && _estado == null && !_noEncontrado) {
        setState(
          () => _error = 'Sin conexión con el servidor. Intenta nuevamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Partido? _buscarActivo(List<Partido> partidos) {
    final idBuscado = _partidoIdActivo ?? widget.partidoId;
    for (final partido in partidos) {
      final coincide = idBuscado == null || partido.id == idBuscado;
      if (coincide && partido.estado == 'EN_CURSO') return partido;
    }
    return null;
  }

  bool get _esEquipoPropio {
    final equipo = _equipoEvento;
    return equipo != null && _ladoEsPropio(equipo);
  }

  bool _ladoEsPropio(String equipo) {
    final partido = _partido;
    if (partido == null) return false;
    return equipo == (partido.esLocal ? 'LOCAL' : 'VISITANTE');
  }

  List<JugadorAlineado> get _jugadoresEnCancha {
    final jugadores = _alineacion?.jugadores ?? const <JugadorAlineado>[];
    return jugadores.where((j) => _enCancha.contains(j.jugadorId)).toList()
      ..sort((a, b) => a.dorsal.compareTo(b.dorsal));
  }

  List<JugadorAlineado> get _suplentesDisponibles {
    final jugadores = _alineacion?.jugadores ?? const <JugadorAlineado>[];
    return jugadores.where((j) => !_enCancha.contains(j.jugadorId)).toList()
      ..sort((a, b) => a.dorsal.compareTo(b.dorsal));
  }

  Future<void> _elegirTipo(TipoEvento tipo) async {
    if (_enviando) return;
    if (!_esEquipoPropio) {
      await _registrar(EventoCrear(tipo: tipo, equipo: _equipoEvento!));
      return;
    }
    setState(() => _tipoElegido = tipo);
  }

  Future<void> _elegirJugador(JugadorAlineado jugador) async {
    final tipo = _tipoElegido;
    if (tipo == null || _enviando) return;
    await _registrar(
      EventoCrear(
        tipo: tipo,
        equipo: _equipoEvento!,
        jugadorId: jugador.jugadorId,
      ),
    );
  }

  Future<void> _iniciarCambio(JugadorAlineado sale) async {
    if (_enviando) return;
    final suplentes = _suplentesDisponibles;
    if (suplentes.isEmpty) {
      _avisar('No hay suplentes disponibles.');
      return;
    }
    final entra = await showModalBottomSheet<JugadorAlineado>(
      context: context,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: FractionallySizedBox(
          heightFactor: .72,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
                child: Text(
                  'Entra por ${sale.dorsal} ${sale.apellido}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Text('Segundo toque: elige al suplente que entra.'),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView(
                  children: [
                    for (final jugador in suplentes)
                      ListTile(
                        key: Key('suplente-${jugador.jugadorId}'),
                        minTileHeight: 60,
                        leading: CircleAvatar(child: Text('${jugador.dorsal}')),
                        title: Text('${jugador.nombre} ${jugador.apellido}'),
                        subtitle: Text(jugador.posicionLegible),
                        onTap: () => Navigator.pop(context, jugador),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (entra == null || !mounted) return;
    await _registrar(
      EventoCrear(
        tipo: TipoEvento.sustitucion,
        equipo: _equipoEvento!,
        jugadorId: sale.jugadorId,
        jugadorEntraId: entra.jugadorId,
      ),
    );
  }

  Future<void> _registrar(EventoCrear solicitud) async {
    final partido = _partido;
    if (partido == null || _enviando) return;
    setState(() => _enviando = true);
    try {
      final evento = await widget.registrar(partido.id, solicitud);
      if (!mounted) return;
      setState(() {
        _ultimoEvento = evento;
        _puedeDeshacer = true;
        _tipoElegido = null;
        if (evento.tipo == TipoEvento.gol) {
          if (_ladoEsPropio(evento.equipo)) {
            _golesFavor++;
          } else {
            _golesContra++;
          }
        }
        if (evento.tipo == TipoEvento.sustitucion &&
            evento.jugadorId != null &&
            evento.jugadorEntraId != null) {
          _enCancha
            ..remove(evento.jugadorId)
            ..add(evento.jugadorEntraId!);
        }
      });
      await _actualizarPendientes();
      _programarVencimiento();
      _confirmar(evento);
    } on ErrorApi catch (e) {
      _avisar(e.detalle, error: true);
    } catch (_) {
      _avisar('No se pudo registrar. Revisa la conexión.', error: true);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  void _programarVencimiento() {
    _venceDeshacer?.cancel();
    _venceDeshacer = Timer(const Duration(seconds: 60), () {
      if (mounted) setState(() => _puedeDeshacer = false);
    });
  }

  void _confirmar(EventoManual evento) {
    final detalle = evento.pendiente
        ? '${evento.tipo.etiqueta} guardado sin conexión. Se sincronizará automáticamente.'
        : evento.convertidaEnRoja
        ? 'Segunda amarilla: convertida en roja.'
        : '${evento.tipo.etiqueta} registrado en el minuto ${evento.minuto}.';
    final mensajero = ScaffoldMessenger.of(context);
    mensajero
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(detalle),
          action: SnackBarAction(
            label: 'Deshacer',
            onPressed: () => _deshacerUltimo(evento),
          ),
        ),
      );
  }

  Future<void> _deshacerUltimo(EventoManual evento) async {
    if (!_puedeDeshacer || _enviando || _ultimoEvento?.id != evento.id) return;
    setState(() => _enviando = true);
    try {
      if (evento.pendiente && evento.uuid != null) {
        await widget.descartarPendiente(evento.uuid!);
      } else {
        await widget.deshacer(evento.id);
      }
      if (!mounted) return;
      setState(() {
        if (evento.tipo == TipoEvento.gol) {
          if (_ladoEsPropio(evento.equipo)) {
            _golesFavor = (_golesFavor - 1).clamp(0, 999);
          } else {
            _golesContra = (_golesContra - 1).clamp(0, 999);
          }
        }
        if (evento.tipo == TipoEvento.sustitucion &&
            evento.jugadorId != null &&
            evento.jugadorEntraId != null) {
          _enCancha
            ..remove(evento.jugadorEntraId)
            ..add(evento.jugadorId!);
        }
        _ultimoEvento = null;
        _puedeDeshacer = false;
      });
      await _actualizarPendientes();
      _venceDeshacer?.cancel();
      _avisar('Evento deshecho.');
    } on ErrorApi catch (e) {
      _avisar(e.detalle, error: true);
    } catch (_) {
      _avisar('No se pudo deshacer el evento.', error: true);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  void _avisar(String texto, {bool error = false}) {
    if (!mounted) return;
    final colores = Theme.of(context).colorScheme;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(texto),
          backgroundColor: error ? colores.error : null,
        ),
      );
  }

  Future<void> _actualizarPendientes() async {
    final partido = _partido;
    if (partido == null) return;
    try {
      final cantidad = await widget.contarPendientes(partido.id);
      if (mounted) setState(() => _pendientes = cantidad);
    } catch (_) {
      // Sin perfil local o base temporalmente no disponible: se reintenta.
    }
  }

  Future<void> _sincronizar({bool anunciar = false}) async {
    final partido = _partido;
    if (partido == null || _sincronizando || _pendientes == 0) return;
    _sincronizando = true;
    if (mounted) setState(() {});
    try {
      final resultado = await widget.sincronizarPendientes(partido.id);
      if (!mounted) return;
      setState(() => _pendientes = resultado.pendientes);
      if (anunciar || resultado.confirmados > 0) {
        final texto = resultado.confirmados > 0
            ? '${resultado.confirmados} evento(s) sincronizado(s).'
            : 'No se pudo sincronizar. Los eventos siguen guardados.';
        _avisar(texto, error: resultado.error != null && anunciar);
      }
    } catch (_) {
      if (anunciar) {
        _avisar(
          'No se pudo sincronizar. Los eventos siguen guardados.',
          error: true,
        );
      }
    } finally {
      _sincronizando = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _recargar() async {
    if (_usarRelojVivo) {
      await _cargarListaPartidos();
      if (_partidoIdActivo != null) {
        await _consultarEstado(silencioso: false);
      }
    }
    if (_usarBotonera) {
      await _cargar();
      await _actualizarPendientes();
      await _sincronizar();
    }
  }

  @override
  Widget build(BuildContext context) {
    final estado = _estado;
    final partido = _partido;
    final alineacion = _alineacion;
    final partidoInfo = _partidoSeleccionado;
    final fase = determinarFasePartido(
      estado,
      estadoPartido: partidoInfo?.estado ?? partido?.estado,
    );
    final textoReloj = formatearCronometroPartido(
      _segundosVisibles,
      estado?.parte ?? 0,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Partido en vivo'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Volver a partidos',
          onPressed: () => context.go('/partidos'),
        ),
        actions: [
          if (_usarBotonera)
            TextButton.icon(
              key: const Key('eventos-pendientes'),
              onPressed: _pendientes > 0 && !_sincronizando
                  ? () => _sincronizar(anunciar: true)
                  : null,
              icon: _sincronizando
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.cloud_upload_outlined),
              label: Text('Pendientes: $_pendientes'),
            ),
          IconButton(
            tooltip: 'Actualizar estado',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _recargar,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _recargar,
        color: verde,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            if (_partidos.isNotEmpty) ...[
              _SelectorPartido(
                partidos: _partidos,
                seleccionadoId: _partidoIdActivo,
                onChanged: _cambiarPartido,
              ),
              const SizedBox(height: 14),
            ],
            if (_cargando &&
                estado == null &&
                partido == null &&
                !_noEncontrado &&
                _error == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_usarRelojVivo &&
                !_usarBotonera &&
                _partidoIdActivo == null &&
                !_cargando)
              const _Mensaje(
                texto: 'Todavía no hay partidos programados en la agenda.',
              ),
            if (_sinConexion && estado != null) ...[
              const _Mensaje(
                texto: 'Sin conexión: se muestra el último estado guardado.',
              ),
              OutlinedButton(
                onPressed: () => _consultarEstado(silencioso: false),
                child: const Text('Reintentar'),
              ),
              const SizedBox(height: 12),
            ] else if (_noEncontrado) ...[
              const _Mensaje(
                texto: 'Partido no encontrado.',
                error: true,
              ),
              OutlinedButton(
                onPressed: () => _consultarEstado(silencioso: false),
                child: const Text('Reintentar'),
              ),
              const SizedBox(height: 12),
            ] else if (_error != null &&
                !_cargando &&
                estado == null &&
                partido == null) ...[
              _Mensaje(texto: _error!, error: true),
              OutlinedButton(
                onPressed: _recargar,
                child: const Text('Reintentar'),
              ),
              const SizedBox(height: 12),
            ],
            if (estado != null && !_noEncontrado) ...[
              _TarjetaCronometro(
                fase: fase,
                textoCronometro: textoReloj,
                parte: estado.parte,
                enCurso: estado.enCurso,
                sinConexion: _sinConexion,
              ),
              const SizedBox(height: 14),
              if (partido == null || alineacion == null) ...[
                _TarjetaMarcador(
                  partido: partidoInfo,
                  partidoId: estado.partidoId,
                  golesFavor: estado.golesFavor,
                  golesContra: estado.golesContra,
                ),
                const SizedBox(height: 14),
              ],
              _TarjetaCalidad(calidad: estado.calidad),
              const SizedBox(height: 14),
              if (partido == null || alineacion == null)
                const _AvisoSoloLectura(),
            ],
            if (partido != null && alineacion != null) ...[
              _PartidoActivo(
                partido: partido,
                golesFavor: _golesFavor,
                golesContra: _golesContra,
              ),
              const SizedBox(height: 16),
              _selectorEquipo(partido),
              const SizedBox(height: 14),
              if (_enviando) const LinearProgressIndicator(),
              if (_esEquipoPropio) _botoneraPropia() else _botoneraRival(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _selectorEquipo(Partido partido) {
    final local = partido.esLocal ? 'Nuestro equipo' : partido.rival;
    final visitante = partido.esLocal ? partido.rival : 'Nuestro equipo';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Equipo del evento',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: SegmentedButton<String>(
            key: const Key('selector-equipo'),
            showSelectedIcon: false,
            segments: [
              ButtonSegment(value: 'LOCAL', label: Text('Local · $local')),
              ButtonSegment(
                value: 'VISITANTE',
                label: Text('Visita · $visitante'),
              ),
            ],
            selected: {_equipoEvento!},
            onSelectionChanged: _enviando
                ? null
                : (seleccion) => setState(() {
                    _equipoEvento = seleccion.single;
                    _tipoElegido = null;
                  }),
          ),
        ),
      ],
    );
  }

  Widget _botoneraPropia() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const SizedBox(height: 14),
      Text(
        '1. Elige el evento',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          for (final tipo in [
            TipoEvento.gol,
            TipoEvento.amarilla,
            TipoEvento.roja,
          ])
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(right: 6),
                child: _BotonEvento(
                  tipo: tipo,
                  elegido: _tipoElegido == tipo,
                  onTap: _enviando ? null : () => _elegirTipo(tipo),
                ),
              ),
            ),
        ],
      ),
      const SizedBox(height: 16),
      Text(
        _tipoElegido == null
            ? '2. Elige al jugador. Para una sustitución usa Cambio en su fila.'
            : '2. Toca al jugador para registrar ${_tipoElegido!.etiqueta}.',
        key: const Key('instruccion-jugador'),
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      for (final jugador in _jugadoresEnCancha)
        _FilaJugador(
          jugador: jugador,
          habilitado: _tipoElegido != null && !_enviando,
          onEvento: () => _elegirJugador(jugador),
          onCambio: () => _iniciarCambio(jugador),
        ),
    ],
  );

  Widget _botoneraRival() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const SizedBox(height: 14),
      const _Mensaje(
        texto:
            'El rival no tiene plantel cargado. El evento se registrará sin jugador.',
      ),
      GridView.count(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisCount: 2,
        childAspectRatio: 2.4,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        children: [
          for (final tipo in TipoEvento.values)
            _BotonEvento(
              botonKey: Key('evento-rival-${tipo.codigo}'),
              tipo: tipo,
              elegido: false,
              onTap: _enviando ? null : () => _elegirTipo(tipo),
            ),
        ],
      ),
    ],
  );
}

class _SelectorPartido extends StatelessWidget {
  const _SelectorPartido({
    required this.partidos,
    required this.seleccionadoId,
    required this.onChanged,
  });

  final List<ResumenPartidoVivo> partidos;
  final int? seleccionadoId;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final existeSeleccionado =
        seleccionadoId != null && partidos.any((p) => p.id == seleccionadoId);

    return DropdownButtonFormField<int>(
      key: const Key('selector-partido'),
      initialValue: existeSeleccionado ? seleccionadoId : partidos.first.id,
      decoration: const InputDecoration(
        labelText: 'Partido seleccionado',
        contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
      items: [
        for (final p in partidos)
          DropdownMenuItem<int>(
            value: p.id,
            child: Text(
              'vs ${p.rival} (${p.estadoLegible})',
              overflow: TextOverflow.ellipsis,
            ),
          ),
      ],
      onChanged: (valor) {
        if (valor != null) onChanged(valor);
      },
    );
  }
}

class _TarjetaCronometro extends StatelessWidget {
  const _TarjetaCronometro({
    required this.fase,
    required this.textoCronometro,
    required this.parte,
    required this.enCurso,
    required this.sinConexion,
  });

  final FasePartido fase;
  final String textoCronometro;
  final int parte;
  final bool enCurso;
  final bool sinConexion;

  String get _textoParte => switch (parte) {
        1 => '1.er tiempo',
        2 => '2.º tiempo',
        _ => 'Sin iniciar',
      };

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final e = t.colorScheme;
    final colorInsignia = fase.enJuego
        ? verde
        : (fase == FasePartido.entretiempo ? ambar : e.outline);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: colorInsignia.withValues(alpha: 0.14),
                    border: Border.all(color: colorInsignia, width: 1.5),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    fase.etiqueta,
                    key: const Key('insignia-fase'),
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: fase.enJuego ? verde : e.onSurface,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: e.surfaceContainerHighest,
                    border: Border.all(color: e.outline),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    sinConexion ? 'Sin red' : 'Sincronizado',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: e.onSurface,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              textoCronometro,
              key: const Key('cronometro-texto'),
              textAlign: TextAlign.center,
              style: t.textTheme.titleLarge?.copyWith(
                fontSize: 52,
                fontWeight: FontWeight.w900,
                letterSpacing: -1,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Parte: $_textoParte · '
              '${enCurso ? 'Reloj corriendo' : 'Reloj pausado'}',
              textAlign: TextAlign.center,
              style: t.textTheme.bodyLarge?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            if (fase == FasePartido.entretiempo) ...[
              const SizedBox(height: 10),
              Text(
                'ENTRETIEMPO: cronómetro en pausa al cierre del 1.er tiempo.',
                textAlign: TextAlign.center,
                style: t.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _TarjetaMarcador extends StatelessWidget {
  const _TarjetaMarcador({
    required this.partido,
    required this.partidoId,
    required this.golesFavor,
    required this.golesContra,
  });

  final ResumenPartidoVivo? partido;
  final int partidoId;
  final int golesFavor;
  final int golesContra;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final p = partido;
    final titulo = p != null
        ? 'Nuestro equipo vs ${p.rival} (${p.esLocal ? 'Local' : 'Visitante'})'
        : 'Partido #$partidoId';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          children: [
            Text(
              titulo,
              textAlign: TextAlign.center,
              style: t.textTheme.titleMedium,
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                Column(
                  children: [
                    Text('A favor', style: t.textTheme.bodyMedium),
                    const SizedBox(height: 4),
                    Text(
                      '$golesFavor',
                      key: const Key('goles-favor'),
                      style: t.textTheme.titleLarge?.copyWith(
                        fontSize: 38,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
                Text(
                  '—',
                  style: t.textTheme.titleLarge?.copyWith(fontSize: 28),
                ),
                Column(
                  children: [
                    Text('En contra', style: t.textTheme.bodyMedium),
                    const SizedBox(height: 4),
                    Text(
                      '$golesContra',
                      key: const Key('goles-contra'),
                      style: t.textTheme.titleLarge?.copyWith(
                        fontSize: 38,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _TarjetaCalidad extends StatelessWidget {
  const _TarjetaCalidad({required this.calidad});

  final IndicadorCalidad calidad;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Estado del seguimiento óptico',
              style: t.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Worker: ${calidad.workerConectado ? 'Conectado' : 'Desconectado'} · '
              'Detectados: ${calidad.jugadoresDetectados}',
              style: t.textTheme.bodyMedium,
            ),
            if (calidad.degradado) ...[
              const SizedBox(height: 8),
              Text(
                'Calidad degradada: '
                '${calidad.motivo ?? 'Revisar visibilidad de cámara.'}',
                style: t.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AvisoSoloLectura extends StatelessWidget {
  const _AvisoSoloLectura();

  @override
  Widget build(BuildContext context) {
    final e = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: e.surface,
        border: Border.all(color: e.outline),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Text(
        'Modo lectura en móvil: el inicio, entretiempo, descuento y cierre del '
        'partido se operan desde la aplicación web.',
        style: TextStyle(fontSize: 16),
      ),
    );
  }
}

class _PartidoActivo extends StatelessWidget {
  const _PartidoActivo({
    required this.partido,
    required this.golesFavor,
    required this.golesContra,
  });

  final Partido partido;
  final int golesFavor;
  final int golesContra;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Card(
      key: const Key('partido-activo'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
              decoration: BoxDecoration(
                color: rojo,
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                'EN VIVO',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text('vs ${partido.rival}', style: t.textTheme.titleLarge),
            ),
            Text(
              '$golesFavor-$golesContra',
              key: const Key('marcador'),
              style: t.textTheme.titleLarge?.copyWith(fontSize: 30),
            ),
          ],
        ),
      ),
    );
  }
}

class _BotonEvento extends StatelessWidget {
  const _BotonEvento({
    this.botonKey,
    required this.tipo,
    required this.elegido,
    required this.onTap,
  });

  final Key? botonKey;
  final TipoEvento tipo;
  final bool elegido;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final color = switch (tipo) {
      TipoEvento.gol => esquema.primary,
      TipoEvento.amarilla => const Color(0xFFFACC15),
      TipoEvento.roja => rojo,
      TipoEvento.sustitucion => ambar,
    };
    return FilledButton(
      key: botonKey ?? Key('evento-${tipo.codigo}'),
      onPressed: onTap,
      style: FilledButton.styleFrom(
        backgroundColor: color,
        foregroundColor: tipo == TipoEvento.amarilla
            ? Colors.black
            : Colors.white,
        side: elegido ? BorderSide(color: esquema.onSurface, width: 4) : null,
        minimumSize: const Size(96, 64),
      ),
      child: Text(tipo.etiqueta),
    );
  }
}

class _FilaJugador extends StatelessWidget {
  const _FilaJugador({
    required this.jugador,
    required this.habilitado,
    required this.onEvento,
    required this.onCambio,
  });

  final JugadorAlineado jugador;
  final bool habilitado;
  final VoidCallback onEvento;
  final VoidCallback onCambio;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      key: Key('jugador-${jugador.jugadorId}'),
      minTileHeight: 68,
      leading: CircleAvatar(child: Text('${jugador.dorsal}')),
      title: Text('${jugador.nombre} ${jugador.apellido}'),
      subtitle: Text(jugador.posicionLegible),
      onTap: habilitado ? onEvento : null,
      trailing: FilledButton.tonal(
        key: Key('cambio-${jugador.jugadorId}'),
        onPressed: onCambio,
        child: const Text('Cambio'),
      ),
    ),
  );
}

class _Mensaje extends StatelessWidget {
  const _Mensaje({required this.texto, this.error = false});
  final String texto;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final e = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: error ? e.errorContainer : e.secondaryContainer,
        border: Border.all(color: error ? e.error : e.outline, width: 2),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        texto,
        style: TextStyle(
          fontSize: 16,
          color: error ? e.onErrorContainer : e.onSecondaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
