/// Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
///
/// Cada feature expone su página; este archivo es el único que las conoce:
/// las features no se importan entre sí.
library;

import 'package:go_router/go_router.dart';

import 'inicio.dart';
import '../features/seguridad/pagina.dart';
import '../features/deportivo/pagina.dart';
import '../features/vision/pagina.dart';
import '../features/partido/pagina.dart';
import '../features/analisis/pagina.dart';
import '../features/asistencia/pagina.dart';
import '../shared/api/almacenamiento.dart';

final router = GoRouter(
  initialLocation: '/',
  // Sin sesión, cualquier ruta que no sea /seguridad redirige al login:
  // ningún módulo (ni siquiera Inicio) se ve antes de autenticarse.
  redirect: (context, state) async {
    final autenticado = await Almacenamiento.haySesion();
    if (!autenticado && state.matchedLocation != '/seguridad') return '/seguridad';
    return null;
  },
  routes: [
    GoRoute(path: '/', builder: (_, _) => const Inicio()),
    GoRoute(path: '/seguridad', builder: (_, _) => const SeguridadPagina()),
    GoRoute(path: '/deportivo', builder: (_, _) => const DeportivoPagina()),
    GoRoute(path: '/vision', builder: (_, _) => const VisionPagina()),
    GoRoute(path: '/partido', builder: (_, _) => const PartidoPagina()),
    GoRoute(path: '/analisis', builder: (_, _) => const AnalisisPagina()),
    GoRoute(path: '/asistencia', builder: (_, _) => const AsistenciaPagina()),
  ],
);
