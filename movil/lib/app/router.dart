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
import '../features/deportivo/agenda/agenda_pagina.dart';
import '../features/deportivo/alineacion/alineacion_pagina.dart';
import '../features/vision/pagina.dart';
import '../features/partido/pagina.dart';
import '../features/analisis/pagina.dart';
import '../features/analisis/resumen_pagina.dart';
import '../features/asistencia/pagina.dart';

/// Pantalla de inicio de sesión (CU-02).
const rutaLogin = '/seguridad';

final router = GoRouter(
  initialLocation: '/',
  // Sin sesión, cualquier ruta que no sea /seguridad redirige al login:
  // ningún módulo (ni siquiera Inicio) se ve antes de autenticarse.
  redirect: (context, state) async {
    final autenticado = await Almacenamiento.haySesion();
    if (!autenticado && state.matchedLocation != rutaLogin) return rutaLogin;
    return null;
  },
  routes: [
    GoRoute(
      path: '/seguridad',
      builder: (_, _) => const SeguridadPagina(),
    ),
    // T-081: resumen de métricas a pantalla completa (fuera del Marco: sin la
    // barra inferior, para que todo entre sin desplazamiento).
    GoRoute(
      path: '/partidos/:id/resumen',
      builder: (_, estado) => ResumenPagina(
        partidoId: int.parse(estado.pathParameters['id']!),
      ),
    ),
    ShellRoute(
      builder: (_, _, child) => Marco(child: child),
      routes: [
        GoRoute(path: '/', builder: (_, _) => const Inicio()),
        GoRoute(path: '/perfil', builder: (_, _) => const PerfilPagina()),
        // T-052 agenda; cada partido abre su alineación (T-053).
        GoRoute(path: '/partidos', builder: (_, _) => const AgendaPagina()),
        GoRoute(
          path: '/partidos/:id/alineacion',
          builder: (_, estado) => AlineacionPagina(
            partidoId: int.parse(estado.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: '/partidos/:id/eventos',
          builder: (_, estado) => PartidoPagina(
            partidoId: int.parse(estado.pathParameters['id']!),
          ),
        ),
        GoRoute(path: '/deportivo', builder: (_, _) => const DeportivoPagina()),
        GoRoute(path: '/vision', builder: (_, _) => const VisionPagina()),
        GoRoute(path: '/partido', builder: (_, _) => const PartidoPagina()),
        GoRoute(
          path: '/partido/:id',
          builder: (_, estado) => PartidoPagina(
            partidoId: int.parse(estado.pathParameters['id']!),
          ),
        ),
        GoRoute(path: '/analisis', builder: (_, _) => const AnalisisPagina()),
        GoRoute(path: '/asistencia', builder: (_, _) => const AsistenciaPagina()),
      ],
    ),
  ],
);
