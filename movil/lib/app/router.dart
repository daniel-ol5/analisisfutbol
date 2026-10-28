/// Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
///
/// Cada feature expone su página; este archivo es el único que las conoce:
/// las features no se importan entre sí.
library;

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import 'inicio.dart';
import 'marco.dart';
import '../shared/api/almacenamiento.dart';
import '../features/seguridad/login_pagina.dart';
import '../features/seguridad/pagina.dart';
import '../features/seguridad/perfil_pagina.dart';
import '../features/deportivo/pagina.dart';
import '../features/vision/pagina.dart';
import '../features/partido/pagina.dart';
import '../features/analisis/pagina.dart';
import '../features/asistencia/pagina.dart';

final router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/login',
      builder: (_, estado) =>
          LoginPagina(destino: estado.uri.queryParameters['desde'] ?? '/perfil'),
    ),
    ShellRoute(
      builder: (_, _, child) => Marco(child: child),
      routes: [
        GoRoute(path: '/', builder: (_, _) => const Inicio()),
        GoRoute(
          path: '/perfil',
          redirect: _requiereSesion,
          builder: (_, _) => const PerfilPagina(),
        ),
        GoRoute(path: '/seguridad', builder: (_, _) => const SeguridadPagina()),
        GoRoute(path: '/deportivo', builder: (_, _) => const DeportivoPagina()),
        GoRoute(path: '/vision', builder: (_, _) => const VisionPagina()),
        GoRoute(path: '/partido', builder: (_, _) => const PartidoPagina()),
        GoRoute(path: '/analisis', builder: (_, _) => const AnalisisPagina()),
        GoRoute(path: '/asistencia', builder: (_, _) => const AsistenciaPagina()),
      ],
    ),
  ],
);

/// Sin sesión guardada, manda al login y vuelve a la ruta pedida al entrar.
Future<String?> _requiereSesion(BuildContext _, GoRouterState estado) async {
  if (await Almacenamiento.haySesion()) return null;
  return Uri(path: '/login', queryParameters: {'desde': estado.uri.path})
      .toString();
}
