/// Asistencia y Reportes  —  P6
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class AsistenciaPagina extends StatelessWidget {
  const AsistenciaPagina({super.key});

  static const casos = [
    'CU-50 Recibir recomendación táctica',
    'CU-51 Valorar recomendación',
    'CU-52 Alertas de estado de jugador',
    'CU-53 Notificaciones push',
    'CU-55 Ver informe post-partido',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P6',
        titulo: 'Asistencia y Reportes',
        casos: casos,
      );
}
