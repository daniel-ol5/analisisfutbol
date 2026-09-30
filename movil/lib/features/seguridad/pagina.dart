/// Seguridad y Administración  —  P1
library;

import 'package:flutter/material.dart';

import '../../shared/ui/pendiente.dart';

class SeguridadPagina extends StatelessWidget {
  const SeguridadPagina({super.key});

  static const casos = [
    'CU-01 Registrar club',
    'CU-02 Iniciar sesión',
    'CU-03 Cerrar sesión',
    'CU-04 Gestionar usuarios y roles',
    'CU-05 Administrar perfil propio',
  ];

  @override
  Widget build(BuildContext context) => const Pendiente(
        paquete: 'P1',
        titulo: 'Seguridad y Administración',
        casos: casos,
      );
}
