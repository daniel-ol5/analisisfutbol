/// Operación del Partido  —  P4
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class PartidoPagina extends StatelessWidget {
  const PartidoPagina({super.key});

  static const casos = [
    'CU-30 Cronómetro y control del partido',
    'CU-33 Cola de eventos sin conexión',
    'CU-34 Asignar jugadores a identificadores',
    'CU-36 Registrar gol',
    'CU-37 Registrar tarjeta',
    'CU-38 Registrar sustitución',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P4',
        titulo: 'Operación del Partido',
        casos: casos,
      );
}
