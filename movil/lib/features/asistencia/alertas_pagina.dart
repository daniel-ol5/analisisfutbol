/// Alertas del partido en vivo  —  CU-52 (HU-46, T-095).
///
/// Lista las alertas de fatiga y riesgo de expulsión de los jugadores propios
/// en cancha, se actualiza sola y permite marcarlas como "Entendido".
library;

import 'package:flutter/material.dart';

import '../../app/tema.dart';
import 'alertas_api.dart' as api;
import 'alertas_estado.dart';
import 'alertas_widgets.dart';

class AlertasPagina extends StatefulWidget {
  const AlertasPagina({
    super.key,
    required this.partidoId,
    this.obtener,
    this.intervalo = AlertasEstado.intervaloPorDefecto,
  });

  final int partidoId;
  final api.ObtenerAlertas? obtener;
  final Duration intervalo;

  @override
  State<AlertasPagina> createState() => _AlertasPaginaState();
}

class _AlertasPaginaState extends State<AlertasPagina> {
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
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Alertas del partido')),
        body: ListenableBuilder(
          listenable: _estado,
          builder: (context, _) {
            final alertas = _estado.alertas;
            return RefreshIndicator(
              onRefresh: _estado.consultar,
              color: verde,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: [
                  if (_estado.sinConexion)
                    const _Aviso(
                      texto: 'Sin conexión: se muestran las últimas alertas recibidas.',
                    ),
                  if (_estado.cargando && alertas.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  else if (alertas.isEmpty)
                    const _Aviso(
                      texto: 'Sin alertas por ahora. Se revisan solas cada 15 segundos.',
                    ),
                  for (final alerta in alertas)
                    TarjetaAlerta(
                      alerta: alerta,
                      nueva: _estado.nuevas.contains(alerta.clave),
                      alDescartar: () => _estado.descartar(alerta),
                    ),
                ],
              ),
            );
          },
        ),
      );
}

class _Aviso extends StatelessWidget {
  const _Aviso({required this.texto});
  final String texto;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Text(texto, style: const TextStyle(fontSize: 16, color: pizarra)),
      );
}
