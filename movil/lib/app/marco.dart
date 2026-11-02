/// Marco común de las pantallas con sesión: Sidebar estructurado (#1F2937) +
/// barra inferior adaptable  —  T-023.
///
/// - En pantallas anchas (>= 780 dp, Chrome Web / Tablet): muestra el Sidebar
///   lateral fijo en gris pizarra (#1F2937) organizado por categorías igual que
///   la aplicación web.
/// - En pantallas móviles (< 780 dp): muestra la barra inferior de 70 dp para
///   uso con el pulgar + un botón «Menú» que despliega el mismo Sidebar como
///   Drawer lateral sin superponer cabeceras.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/seguridad/api.dart' as seguridad_api;
import 'tema.dart';

class _ItemMenu {
  const _ItemMenu({
    required this.ruta,
    required this.nombre,
    required this.icono,
    this.paquete,
  });

  final String ruta;
  final String nombre;
  final IconData icono;
  final String? paquete;
}

class _GrupoMenu {
  const _GrupoMenu(this.categoria, this.items);
  final String categoria;
  final List<_ItemMenu> items;
}

const _gruposMenu = [
  _GrupoMenu('PRINCIPAL', [
    _ItemMenu(
      ruta: '/',
      nombre: 'Panel de Inicio',
      icono: Icons.grid_view_rounded,
    ),
  ]),
  _GrupoMenu('COMPETICIÓN Y VISIÓN', [
    _ItemMenu(
      ruta: '/deportivo',
      nombre: 'Gestión Deportiva',
      icono: Icons.shield_outlined,
      paquete: 'P2',
    ),
    _ItemMenu(
      ruta: '/partidos',
      nombre: 'Agenda y Alineación',
      icono: Icons.sports_soccer_outlined,
      paquete: 'CU-17',
    ),
    _ItemMenu(
      ruta: '/vision',
      nombre: 'Visión por Computadora',
      icono: Icons.videocam_outlined,
      paquete: 'P3',
    ),
    _ItemMenu(
      ruta: '/partido',
      nombre: 'Operación del Partido',
      icono: Icons.stadium_outlined,
      paquete: 'P4',
    ),
  ]),
  _GrupoMenu('ANÁLISIS Y REPORTES', [
    _ItemMenu(
      ruta: '/analisis',
      nombre: 'Análisis Táctico',
      icono: Icons.analytics_outlined,
      paquete: 'P5',
    ),
    _ItemMenu(
      ruta: '/asistencia',
      nombre: 'Asistencia y Reportes',
      icono: Icons.description_outlined,
      paquete: 'P6',
    ),
  ]),
  _GrupoMenu('ADMINISTRACIÓN', [
    _ItemMenu(
      ruta: '/perfil',
      nombre: 'Mi perfil y Pantalla',
      icono: Icons.person_outline,
      paquete: 'P1',
    ),
  ]),
];

class Marco extends StatefulWidget {
  const Marco({super.key, required this.child});
  final Widget child;

  @override
  State<Marco> createState() => _MarcoState();
}

class _MarcoState extends State<Marco> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  static const _destinosInferiores = ['/', '/deportivo', '/partidos', '/perfil'];

  int _indiceInferior(String ruta) {
    if (ruta.startsWith('/perfil')) return 3;
    if (ruta.startsWith('/partidos')) return 2;
    if (ruta.startsWith('/deportivo')) return 1;
    return 0;
  }

  bool _esRutaActiva(String rutaActual, String rutaItem) {
    if (rutaItem == '/') return rutaActual == '/';
    return rutaActual == rutaItem || rutaActual.startsWith('$rutaItem/');
  }

  Future<void> _cerrarSesion(BuildContext context) async {
    try {
      await seguridad_api.cerrarSesion();
    } catch (_) {}
    if (!context.mounted) return;
    context.go('/seguridad');
  }

  @override
  Widget build(BuildContext context) {
    final ruta = GoRouterState.of(context).uri.path;
    final ancho = MediaQuery.sizeOf(context).width;
    final esPantallaAncha = ancho >= 780;

    if (esPantallaAncha) {
      return Scaffold(
        body: Row(
          children: [
            SizedBox(
              width: 268,
              child: _SidebarEstructurado(
                rutaActual: ruta,
                esActiva: (r) => _esRutaActiva(ruta, r),
                alNavegar: (destino) => context.go(destino),
                alCerrarSesion: () => _cerrarSesion(context),
              ),
            ),
            Expanded(child: widget.child),
          ],
        ),
      );
    }

    final seleccionado = _indiceInferior(ruta);

    return Scaffold(
      key: _scaffoldKey,
      drawer: Drawer(
        width: 284,
        backgroundColor: pizarra,
        shape: const RoundedRectangleBorder(),
        child: _SidebarEstructurado(
          rutaActual: ruta,
          esActiva: (r) => _esRutaActiva(ruta, r),
          alNavegar: (destino) {
            Navigator.of(context).pop();
            context.go(destino);
          },
          alCerrarSesion: () {
            Navigator.of(context).pop();
            _cerrarSesion(context);
          },
        ),
      ),
      body: widget.child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
              width: 1,
            ),
          ),
        ),
        child: NavigationBar(
          selectedIndex: seleccionado,
          onDestinationSelected: (i) {
            if (i == 4) {
              _scaffoldKey.currentState?.openDrawer();
              return;
            }
            context.go(_destinosInferiores[i]);
          },
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.grid_view_outlined),
              selectedIcon: Icon(Icons.grid_view_rounded, color: verde),
              label: 'Inicio',
            ),
            NavigationDestination(
              icon: Icon(Icons.shield_outlined),
              selectedIcon: Icon(Icons.shield, color: verde),
              label: 'Deportivo',
            ),
            NavigationDestination(
              icon: Icon(Icons.sports_soccer_outlined),
              selectedIcon: Icon(Icons.sports_soccer, color: verde),
              label: 'Partidos',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              selectedIcon: Icon(Icons.person, color: verde),
              label: 'Mi perfil',
            ),
            NavigationDestination(
              icon: Icon(Icons.menu_rounded),
              selectedIcon: Icon(Icons.menu_open_rounded),
              label: 'Módulos',
            ),
          ],
        ),
      ),
    );
  }
}

