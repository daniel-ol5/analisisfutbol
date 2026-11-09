/// Botonera de eventos en vivo — T-069 (HU-32).
///
/// Gol y tarjetas: tipo + jugador. Sustitución: "Cambio" en el titular que
/// sale + suplente que entra. Ambos recorridos requieren como máximo 2 toques.
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
  });

  /// null abre el único partido EN_CURSO; la ruta de agenda pasa un id.
  final int? partidoId;
  final ObtenerPartidos obtenerPartidos;
  final ObtenerAlineacion obtenerAlineacion;
  final RegistrarEvento registrar;
  final DeshacerEvento deshacer;
  final ContarPendientes contarPendientes;
  final SincronizarPendientes sincronizarPendientes;
  final DescartarPendiente descartarPendiente;

  @override
  State<PartidoPagina> createState() => _PartidoPaginaState();
}

class _PartidoPaginaState extends State<PartidoPagina>
    with WidgetsBindingObserver {
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _cargar().then((_) => _actualizarPendientes());
    _reintentoSincronizacion = Timer.periodic(
      const Duration(seconds: 15),
      (_) => _sincronizar(),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _venceDeshacer?.cancel();
    _reintentoSincronizacion?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _sincronizar();
  }

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
          _error = widget.partidoId == null
              ? 'No hay un partido en curso.'
              : 'Este partido no está en curso.';
        });
        return;
      }
      final alineacion = await widget.obtenerAlineacion(partido.id);
      if (!mounted) return;
      setState(() {
        _partido = partido;
        _alineacion = alineacion;
        _enCancha
          ..clear()
          ..addAll(alineacion.titulares.map((j) => j.jugadorId));
        _equipoEvento = partido.esLocal ? 'LOCAL' : 'VISITANTE';
        _golesFavor = partido.golesFavor;
        _golesContra = partido.golesContra;
      });
    } on ErrorApi catch (e) {
      if (mounted) setState(() => _error = e.detalle);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'Sin conexión con el servidor. Intenta nuevamente.',
        );
      }
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Partido? _buscarActivo(List<Partido> partidos) {
    for (final partido in partidos) {
      final coincide =
          widget.partidoId == null || partido.id == widget.partidoId;
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
    await _cargar();
    await _actualizarPendientes();
    await _sincronizar();
  }

  @override
  Widget build(BuildContext context) {
    final partido = _partido;
    final alineacion = _alineacion;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Eventos en vivo'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Volver a partidos',
          onPressed: () => context.go('/partidos'),
        ),
        actions: [
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
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _recargar,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            if (_cargando)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_error != null && !_cargando) ...[
              _Mensaje(texto: _error!, error: true),
              OutlinedButton(
                onPressed: _cargar,
                child: const Text('Reintentar'),
              ),
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
          color: error ? e.onErrorContainer : e.onSecondaryContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
