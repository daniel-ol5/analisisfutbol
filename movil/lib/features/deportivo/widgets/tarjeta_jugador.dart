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
    this.onEditar,
    this.onBaja,
    this.onReactivar,
  });

  final Jugador jugador;
  final VoidCallback? onTap;
  final VoidCallback? onEditar;
  final VoidCallback? onBaja;
  final VoidCallback? onReactivar;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    final colorBorde =
        esOscuro ? const Color(0xFF334155) : const Color(0xFFCBD5E1);
    final colorFondo = esOscuro ? pizarra : Colors.white;
    final tieneAcciones =
        onEditar != null || onBaja != null || onReactivar != null;

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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
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
            if (tieneAcciones) ...[
              const SizedBox(height: 10),
              const Divider(height: 1),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (onTap != null)
                    TextButton(
                      onPressed: onTap,
                      style: TextButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        foregroundColor: t.colorScheme.onSurface,
                      ),
                      child: const Text(
                        'Ver ficha',
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800),
                      ),
                    ),
                  if (onEditar != null)
                    TextButton(
                      onPressed: onEditar,
                      style: TextButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        foregroundColor: verde,
                      ),
                      child: const Text(
                        'Editar',
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800),
                      ),
                    ),
                  if (jugador.activo && onBaja != null)
                    TextButton(
                      onPressed: onBaja,
                      style: TextButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        foregroundColor: rojo,
                      ),
                      child: const Text(
                        'Dar de baja',
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800),
                      ),
                    )
                  else if (!jugador.activo && onReactivar != null)
                    TextButton(
                      onPressed: onReactivar,
                      style: TextButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        foregroundColor: verde,
                      ),
                      child: const Text(
                        'Reactivar',
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800),
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
