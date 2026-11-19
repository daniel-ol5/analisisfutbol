/// Área Técnica — aplicación móvil.
///
/// Cliente para el DT y el asistente de campo. Se organiza en los mismos seis
/// paquetes del modelo de casos de uso que el backend y la web.
library;

import 'dart:async';

import 'package:flutter/material.dart';

import 'app/router.dart';
import 'app/tema.dart';
import 'features/asistencia/push.dart';
import 'shared/api/cliente.dart';

/// Para los avisos que no dependen de una pantalla (push con la app abierta, T-096).
final avisosGlobales = GlobalKey<ScaffoldMessengerState>();

void _avisarPush(String texto, String ruta) {
  avisosGlobales.currentState
    ?..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(texto, style: const TextStyle(fontSize: 16)),
      duration: const Duration(seconds: 10),
      action: SnackBarAction(label: 'Ver', onPressed: () => router.go(ruta)),
    ));
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Antes del primer cuadro, para no mostrar un tema y saltar a otro.
  await cargarModoTema();
  // T-026: si la sesión no se puede renovar, de vuelta al login.
  cliente.alSesionCaida = () => router.go(rutaLogin);
  runApp(const AreaTecnica());
  // T-096: solo si se compiló con la configuración de Firebase (si no, no hace nada).
  unawaited(iniciarPush(navegar: router.go, avisar: _avisarPush));
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
          scaffoldMessengerKey: avisosGlobales,
        ),
      );
}
