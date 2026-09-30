/// Gestión Deportiva  —  P2
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class DeportivoPagina extends StatelessWidget {
  const DeportivoPagina({super.key});

  static const casos = [
    'CU-09 Consultar equipos',
    'CU-11 Consultar plantel',
    'CU-15 Agenda de partidos',
    'CU-17 Ver alineación',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P2',
        titulo: 'Gestión Deportiva',
        casos: casos,
      );
}