class _SidebarEstructurado extends StatelessWidget {
  const _SidebarEstructurado({
    required this.rutaActual,
    required this.esActiva,
    required this.alNavegar,
    required this.alCerrarSesion,
  });

  final String rutaActual;
  final bool Function(String ruta) esActiva;
  final ValueChanged<String> alNavegar;
  final VoidCallback alCerrarSesion;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: pizarra,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Cabecera de marca en #1F2937
            Container(
              padding: const EdgeInsets.fromLTRB(18, 20, 18, 16),
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Color(0xFF334155), width: 1),
                ),
              ),
              child: InkWell(
                onTap: () => alNavegar('/'),
                borderRadius: BorderRadius.circular(8),
                child: Row(
                  children: [
                    Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [verde, verdeClaro],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: [
                          BoxShadow(
                            color: verde.withValues(alpha: 0.35),
                            blurRadius: 8,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.sports_soccer,
                        color: Colors.white,
                        size: 21,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          RichText(
                            text: const TextSpan(
                              style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w900,
                                color: Colors.white,
                                letterSpacing: -0.3,
                              ),
                              children: [
                                TextSpan(text: 'Área '),
                                TextSpan(
                                  text: 'Técnica',
                                  style: TextStyle(color: verdeClaro),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            'Telemetría y Visión',
                            style: TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w500,
                              color: Color(0xFF94A3B8),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Lista de navegación agrupada por categorías
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                children: [
                  for (final grupo in _gruposMenu) ...[
                    Padding(
                      padding: const EdgeInsets.fromLTRB(10, 6, 10, 6),
                      child: Text(
                        grupo.categoria,
                        style: const TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.0,
                          color: Color(0xFF94A3B8),
                        ),
                      ),
                    ),
                    for (final item in grupo.items)
                      _TileSidebar(
                        item: item,
                        activo: esActiva(item.ruta),
                        onTap: () => alNavegar(item.ruta),
                      ),
                    const SizedBox(height: 12),
                  ],
                ],
              ),
            ),

            // Pie del Sidebar: Selector rápido de tema + Cerrar sesión
            Container(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
              decoration: const BoxDecoration(
                color: Color(0xFF17202E),
                border: Border(
                  top: BorderSide(color: Color(0xFF334155), width: 1),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ValueListenableBuilder<ModoTema>(
                    valueListenable: modoTema,
                    builder: (_, modoActual, _) => Row(
                      children: [
                        for (final opcion in [
                          ModoTema.claro,
                          ModoTema.oscuro,
                          ModoTema.sol,
                        ])
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 2),
                              child: InkWell(
                                onTap: () => cambiarModoTema(opcion),
                                borderRadius: BorderRadius.circular(6),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 6),
                                  decoration: BoxDecoration(
                                    color: modoActual == opcion
                                        ? verdeClaro.withValues(alpha: 0.18)
                                        : Colors.transparent,
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(
                                      color: modoActual == opcion
                                          ? verdeClaro
                                          : const Color(0xFF334155),
                                    ),
                                  ),
                                  alignment: Alignment.center,
                                  child: Text(
                                    opcion.etiqueta,
                                    style: TextStyle(
                                      fontSize: 11.5,
                                      fontWeight: FontWeight.w700,
                                      color: modoActual == opcion
                                          ? verdeClaro
                                          : const Color(0xFFCBD5E1),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  InkWell(
                    onTap: alCerrarSesion,
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 9,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.04),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF334155)),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.logout_rounded,
                            size: 16,
                            color: Color(0xFFCBD5E1),
                          ),
                          SizedBox(width: 8),
                          Text(
                            'Cerrar sesión',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFFCBD5E1),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TileSidebar extends StatelessWidget {
  const _TileSidebar({
    required this.item,
    required this.activo,
    required this.onTap,
  });

  final _ItemMenu item;
  final bool activo;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorTexto = activo ? Colors.white : const Color(0xFFCBD5E1);
    final colorIcono = activo ? verdeClaro : const Color(0xFF94A3B8);

    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 10),
          decoration: BoxDecoration(
            color: activo
                ? verdeClaro.withValues(alpha: 0.15)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: Border(
              left: BorderSide(
                color: activo ? verdeClaro : Colors.transparent,
                width: 3,
              ),
            ),
          ),
          child: Row(
            children: [
              Icon(item.icono, size: 19, color: colorIcono),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  item.nombre,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: activo ? FontWeight.w700 : FontWeight.w500,
                    color: colorTexto,
                  ),
                ),
              ),
              if (item.paquete != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: activo
                        ? verdeClaro.withValues(alpha: 0.2)
                        : const Color(0xFF283548),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    item.paquete!,
                    style: TextStyle(
                      fontSize: 10,
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.w700,
                      color: activo ? verdeClaro : const Color(0xFF94A3B8),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
