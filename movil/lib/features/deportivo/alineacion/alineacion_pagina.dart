/// CU-17 · Ver alineación en móvil  —  T-053 (HU-14).
///
/// Solo lectura: la alineación se arma en la web (T-051). Muestra la cancha
/// con los titulares, el capitán, la formación y el banco. Sin conexión,
/// muestra la última alineación descargada de ese partido.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/api/cliente.dart';
import 'api.dart';
import 'cancha.dart';
import 'modelos.dart';

class AlineacionPagina extends StatefulWidget {
  const AlineacionPagina({
    super.key,
    required this.partidoId,
    this.obtener = obtenerAlineacion,
    this.enCache = alineacionEnCache,
  });

  final int partidoId;

  /// Inyectables para las pruebas; por defecto, la API y la caché reales.
  final Future<Alineacion> Function(int) obtener;
  final Future<Alineacion?> Function(int) enCache;

  @override
  State<AlineacionPagina> createState() => _AlineacionPaginaState();
}

class _AlineacionPaginaState extends State<AlineacionPagina> {
  Alineacion? _alineacion;
  bool _cargando = true;
  bool _desdeCache = false;
  bool _sinAlineacion = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    setState(() => _cargando = true);
    final guardada = await widget.enCache(widget.partidoId);
    if (mounted && guardada != null && _alineacion == null) {
      setState(() => _alineacion = guardada);
    }
    try {
      final alineacion = await widget.obtener(widget.partidoId);
      if (!mounted) return;
      setState(() {
        _alineacion = alineacion;
        _desdeCache = false;
        _sinAlineacion = false;
        _error = null;
      });
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _sinAlineacion = e.codigo == 404;
        _error = e.codigo == 404 ? null : e.detalle;
        if (e.codigo == 404) _alineacion = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _desdeCache = _alineacion != null;
        _error = _alineacion == null ? 'Sin conexión con el servidor.' : null;
      });
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final alineacion = _alineacion;
    return Scaffold(
      appBar: AppBar(
        title: Text('Alineación · Partido ${widget.partidoId}'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Volver a partidos',
          onPressed: () => context.go('/partidos'),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _cargar,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            if (_cargando && alineacion == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_desdeCache)
              const _Mensaje(
                  texto: 'Sin conexión: se muestra la última alineación guardada.'),
            if (_sinAlineacion)
              const _Mensaje(
                  texto: 'Este partido todavía no tiene alineación. '
                      'El cuerpo técnico la arma desde la web.'),
            if (_error != null) ...[
              _Mensaje(texto: _error!),
              OutlinedButton(onPressed: _cargar, child: const Text('Reintentar')),
            ],
            if (alineacion != null) ..._contenido(context, alineacion),
          ],
        ),
      ),
    );
  }

  List<Widget> _contenido(BuildContext context, Alineacion a) {
    final t = Theme.of(context);
    final capitan = a.capitan;
    return [
      Row(
        children: [
          Text(a.formacion,
              key: const Key('formacion'),
              style: t.textTheme.titleLarge?.copyWith(fontSize: 28)),
          const SizedBox(width: 12),
          if (capitan != null)
            Expanded(
              child: Text('Capitán: ${capitan.dorsal} ${capitan.apellido}',
                  style: t.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w700)),
            ),
        ],
      ),
      const SizedBox(height: 12),
      Cancha(titulares: a.titulares),
      const SizedBox(height: 20),
      Text('Suplentes (${a.suplentes.length})', style: t.textTheme.titleMedium),
      const SizedBox(height: 8),
      if (a.suplentes.isEmpty)
        Text('Sin suplentes convocados.', style: t.textTheme.bodyMedium),
      for (final j in a.suplentes)
        Card(
          child: ListTile(
            leading: CircleAvatar(
              radius: 22,
              backgroundColor: t.colorScheme.surface,
              foregroundColor: t.colorScheme.onSurface,
              child: Text('${j.dorsal}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
            ),
            title: Text('${j.nombre} ${j.apellido}'),
            subtitle: Text(j.posicionLegible),
          ),
        ),
    ];
  }
}

class _Mensaje extends StatelessWidget {
  const _Mensaje({required this.texto});
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
      child: Text(texto,
          style: TextStyle(
              color: e.onSecondaryContainer, fontWeight: FontWeight.w600)),
    );
  }
}
