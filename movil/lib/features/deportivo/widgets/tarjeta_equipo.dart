/// Tarjeta de Equipo diseñada para alto contraste bajo el sol  —  CU-09.
///
/// Sigue la dirección visual "Campo nocturno / Pizarra táctica":
/// - Tipografía grande y pesada (>= 18px en títulos, >= 14px en etiquetas)
/// - Bordes nítidos (1.5px a 2px) para no depender de sombras sutiles que se pierden al sol
/// - Chips de indumentaria con contraste dinámico blanco/negro según luminancia.
library;

import 'package:flutter/material.dart';

import '../../../app/tema.dart';
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
  });

  final Equipo equipo;
  final VoidCallback? onTap;
  final bool mostrarIndumentaria;
  final VoidCallback? onEditar;
  final VoidCallback? onDesactivar;
  final VoidCallback? onReactivar;
  final VoidCallback? onIrIndumentaria;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;
    final colorBorde =
        esOscuro ? const Color(0xFF475569) : const Color(0xFFCBD5E1);
    final tieneAccionesCrud =
        onEditar != null || onDesactivar != null || onReactivar != null;

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: colorBorde, width: 1.8),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Cabecera: Nombre del equipo + Estado / Jugadores
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Barra vertical con los 3 colores del equipo
                  Container(
                    width: 8,
                    height: 52,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: t.colorScheme.onSurface.withValues(alpha: 0.25),
                        width: 1,
                      ),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        Expanded(
                            child: Container(color: equipo.colorLocalParsed)),
                        Expanded(
                            child:
                                Container(color: equipo.colorVisitanteParsed)),
                        Expanded(
                            child: Container(color: equipo.colorArqueroParsed)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Nombre y Categoría
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          equipo.nombre,
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            height: 1.15,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 8,
                          runSpacing: 6,
                          children: [
                            if (equipo.categoria.isNotEmpty)
                              _EtiquetaDato(
                                icono: Icons.shield_outlined,
                                texto: equipo.categoria.toUpperCase(),
                                destacado: true,
                              ),
                            if (equipo.temporada.isNotEmpty)
                              _EtiquetaDato(
                                icono: Icons.calendar_today_outlined,
                                texto: 'TEMP ${equipo.temporada}',
                              ),
                            _EtiquetaDato(
                              icono: Icons.groups_2_outlined,
                              texto: '${equipo.jugadores} JUGADORES',
                            ),
                            if (!equipo.activo)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFA2372A)
                                      .withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(5),
                                  border: Border.all(
                                      color: const Color(0xFFA2372A)),
                                ),
                                child: const Text(
                                  'INACTIVO',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w900,
                                    color: Color(0xFFA2372A),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              if (mostrarIndumentaria) ...[
                const SizedBox(height: 14),
                const Divider(height: 1, thickness: 1.2),
                const SizedBox(height: 12),

                // Sección de Indumentaria (CU-10) con alto contraste
                Row(
                  children: [
                    Text(
                      'INDUMENTARIA OFICIAL (CU-10)',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.8,
                        color: t.colorScheme.onSurface.withValues(alpha: 0.75),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: _ChipIndumentaria(
                        etiqueta: 'LOCAL',
                        hex: equipo.colorLocal,
                        color: equipo.colorLocalParsed,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _ChipIndumentaria(
                        etiqueta: 'VISITA',
                        hex: equipo.colorVisitante,
                        color: equipo.colorVisitanteParsed,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _ChipIndumentaria(
                        etiqueta: 'ARQUERO',
                        hex: equipo.colorArquero,
                        color: equipo.colorArqueroParsed,
                      ),
                    ),
                  ],
                ),
              ],

              if (tieneAccionesCrud) ...[
                const SizedBox(height: 12),
                const Divider(height: 1, thickness: 1.1),
                const SizedBox(height: 10),
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    // Acceso rápido a Indumentaria (CU-10)
                    if (onIrIndumentaria != null)
                      InkWell(
                        onTap: onIrIndumentaria,
                        borderRadius: BorderRadius.circular(6),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 9, vertical: 6),
                          decoration: BoxDecoration(
                            color: t.colorScheme.surfaceContainerHighest
                                .withValues(alpha: 0.5),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                                color: t.colorScheme.outlineVariant),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              for (final c in [
                                equipo.colorLocalParsed,
                                equipo.colorVisitanteParsed,
                                equipo.colorArqueroParsed,
                              ])
                                Container(
                                  width: 11,
                                  height: 11,
                                  margin: const EdgeInsets.only(right: 3),
                                  decoration: BoxDecoration(
                                    color: c,
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                        color: Colors.black38, width: 0.8),
                                  ),
                                ),
                              const SizedBox(width: 3),
                              const Text(
                                'Kits CU-10',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
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
                        if (equipo.activo && onDesactivar != null)
                          TextButton(
                            onPressed: onDesactivar,
                            style: TextButton.styleFrom(
                              visualDensity: VisualDensity.compact,
                              foregroundColor: const Color(0xFFA2372A),
                            ),
                            child: const Text(
                              'Dar de baja',
                              style: TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w800),
                            ),
                          )
                        else if (!equipo.activo && onReactivar != null)
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
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _EtiquetaDato extends StatelessWidget {
  const _EtiquetaDato({
    required this.icono,
    required this.texto,
    this.destacado = false,
  });

  final IconData icono;
  final String texto;
  final bool destacado;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: destacado
            ? verde.withValues(alpha: esOscuro ? 0.25 : 0.12)
            : t.colorScheme.onSurface.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(
          color: destacado
              ? verde
              : t.colorScheme.onSurface.withValues(alpha: 0.25),
          width: 1.2,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icono,
            size: 13,
            color: destacado
                ? (esOscuro ? const Color(0xFF2DD4BF) : verde)
                : t.colorScheme.onSurface,
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              texto,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.4,
                color: destacado
                    ? (esOscuro ? const Color(0xFF2DD4BF) : verde)
                    : t.colorScheme.onSurface,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChipIndumentaria extends StatelessWidget {
  const _ChipIndumentaria({
    required this.etiqueta,
    required this.hex,
    required this.color,
  });

  final String etiqueta;
  final String hex;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final esClaro = Equipo.esColorClaro(color);
    final colorTexto = esClaro ? const Color(0xFF111111) : Colors.white;
    final colorBorde =
        esClaro ? const Color(0xFF333333) : const Color(0xFFCCCCCC);

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7, horizontal: 8),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: colorBorde, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            etiqueta,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.6,
              color: colorTexto,
            ),
          ),
          const SizedBox(height: 1),
          Text(
            hex.toUpperCase(),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              fontFamily: 'monospace',
              color: colorTexto,
            ),
          ),
        ],
      ),
    );
  }
}
