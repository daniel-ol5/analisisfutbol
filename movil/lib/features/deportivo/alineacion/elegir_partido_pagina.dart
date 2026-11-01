/// Entrada provisional a la alineación, mientras no exista la agenda.
///
/// PROVISORIO hasta T-052: la agenda de partidos necesita GET /deportivo/partidos
/// (CU-15, Susana). Cuando exista, esta pantalla se reemplaza por la agenda y
/// cada partido abre su alineación con un toque.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class ElegirPartidoPagina extends StatefulWidget {
  const ElegirPartidoPagina({super.key});

  @override
  State<ElegirPartidoPagina> createState() => _ElegirPartidoPaginaState();
}

class _ElegirPartidoPaginaState extends State<ElegirPartidoPagina> {
  final _formulario = GlobalKey<FormState>();
  final _numero = TextEditingController();

  @override
  void dispose() {
    _numero.dispose();
    super.dispose();
  }

  void _abrir() {
    if (!_formulario.currentState!.validate()) return;
    context.go('/partidos/${int.parse(_numero.text.trim())}/alineacion');
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Partidos')),
      body: Form(
        key: _formulario,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          children: [
            Text('La agenda de partidos todavía no está disponible.',
                style: t.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Mientras tanto, abre la alineación de un partido con su número.',
                style: t.textTheme.bodyMedium),
            const SizedBox(height: 20),
            TextFormField(
              controller: _numero,
              decoration: const InputDecoration(labelText: 'Número de partido'),
              keyboardType: TextInputType.number,
              textInputAction: TextInputAction.go,
              onFieldSubmitted: (_) => _abrir(),
              validator: (v) {
                final n = int.tryParse((v ?? '').trim());
                return n == null || n < 1 ? 'Escribe un número de partido válido.' : null;
              },
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _abrir,
              icon: const Icon(Icons.sports_soccer),
              label: const Text('Ver alineación'),
            ),
          ],
        ),
      ),
    );
  }
}
