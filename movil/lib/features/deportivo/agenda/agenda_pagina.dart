/// CU-15 · Agenda de partidos en móvil  —  T-052 (HU-14).
///
/// Próximos partidos arriba y jugados abajo; un toque abre la alineación
/// (T-053). Sin conexión muestra la última agenda descargada y avisa de cuándo
/// es, para consultarla en la cancha sin cobertura.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/api/cliente.dart';
import '../api.dart' as deportivo;
import 'api.dart';
import 'modelos.dart';

/// Nombre de cada equipo del club por id; vacío si no se pudo obtener.
Future<Map<int, String>> _nombresDeEquipos() async {
  try {
    final equipos = await deportivo.listarEquipos();
    return {for (final e in equipos) e.id: e.nombre};
  } catch (_) {
    return {};
  }
}

class AgendaPagina extends StatefulWidget {
  const AgendaPagina({
    super.key,
    this.obtener = listarPartidos,
    this.enCache = agendaEnCache,
    this.equipos = _nombresDeEquipos,
  });

  /// Inyectables para las pruebas; por defecto, la API y la caché reales.
  final Future<List<Partido>> Function() obtener;
  final Future<AgendaGuardada?> Function() enCache;
  final Future<Map<int, String>> Function() equipos;

  @override
  State<AgendaPagina> createState() => _AgendaPaginaState();
}

class _AgendaPaginaState extends State<AgendaPagina> {
  /// Toda la agenda descargada; los filtros se aplican al dibujar.
  List<Partido>? _partidos;
  FiltroAgenda _filtro = const FiltroAgenda();
  Map<int, String> _equipos = {};
  bool _cargando = true;

  /// Cuándo se descargó la agenda que se está mostrando.
  DateTime? _descargada;

