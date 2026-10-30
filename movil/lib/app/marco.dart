/// Marco común de las pantallas con sesión: barra de navegación inferior  —  T-023.
///
/// Abajo y con zonas táctiles de 72 dp para alcanzarla con el pulgar de una
/// sola mano, sin tener que estirarse hasta la parte superior de la pantalla.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class Marco extends StatelessWidget {
  const Marco({super.key, required this.child});
  final Widget child;

  static const _destinos = ['/', '/partidos', '/perfil'];

  @override
  Widget build(BuildContext context) {
    final ruta = GoRouterState.of(context).uri.path;
    final seleccionado = ruta.startsWith('/perfil')
        ? 2
        : ruta.startsWith('/partidos')
            ? 1
            : 0;

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: seleccionado,
        onDestinationSelected: (i) => context.go(_destinos[i]),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Inicio',
          ),
          NavigationDestination(
            icon: Icon(Icons.sports_soccer_outlined),
            selectedIcon: Icon(Icons.sports_soccer),
            label: 'Partidos',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Mi perfil',
          ),
        ],
      ),
    );
  }
}
