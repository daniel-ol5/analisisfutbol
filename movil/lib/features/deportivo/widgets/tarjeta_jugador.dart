/// Tarjeta de visualización de jugador de alto contraste  —  CU-11.
library;

import 'package:flutter/material.dart';

import '../../../app/tema.dart';
import '../modelos.dart';

class TarjetaJugador extends StatelessWidget {
  const TarjetaJugador({
    super.key,
    required this.jugador,
    this.onTap,
  });

  final Jugador jugador;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    final colorBorde =
        esOscuro ? const Color(0xFF334155) : const Color(0xFFCBD5E1);
    final colorFondo = esOscuro ? pizarra : Colors.white;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colorFondo,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: colorBorde, width: 1.5),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: esOscuro ? 0.3 : 0.05),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Dorsal en bloque Teal de alto contraste
            Container(
              width: 48,
              height: 48,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: verde,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '${jugador.dorsal}',
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          jugador.nombreCompleto,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.2,
                          ),
                        ),
                      ),
                      if (!jugador.activo)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: rojo,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'BAJA',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${jugador.posicionLegible} · Pie ${jugador.pieLegible} · ${jugador.alturaCm} cm',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: t.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
