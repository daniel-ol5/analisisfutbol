/// Pantalla base de una feature todavía no implementada.
///
/// Muestra qué casos de uso le corresponden, para que quien la tome sepa de
/// entrada cuál es su alcance.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';

class Pendiente extends StatelessWidget {
  const Pendiente({
    super.key,
    required this.paquete,
    required this.titulo,
    required this.casos,
  });

  final String paquete;
  final String titulo;
  final List<String> casos;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(titulo, style: const TextStyle(fontSize: 18)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
        children: [
          Text(paquete,
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w700, color: verde)),
          const SizedBox(height: 10),
          Text('Pendiente de implementación. Casos de uso de este paquete:',
              style: t.textTheme.bodyMedium
                  ?.copyWith(color: t.colorScheme.onSurfaceVariant)),
          const SizedBox(height: 14),
          Card(
            child: Column(
              children: [
                for (var i = 0; i < casos.length; i++)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 18, vertical: 13),
                    decoration: BoxDecoration(
                      border: i == casos.length - 1
                          ? null
                          : Border(
                              bottom: BorderSide(
                                  color: t.colorScheme.outlineVariant)),
                    ),
                    child: Text(casos[i], style: const TextStyle(fontSize: 15)),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