  /// La agenda en pantalla no está al día: el servidor no respondió.
  bool _sinConexion = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _cargar();
    widget.equipos().then((e) {
      if (mounted) setState(() => _equipos = e);
    });
  }

  Future<void> _cargar() async {
    setState(() => _cargando = true);
    final guardada = await widget.enCache();
    if (mounted && guardada != null && _partidos == null) {
      setState(() {
        _partidos = guardada.partidos;
        _descargada = guardada.guardado;
        _sinConexion = true; // hasta que responda el servidor
      });
    }
    try {
      final partidos = await widget.obtener();
      if (!mounted) return;
      setState(() {
        _partidos = partidos;
        _descargada = DateTime.now();
        _sinConexion = false;
        _error = null;
      });
    } on ErrorApi catch (e) {
      if (!mounted) return;
      setState(() {
        _sinConexion = false;
        _error = e.detalle;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _sinConexion = _partidos != null;
        _error = _partidos == null ? 'Sin conexión con el servidor.' : null;
      });
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final todos = _partidos;
    final agenda = todos == null ? null : Agenda(_filtro.aplicar(todos));
    final t = Theme.of(context);
    // El nombre del equipo solo aporta si el club tiene más de uno.
    final mostrarEquipo = _equipos.length > 1;
    return Scaffold(
      appBar: AppBar(title: const Text('Agenda de partidos')),
      body: RefreshIndicator(
        onRefresh: _cargar,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            if (_cargando && agenda == null)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_sinConexion && !_cargando && _descargada != null)
              _Mensaje(
                texto: 'Sin conexión: agenda guardada el '
                    '${fechaCorta(_descargada!)}. Desliza hacia abajo para actualizar.',
              ),
            if (_error != null) ...[
              _Mensaje(texto: _error!),
              OutlinedButton(onPressed: _cargar, child: const Text('Reintentar')),
              const SizedBox(height: 12),
            ],
            if (todos != null && todos.isNotEmpty)
              _Filtros(
                filtro: _filtro,
                equipos: mostrarEquipo ? _equipos : const {},
                onCambiar: (f) => setState(() => _filtro = f),
              ),
            if (todos != null && todos.isEmpty)
              Text('Todavía no hay partidos programados.', style: t.textTheme.bodyLarge),
            if (todos != null && todos.isNotEmpty && agenda!.vacia) ...[
              Text('Ningún partido coincide con los filtros.', style: t.textTheme.bodyLarge),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => setState(() => _filtro = const FiltroAgenda()),
                child: const Text('Quitar filtros'),
              ),
            ],
            if (agenda != null && agenda.proximos.isNotEmpty) ...[
              _Titulo('Próximos (${agenda.proximos.length})'),
              for (final p in agenda.proximos)
                TarjetaPartido(
                  partido: p,
                  equipo: mostrarEquipo ? _equipos[p.equipoId] : null,
                ),
            ],
            if (agenda != null && agenda.jugados.isNotEmpty) ...[
              _Titulo('Anteriores (${agenda.jugados.length})'),
              for (final p in agenda.jugados)
                TarjetaPartido(
                  partido: p,
                  equipo: mostrarEquipo ? _equipos[p.equipoId] : null,
                ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Chips de filtro: grandes y en una fila deslizable, para usar con una mano.
class _Filtros extends StatelessWidget {
  const _Filtros({required this.filtro, required this.equipos, required this.onCambiar});

  final FiltroAgenda filtro;

  /// Vacío si el club tiene un solo equipo: entonces no se muestra esa fila.
  final Map<int, String> equipos;
  final ValueChanged<FiltroAgenda> onCambiar;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Fila(
            etiqueta: 'Filtrar por momento',
            chips: [
              for (final m in Momento.values)
                _Chip(
                  texto: m.etiqueta,
                  elegido: filtro.momento == m,
                  onTap: () => onCambiar(filtro.conMomento(m)),
                ),
            ],
          ),
          if (equipos.isNotEmpty) ...[
            const SizedBox(height: 8),
            _Fila(
              etiqueta: 'Filtrar por equipo',
              chips: [
                _Chip(
                  texto: 'Todos los equipos',
                  elegido: filtro.equipoId == null,
                  onTap: () => onCambiar(filtro.conEquipo(null)),
                ),
                for (final e in equipos.entries)
                  _Chip(
                    texto: e.value,
                    elegido: filtro.equipoId == e.key,
                    onTap: () => onCambiar(filtro.conEquipo(e.key)),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _Fila extends StatelessWidget {
  const _Fila({required this.etiqueta, required this.chips});
  final String etiqueta;
  final List<Widget> chips;

  @override
  Widget build(BuildContext context) => Semantics(
        label: etiqueta,
        container: true,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final c in chips) Padding(padding: const EdgeInsets.only(right: 8), child: c),
            ],
          ),
        ),
      );
}

class _Chip extends StatelessWidget {
  const _Chip({required this.texto, required this.elegido, required this.onTap});
  final String texto;
  final bool elegido;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ChoiceChip(
        label: Text(texto, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        selected: elegido,
        onSelected: (_) => onTap(),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        materialTapTargetSize: MaterialTapTargetSize.padded,
      );
}

class TarjetaPartido extends StatelessWidget {
  const TarjetaPartido({super.key, required this.partido, this.equipo});

  final Partido partido;
  final String? equipo;

  @override
  Widget build(BuildContext context) {
    final p = partido;
    final t = Theme.of(context);
    final condicion = p.esLocal ? 'Local' : 'Visitante';
    final detalle = [
      fechaCorta(p.fechaHora),
      condicion,
      if (p.sede.isNotEmpty) p.sede,
      ?equipo,
    ].join(' · ');

    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        title: Text(
          'vs ${p.rival}',
          style: t.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w800,
            decoration: p.cancelado ? TextDecoration.lineThrough : null,
          ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(detalle, style: t.textTheme.bodyMedium),
              const SizedBox(height: 6),
              _EstadoChip(partido: p),
            ],
          ),
        ),
        trailing: p.conResultado
            ? Text('${p.golesFavor}-${p.golesContra}',
                key: Key('resultado-${p.id}'),
                style: t.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900))
            : const Icon(Icons.chevron_right),
        onTap: () => context.go('/partidos/${p.id}/alineacion'),
      ),
    );
  }
}

class _EstadoChip extends StatelessWidget {
  const _EstadoChip({required this.partido});
  final Partido partido;

  @override
  Widget build(BuildContext context) {
    final e = Theme.of(context).colorScheme;
    final destacado = partido.estado == 'EN_CURSO';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: destacado ? e.primary : e.surfaceContainerHighest,
        border: Border.all(color: e.outline),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        partido.estadoLegible,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: destacado ? e.onPrimary : e.onSurface,
        ),
      ),
    );
  }
}

class _Titulo extends StatelessWidget {
  const _Titulo(this.texto);
  final String texto;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
        child: Text(texto, style: Theme.of(context).textTheme.titleMedium),
      );
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
          style: TextStyle(color: e.onSecondaryContainer, fontWeight: FontWeight.w600)),
    );
  }
}
