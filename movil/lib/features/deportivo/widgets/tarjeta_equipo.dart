/// Tarjeta de visualización de equipo de alto contraste  —  CU-09.
library;

import 'package:flutter/material.dart';

import '../../../app/tema.dart';
import '../modelos.dart';

class TarjetaEquipo extends StatelessWidget {
  const TarjetaEquipo({
    super.key,
    required this.equipo,
    this.onTap,
  });

  final Equipo equipo;
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Cabecera: Nombre del equipo en texto grande y legible
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    equipo.nombre,
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.2,
                      height: 1.2,
                    ),
                  ),
                ),
                if (!equipo.activo)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: rojo,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'INACTIVO',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),

            // Pills informativos: Categoría, Temporada, Cantidad de Jugadores
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                if (equipo.categoria.isNotEmpty)
                  _BadgeInfo(
                    etiqueta: equipo.categoria.toUpperCase(),
                    icono: Icons.shield_outlined,
                  ),
                if (equipo.temporada.isNotEmpty)
                  _BadgeInfo(
                    etiqueta: 'TEMP ${equipo.temporada}',
                    icono: Icons.calendar_today_outlined,
                  ),
                _BadgeInfo(
                  etiqueta: '${equipo.jugadores} JUGADORES',
                  icono: Icons.people_alt_outlined,
                  destacado: true,
                ),
              ],
            ),
            const SizedBox(height: 14),

            // Título de indumentaria de alta visibilidad
            const Text(
              'INDUMENTARIA OFICIAL (CU-10)',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.0,
              ),
            ),
            const SizedBox(height: 8),

            // Tres chips de colores (Titular, Suplente, Arquero)
            Row(
              children: [
                Expanded(
                  child: _ChipCamiseta(
                    rol: 'LOCAL',
                    color: equipo.colorLocalParsed,
                    hex: equipo.colorLocal,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _ChipCamiseta(
                    rol: 'VISITA',
                    color: equipo.colorVisitanteParsed,
                    hex: equipo.colorVisitante,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _ChipCamiseta(
                    rol: 'ARQUERO',
                    color: equipo.colorArqueroParsed,
                    hex: equipo.colorArquero,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _BadgeInfo extends StatelessWidget {
  const _BadgeInfo({
    required this.etiqueta,
    required this.icono,
    this.destacado = false,
  });

  final String etiqueta;
  final IconData icono;
  final bool destacado;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    final fondo = destacado
        ? (esOscuro ? verdeClaro.withValues(alpha: 0.16) : mentaSuave)
        : (esOscuro ? const Color(0xFF283548) : const Color(0xFFF1F5F9));
    final textoColor = destacado
        ? (esOscuro ? verdeClaro : verde)
        : (esOscuro ? Colors.white : pizarra);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: fondo,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: destacado
              ? (esOscuro ? verdeClaro : mentaBorde)
              : (esOscuro ? const Color(0xFF475569) : const Color(0xFFCBD5E1)),
          width: 1.2,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icono, size: 14, color: textoColor),
          const SizedBox(width: 4),
          Text(
            etiqueta,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: textoColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _ChipCamiseta extends StatelessWidget {
  const _ChipCamiseta({
    required this.rol,
    required this.color,
    required this.hex,
  });

  final String rol;
  final Color color;
  final String hex;

  @override
  Widget build(BuildContext context) {
    final esClaro = Equipo.esColorClaro(color);
    final textoColor = esClaro ? Colors.black : Colors.white;

    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: esClaro ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
          width: 1.6,
        ),
        boxShadow: const [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 3,
            offset: Offset(0, 1),
          ),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            rol,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w900,
              color: textoColor,
              letterSpacing: 0.5,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            hex.toUpperCase(),
            style: TextStyle(
              fontSize: 11,
              fontFamily: 'monospace',
              fontWeight: FontWeight.w700,
              color: textoColor.withValues(alpha: 0.85),
              height: 1.1,
            ),
          ),
        ],
      ),
    );
  }
}
