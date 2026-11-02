/// Mensaje destacado de error o de éxito, legible al sol: borde definido,
/// ícono contextual y texto en negrita sobre fondo de alto contraste.
library;

import 'package:flutter/material.dart';

class Aviso extends StatelessWidget {
  const Aviso({super.key, required this.texto, this.exito = false});

  final String texto;
  final bool exito;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final fondo = exito
        ? esquema.secondaryContainer
        : esquema.errorContainer.withValues(alpha: 0.35);
    final borde = exito ? esquema.primary : esquema.error;
    final colorTexto =
        exito ? esquema.onSecondaryContainer : esquema.onSurface;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: fondo,
        border: Border.all(color: borde, width: 1.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            exito ? Icons.check_circle_outline_rounded : Icons.error_outline_rounded,
            color: borde,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              texto,
              style: TextStyle(
                color: colorTexto,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
