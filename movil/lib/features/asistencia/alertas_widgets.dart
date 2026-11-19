/// Barra de alertas para la pantalla del partido y tarjeta de una alerta  —  CU-52 (T-095).
///
/// HU-46, criterio 3: "Notificación destacada en la barra superior móvil". La
/// barra se inserta arriba del cronómetro del partido en vivo; la inyecta el
/// router (las features no se importan entre sí).
///
/// Lectura al sol: texto de 16 pt o más, colores sólidos con texto blanco o
/// pizarra (contraste alto), e ícono además del color para no depender de él.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import 'alertas_api.dart' as api;
import 'alertas_estado.dart';
import 'alertas_modelos.dart';

/// Fondo y texto de una alerta: riesgo de expulsión en rojo, fatiga en ámbar.
({Color fondo, Color texto, IconData icono}) estiloAlerta(TipoAlerta tipo) => switch (tipo) {
      TipoAlerta.riesgoExpulsion => (fondo: rojo, texto: Colors.white, icono: Icons.style),
      TipoAlerta.fatiga => (fondo: ambar, texto: pizarraOscura, icono: Icons.battery_alert),
    };

class BarraAlertas extends StatefulWidget {
  const BarraAlertas({
    super.key,
    required this.partidoId,
    this.obtener,
    this.intervalo = AlertasEstado.intervaloPorDefecto,
    this.alVer,
  });

  final int partidoId;
  final api.ObtenerAlertas? obtener;
  final Duration intervalo;

  /// Por defecto abre `/partidos/{id}/alertas`.
  final VoidCallback? alVer;

  @override
  State<BarraAlertas> createState() => _BarraAlertasState();
}

class _BarraAlertasState extends State<BarraAlertas> {
  late final AlertasEstado _estado = AlertasEstado(
    partidoId: widget.partidoId,
    obtener: widget.obtener,
    intervalo: widget.intervalo,
  )..iniciar();

  @override
  void dispose() {
    _estado.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: _estado,
        builder: (context, _) {
          final alertas = _estado.alertas;
          if (alertas.isEmpty) return const SizedBox.shrink();
          final primera = alertas.first;
          final estilo = estiloAlerta(primera.tipo);
          final otras = alertas.length - 1;
          return Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Semantics(
              liveRegion: true,
              button: true,
              label: 'Alerta: ${primera.mensaje}',
              child: Material(
                key: const Key('barra-alertas'),
                color: estilo.fondo,
                borderRadius: BorderRadius.circular(14),
                child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: widget.alVer ??
                      () => context.push('/partidos/${widget.partidoId}/alertas'),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
                    child: Row(
                      children: [
                        Icon(estilo.icono, color: estilo.texto, size: 30),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                primera.mensaje,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: estilo.texto,
                                  fontSize: 17,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              if (otras > 0 || _estado.sinConexion)
                                Text(
                                  [
                                    if (otras > 0)
                                      otras == 1 ? '+1 alerta más' : '+$otras alertas más',
                                    if (_estado.sinConexion) 'sin conexión',
                                  ].join(' · '),
                                  style: TextStyle(color: estilo.texto, fontSize: 16),
                                ),
                            ],
                          ),
                        ),
                        Icon(Icons.chevron_right, color: estilo.texto, size: 28),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      );
}

/// Una alerta completa, con su justificación y el botón "Entendido".
class TarjetaAlerta extends StatelessWidget {
  const TarjetaAlerta({
    super.key,
    required this.alerta,
    required this.alDescartar,
    this.nueva = false,
  });

  final Alerta alerta;
  final VoidCallback alDescartar;
  final bool nueva;

  @override
  Widget build(BuildContext context) {
    final estilo = estiloAlerta(alerta.tipo);
    return Card(
      key: Key('alerta-${alerta.clave}'),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: estilo.fondo, width: nueva ? 4 : 2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: estilo.fondo,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(estilo.icono, color: estilo.texto, size: 18),
                      const SizedBox(width: 6),
                      Text(
                        alerta.tipo.etiqueta,
                        style: TextStyle(
                          color: estilo.texto,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                Text(
                  "${alerta.minuto}'",
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              alerta.mensaje,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: pizarra),
            ),
            const SizedBox(height: 6),
            Text(alerta.justificacion, style: const TextStyle(fontSize: 16, color: pizarra)),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: Key('entendido-${alerta.clave}'),
                style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
                onPressed: alDescartar,
                child: const Text('Entendido', style: TextStyle(fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
