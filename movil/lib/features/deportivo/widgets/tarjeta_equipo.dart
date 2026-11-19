import 'package:flutter/material.dart';

import '../modelos.dart';

class TarjetaEquipo extends StatelessWidget {
  const TarjetaEquipo({
    super.key,
    required this.equipo,
    this.onTap,
    this.mostrarIndumentaria = true,
    this.onEditar,
    this.onDesactivar,
    this.onReactivar,
    this.onIrIndumentaria,
    this.onIrPlantel,
  });

  final Equipo equipo;
  final bool mostrarIndumentaria;
  final VoidCallback? onTap, onEditar, onDesactivar, onReactivar;
  final VoidCallback? onIrIndumentaria, onIrPlantel;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final esquema = tema.colorScheme;
    final datos = [
      equipo.categoria,
      equipo.temporada,
    ].where((dato) => dato.isNotEmpty).join(' · ');
    final jugadores =
        '${equipo.jugadores} ${equipo.jugadores == 1 ? 'jugador' : 'jugadores'}';
    final accionEstado = equipo.activo ? onDesactivar : onReactivar;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 13, 14, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(equipo.nombre, style: tema.textTheme.titleMedium),
              if (datos.isNotEmpty)
                Text(datos, style: TextStyle(color: esquema.onSurfaceVariant)),
              if (!equipo.activo)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'Inactivo',
                    style: TextStyle(
                      color: esquema.error,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              if (onIrPlantel != null || onIrIndumentaria != null)
                Wrap(
                  spacing: 8,
                  children: [
                    if (onIrPlantel != null)
                      TextButton.icon(
                        onPressed: onIrPlantel,
                        icon: const Icon(Icons.groups_outlined, size: 19),
                        label: Text(jugadores),
                      )
                    else
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Text(
                          jugadores,
                          style: TextStyle(color: esquema.onSurfaceVariant),
                        ),
                      ),
                    if (onIrIndumentaria != null)
                      TextButton.icon(
                        onPressed: onIrIndumentaria,
                        icon: const Icon(Icons.checkroom_outlined, size: 19),
                        label: const Text('Indumentaria'),
                      ),
                  ],
                )
              else
                Text(
                  jugadores,
                  style: TextStyle(color: esquema.onSurfaceVariant),
                ),
              if (mostrarIndumentaria) ...[
                const SizedBox(height: 12),
                Text('Indumentaria', style: tema.textTheme.labelLarge),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 12,
                  runSpacing: 6,
                  children: [
                    for (final (nombre, hex, color) in [
                      ('Titular', equipo.colorLocal, equipo.colorLocalParsed),
                      (
                        'Alternativa',
                        equipo.colorVisitante,
                        equipo.colorVisitanteParsed,
                      ),
                      (
                        'Arquero',
                        equipo.colorArquero,
                        equipo.colorArqueroParsed,
                      ),
                    ])
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 16,
                            height: 16,
                            decoration: BoxDecoration(
                              color: color,
                              shape: BoxShape.circle,
                              border: Border.all(color: esquema.outlineVariant),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              '$nombre · $hex',
                              style: TextStyle(color: esquema.onSurfaceVariant),
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ],
              if (onEditar != null || accionEstado != null) ...[
                const Divider(height: 1),
                Wrap(
                  spacing: 8,
                  children: [
                    if (onEditar != null)
                      TextButton(
                        onPressed: onEditar,
                        child: const Text('Editar'),
                      ),
                    if (accionEstado != null)
                      TextButton(
                        onPressed: accionEstado,
                        child: Text(
                          equipo.activo ? 'Dar de baja' : 'Reactivar',
                        ),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
