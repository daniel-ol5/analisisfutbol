import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/seguridad/api.dart' as seguridad;
import '../shared/ui/marca.dart';
import 'navegacion.dart';
import 'router.dart';
import 'tema.dart';

const _agenda = Modulo('/partidos', 'Partidos', Icons.sports_soccer_outlined);

class Marco extends StatefulWidget {
  const Marco({super.key, required this.ruta, required this.child});
  final String ruta;
  final Widget child;

  @override
  State<Marco> createState() => _MarcoState();
}

class _MarcoState extends State<Marco> {
  bool _compacto = false;
  bool _cerrando = false;

  int get _destino => switch (widget.ruta) {
    '/' => 0,
    final ruta
        when esRutaActiva(ruta, '/partidos') ||
            esRutaActiva(ruta, '/partido') =>
      1,
    final ruta when esRutaActiva(ruta, '/analisis') => 2,
    _ => 3,
  };

  Future<void> _cerrarSesion() async {
    if (_cerrando) return;
    setState(() => _cerrando = true);
    try {
      await seguridad.cerrarSesion();
    } catch (_) {
      // El servicio limpia la sesión local aunque la conexión se interrumpa.
    }
    if (mounted) context.go(rutaLogin);
  }

  Future<void> _abrirModulos() async {
    final accion = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: menuOscuro,
      constraints: const BoxConstraints(maxWidth: 520),
      useSafeArea: true,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        top: false,
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(12, 0, 12, 8),
              child: Text(
                'Módulos',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 21,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            for (final modulo in modulos)
              _EnlaceMenu(
                modulo: modulo,
                activo: esRutaActiva(widget.ruta, modulo.ruta),
                alTocar: () => Navigator.of(context).pop(modulo.ruta),
              ),
            const Divider(color: bordeMenu),
            _EnlaceMenu(
              modulo: const Modulo(
                rutaLogin,
                'Cerrar sesión',
                Icons.logout_rounded,
              ),
              alTocar: () => Navigator.of(context).pop(rutaLogin),
            ),
          ],
        ),
      ),
    );
    if (!mounted || accion == null) return;
    if (accion == rutaLogin) {
      await _cerrarSesion();
    } else {
      context.go(accion);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.sizeOf(context).width >= 780) {
      const opciones = [inicioModulo, _agenda, ...modulos];
      return Scaffold(
        body: Row(
          children: [
            ColoredBox(
              color: menuOscuro,
              child: SizedBox(
                width: _compacto ? 72 : 240,
                child: SafeArea(
                  right: false,
                  child: Column(
                    children: [
                      if (_compacto)
                        IconButton(
                          tooltip: 'Expandir menú',
                          onPressed: () => setState(() => _compacto = false),
                          icon: const Icon(
                            Icons.menu_open_rounded,
                            color: textoMenu,
                          ),
                        )
                      else
                        Row(
                          children: [
                            const SizedBox(width: 14),
                            const SelloArea(),
                            const SizedBox(width: 10),
                            const Expanded(
                              child: Text(
                                'Área Técnica',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            IconButton(
                              tooltip: 'Contraer menú',
                              onPressed: () => setState(() => _compacto = true),
                              icon: const Icon(
                                Icons.menu_open_rounded,
                                color: textoMenu,
                              ),
                            ),
                          ],
                        ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: ListView(
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          children: [
                            for (final modulo in opciones)
                              _EnlaceMenu(
                                modulo: modulo,
                                compacto: _compacto,
                                activo: esRutaActiva(widget.ruta, modulo.ruta),
                                alTocar: () => context.go(modulo.ruta),
                              ),
                          ],
                        ),
                      ),
                      const Divider(color: bordeMenu),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        child: _EnlaceMenu(
                          modulo: const Modulo(
                            rutaLogin,
                            'Cerrar sesión',
                            Icons.logout_rounded,
                          ),
                          compacto: _compacto,
                          alTocar: _cerrando ? null : _cerrarSesion,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Expanded(child: widget.child),
          ],
        ),
      );
    }

    return Scaffold(
      body: widget.child,
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
        ),
        child: NavigationBar(
          selectedIndex: _destino,
          onDestinationSelected: (indice) {
            switch (indice) {
              case 0:
                context.go('/');
              case 1:
                context.go('/partidos');
              case 2:
                context.go('/analisis');
              case 3:
                _abrirModulos();
            }
          },
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.grid_view_rounded),
              label: 'Inicio',
            ),
            NavigationDestination(
              icon: Icon(Icons.sports_soccer_outlined),
              label: 'Partidos',
            ),
            NavigationDestination(
              icon: Icon(Icons.analytics_outlined),
              label: 'Análisis',
            ),
            NavigationDestination(
              icon: Icon(Icons.more_horiz_rounded),
              label: 'Más',
            ),
          ],
        ),
      ),
    );
  }
}

class _EnlaceMenu extends StatelessWidget {
  const _EnlaceMenu({
    required this.modulo,
    this.alTocar,
    this.activo = false,
    this.compacto = false,
  });

  final Modulo modulo;
  final VoidCallback? alTocar;
  final bool activo;
  final bool compacto;

  @override
  Widget build(BuildContext context) {
    final color = activo ? limaMarca : textoMenu;
    final contenido = ListTile(
      selected: activo,
      leading: compacto ? null : Icon(modulo.icono, color: color, size: 22),
      title: compacto
          ? Icon(modulo.icono, color: color, size: 22)
          : Text(
              modulo.nombre,
              style: TextStyle(color: color, fontWeight: FontWeight.w600),
            ),
      dense: true,
      minTileHeight: 48,
      contentPadding: EdgeInsets.symmetric(horizontal: compacto ? 4 : 12),
      selectedTileColor: Colors.white.withValues(alpha: .09),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
      onTap: alTocar,
    );
    return compacto
        ? Tooltip(message: modulo.nombre, child: contenido)
        : contenido;
  }
}
