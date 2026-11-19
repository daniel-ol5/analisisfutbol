import 'package:flutter/material.dart';

import 'api.dart';
import 'modelos.dart';

class SelectorPartido extends StatefulWidget {
  const SelectorPartido({super.key, required this.contenido});

  final Widget Function(Partido) contenido;

  @override
  State<SelectorPartido> createState() => _SelectorPartidoState();
}

class _SelectorPartidoState extends State<SelectorPartido> {
  late Future<List<Partido>> _agenda = listarPartidos();
  int? _seleccionado;

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Partido>>(
    future: _agenda,
    builder: (context, consulta) {
      if (consulta.hasError) {
        return Center(
          child: OutlinedButton.icon(
            onPressed: () => setState(() => _agenda = listarPartidos()),
            icon: const Icon(Icons.refresh),
            label: const Text('Reintentar agenda'),
          ),
        );
      }
      final partidos = consulta.data;
      if (partidos == null) {
        return const Center(child: CircularProgressIndicator());
      }
      if (partidos.isEmpty) {
        return const Center(child: Text('Todavía no hay partidos.'));
      }
      final actual = partidos.firstWhere(
        (partido) => partido.id == _seleccionado,
        orElse: () => partidos.firstWhere(
          (partido) => partido.estado == 'EN_CURSO',
          orElse: () => partidos.first,
        ),
      );
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: InputDecorator(
              decoration: const InputDecoration(
                labelText: 'Partido',
                contentPadding: EdgeInsets.symmetric(horizontal: 12),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  value: actual.id,
                  isExpanded: true,
                  items: [
                    for (final partido in partidos)
                      DropdownMenuItem(
                        value: partido.id,
                        child: Text(
                          'vs. ${partido.rival} · ${fechaCorta(partido.fechaHora)}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (id) => setState(() => _seleccionado = id),
                ),
              ),
            ),
          ),
          Expanded(
            child: KeyedSubtree(
              key: ValueKey(actual.id),
              child: widget.contenido(actual),
            ),
          ),
        ],
      );
    },
  );
}
