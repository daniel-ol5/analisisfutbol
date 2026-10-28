/// Mensaje destacado de error o de éxito, legible al sol: borde grueso y texto
/// en negrita sobre fondo de color.
library;

import 'package:flutter/material.dart';

class Aviso extends StatelessWidget {
  const Aviso({super.key, required this.texto, this.exito = false});

  final String texto;
  final bool exito;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final fondo = exito ? esquema.secondaryContainer : esquema.errorContainer;
    final borde = exito ? esquema.primary : esquema.error;
    final colorTexto = exito ? esquema.onSecondaryContainer : esquema.onErrorContainer;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: fondo,
        border: Border.all(color: borde, width: 2),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(texto,
          style: TextStyle(color: colorTexto, fontWeight: FontWeight.w600)),
    );
  }
}
