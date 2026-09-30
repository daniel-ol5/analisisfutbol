/// Análisis Táctico  —  P5
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class AnalisisPagina extends StatelessWidget {
  const AnalisisPagina({super.key});

  static const casos = [
    'CU-40 Partido en vivo',
    'CU-41 Plano 2D de posiciones',
    'CU-43 Métricas físicas por jugador',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P5',
        titulo: 'Análisis Táctico',
        casos: casos,
      );
}
