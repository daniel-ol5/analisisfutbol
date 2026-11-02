/// Rutas de la aplicación, una sección por paquete del modelo de casos de uso.
///
/// Cada feature expone su página; este archivo es el único que las conoce:
/// las features no se importan entre sí.
library;

import 'package:go_router/go_router.dart';

import 'inicio.dart';
import 'marco.dart';
import '../shared/api/almacenamiento.dart';
import '../features/seguridad/pagina.dart';
import '../features/seguridad/perfil_pagina.dart';
import '../features/deportivo/pagina.dart';
import '../features/deportivo/alineacion/alineacion_pagina.dart';
import '../features/deportivo/alineacion/elegir_partido_pagina.dart';
import '../features/vision/pagina.dart';
import '../features/partido/pagina.dart';
import '../features/analisis/pagina.dart';
import '../features/asistencia/pagina.dart';

/// Pantalla de inicio de sesión (CU-02): la única ruta visible sin sesión.
const rutaLogin = '/seguridad';

final router = GoRouter(
  initialLocation: '/',
  // Sin sesión, cualquier ruta que no sea /seguridad ni /login redirige al login:
  // ningún módulo (ni siquiera Inicio) se ve antes de autenticarse.
  redirect: (context, state) async {
    final autenticado = await Almacenamiento.haySesion();
    if (!autenticado && state.matchedLocation != rutaLogin) return rutaLogin;
    return null;
  },
  routes: [
    final loc = state.matchedLocation;
    if (!autenticado &&
        loc != '/seguridad' &&
        loc != '/login' &&
        loc != '/perfil' &&
        !loc.startsWith('/partidos')) {
      return '/seguridad';
    }
    return null;
  },
  routes: [
    GoRoute(
      path: '/login',
      builder: (_, estado) =>
          LoginPagina(destino: estado.uri.queryParameters['desde'] ?? '/perfil'),
    ),
    GoRoute(
      path: '/seguridad',
      builder: (_, _) => const SeguridadPagina(),
    ),
    ShellRoute(
      builder: (_, _, child) => Marco(child: child),
      routes: [
        GoRoute(path: '/', builder: (_, _) => const Inicio()),
        GoRoute(path: '/perfil', builder: (_, _) => const PerfilPagina()),
        // T-053. PROVISORIO hasta T-052: /partidos será la agenda.
        GoRoute(path: '/partidos', builder: (_, _) => const ElegirPartidoPagina()),
        GoRoute(
          path: '/partidos/:id/alineacion',
          builder: (_, estado) => AlineacionPagina(
            partidoId: int.parse(estado.pathParameters['id']!),
          ),
        ),
        GoRoute(path: '/deportivo', builder: (_, _) => const DeportivoPagina()),
        GoRoute(path: '/vision', builder: (_, _) => const VisionPagina()),
        GoRoute(path: '/partido', builder: (_, _) => const PartidoPagina()),
        GoRoute(path: '/analisis', builder: (_, _) => const AnalisisPagina()),
        GoRoute(path: '/asistencia', builder: (_, _) => const AsistenciaPagina()),
      ],
    ),
  ],
);
