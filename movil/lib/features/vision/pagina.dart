/// Visión por Computadora  —  P3
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class VisionPagina extends StatelessWidget {
  const VisionPagina({super.key});

  static const casos = [
    'CU-18 Guía de montaje de cámara',
    'CU-27 Estado del procesamiento',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P3',
        titulo: 'Visión por Computadora',
        casos: casos,
      );
}
