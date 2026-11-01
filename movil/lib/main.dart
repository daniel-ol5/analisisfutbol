/// Área Técnica — aplicación móvil.
///
/// Cliente para el DT y el asistente de campo. Se organiza en los mismos seis
/// paquetes del modelo de casos de uso que el backend y la web.
library;

import 'package:flutter/material.dart';

import 'app/router.dart';
import 'app/tema.dart';
import 'shared/api/cliente.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Antes del primer cuadro, para no mostrar un tema y saltar a otro.
  await cargarModoTema();
  // T-026: si la sesión no se puede renovar, de vuelta al login.
  cliente.alSesionCaida = () => router.go('/login');
  runApp(const AreaTecnica());
}

class AreaTecnica extends StatelessWidget {
  const AreaTecnica({super.key});

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<ModoTema>(
        valueListenable: modoTema,
        builder: (_, modo, _) => MaterialApp.router(
          title: 'Área Técnica',
          debugShowCheckedModeBanner: false,
          theme: modo == ModoTema.sol ? temaSol : temaClaro,
          darkTheme: temaOscuro,
          themeMode: modo.themeMode,
          routerConfig: router,
        ),
      );
}
