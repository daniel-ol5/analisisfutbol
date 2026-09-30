/// Área Técnica — aplicación móvil.
///
/// Cliente para el DT y el asistente de campo. Se organiza en los mismos seis
/// paquetes del modelo de casos de uso que el backend y la web.
library;

import 'package:flutter/material.dart';

import 'app/router.dart';
import 'app/tema.dart';

void main() => runApp(const AreaTecnica());

class AreaTecnica extends StatelessWidget {
  const AreaTecnica({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp.router(
        title: 'Área Técnica',
        debugShowCheckedModeBanner: false,
        theme: temaClaro,
        darkTheme: temaOscuro,
        routerConfig: router,
      );
}
