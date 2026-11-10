/// CU-30 · Cronómetro sincronizado en móvil  —  T-071 (P4).
///
/// Pantalla de solo lectura para todos los roles en móvil. Consulta
/// `GET /partido/{id}/estado` cada 5 s (`intervaloSondeoEstado`) y mantiene un
/// reloj monótono local (`Stopwatch`) que avanza segundo a segundo sin
/// retroceder el segundero ni verse afectado por cambios en la hora del
/// teléfono.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/tema.dart';
import '../../shared/api/cliente.dart';
import 'api.dart';
import 'modelos.dart';

class PartidoPagina extends StatefulWidget {
  const PartidoPagina({
    super.key,
    this.partidoId,
    this.obtenerEstado = obtenerEstadoPartido,
    this.enCache = estadoPartidoEnCache,
    this.listarPartidos = listarPartidosVivo,
    this.partidosEnCache = partidosVivoEnCache,
    this.ahoraMonotonoMs,
    this.intervaloSondeo = intervaloSondeoEstado,
    this.intervaloTick = intervaloTickReloj,
  });

  /// Identificador del partido si se navega a `/partido/:id`. Si es `null`
  /// (`/partido`), se selecciona el primer partido priorizado (`EN_CURSO` o
  /// `PROGRAMADO`).
  final int? partidoId;

  /// Funciones inyectables para pruebas sin red ni esperas reales.
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

  List<ResumenPartidoVivo> _partidos = const [];
  int? _partidoIdActivo;
  EstadoEnVivo? _estado;
  AnclaReloj? _ancla;
  int _segundosVisibles = 0;

  bool _cargando = true;
  bool _sinConexion = false;
  bool _noEncontrado = false;
  String? _error;

  Timer? _timerSondeo;
  Timer? _timerTick;

  int _leerAhoraMs() =>
      widget.ahoraMonotonoMs?.call() ?? _stopwatch.elapsedMilliseconds;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _partidoIdActivo = widget.partidoId;
    _inicializar();
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
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _detenerTimers();
      return;
    }
    if (state == AppLifecycleState.resumed) {
      _actualizarSegundero();
      _iniciarTimers();
      if (_partidoIdActivo != null) {
        _consultarEstado(silencioso: true);
      }
    }
  }

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

  Future<void> _inicializar() async {
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
    } else {
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
    _iniciarTimers();
    _consultarEstado(silencioso: false);
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
        // Desde caché en frío mostramos el último segundo conocido sin avanzar
        // a ciegas hasta confirmar con el servidor.
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
        } else {
          _error = e.detalle;
        }
      });
    } catch (_) {
      if (!mounted || _partidoIdActivo != id) return;
      setState(() {
        _sinConexion = _estado != null;
        _error = _estado == null ? 'Sin conexión con el servidor.' : null;
      });
    } finally {
      if (mounted && !silencioso && _partidoIdActivo == id) {
        setState(() => _cargando = false);
      }
    }
  }

  Future<void> _refrescarManual() async {
    await _cargarListaPartidos();
    if (_partidoIdActivo != null) {
      await _consultarEstado(silencioso: false);
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

  @override
  Widget build(BuildContext context) {
    final estado = _estado;
    final partidoInfo = _partidoSeleccionado;
    final fase = determinarFasePartido(
      estado,
      estadoPartido: partidoInfo?.estado,
    );
    final textoReloj = formatearCronometroPartido(
      _segundosVisibles,
      estado?.parte ?? 0,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Partido en vivo'),
        actions: [
          IconButton(
            tooltip: 'Actualizar estado',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _refrescarManual,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refrescarManual,
        color: verde,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
          children: [
            if (_partidos.isNotEmpty) ...[
              _SelectorPartido(
                partidos: _partidos,
                seleccionadoId: _partidoIdActivo,
                onChanged: _cambiarPartido,
              ),
              const SizedBox(height: 14),
            ],
            if (_cargando && estado == null && !_noEncontrado && _error == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_partidoIdActivo == null && !_cargando)
              const _MensajeBanner(
                texto: 'Todavía no hay partidos programados en la agenda.',
              ),
            if (_sinConexion && estado != null) ...[
              const _MensajeBanner(
                texto: 'Sin conexión: se muestra el último estado guardado.',
              ),
              OutlinedButton(
                onPressed: () => _consultarEstado(silencioso: false),
                child: const Text('Reintentar'),
              ),
              const SizedBox(height: 12),
            ],
            if (_noEncontrado) ...[
              const _MensajeBanner(
                texto: 'Partido no encontrado.',
              ),
              OutlinedButton(
                onPressed: () => _consultarEstado(silencioso: false),
                child: const Text('Reintentar'),
              ),
              const SizedBox(height: 12),
            ],
            if (_error != null) ...[
              _MensajeBanner(texto: _error!),
              OutlinedButton(
                onPressed: () => _consultarEstado(silencioso: false),
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
              _TarjetaMarcador(
                partido: partidoInfo,
                partidoId: estado.partidoId,
                golesFavor: estado.golesFavor,
                golesContra: estado.golesContra,
              ),
              const SizedBox(height: 14),
              _TarjetaCalidad(calidad: estado.calidad),
              const SizedBox(height: 14),
              const _AvisoSoloLectura(),
            ],
          ],
        ),
      ),
    );
  }
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
            Text('Estado del seguimiento óptico', style: t.textTheme.titleMedium),
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

class _MensajeBanner extends StatelessWidget {
  const _MensajeBanner({required this.texto});
  final String texto;

  @override
  Widget build(BuildContext context) {
    final e = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: e.secondaryContainer,
        border: Border.all(color: e.outline, width: 2),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        texto,
        style: TextStyle(
          fontSize: 16,
          color: e.onSecondaryContainer,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
