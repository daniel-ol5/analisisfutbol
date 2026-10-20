/// Gestión Deportiva  —  P2 · CU-09 … CU-17
///
/// T-044: Consulta de equipos en móvil (CU-09).
/// Criterio de aceptación: Carga en menos de 2 segundos y es legible al sol.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/tema.dart';
import '../../shared/api/almacenamiento.dart';
import 'api.dart';
import 'modelos.dart';
import 'widgets/tarjeta_equipo.dart';

class DeportivoPagina extends StatefulWidget {
  const DeportivoPagina({super.key});

  @override
  State<DeportivoPagina> createState() => _DeportivoPaginaState();
}

class _DeportivoPaginaState extends State<DeportivoPagina> {
  int _pestanaSeleccionada = 0;

  // Estados de la consulta de equipos (CU-09)
  List<Equipo> _equipos = [];
  bool _cargando = true;
  String? _error;
  bool _sesionIniciada = true;
  bool _conectandoDemo = false;

  // Filtros en memoria para respuesta instantánea (0 ms)
  String _busqueda = '';
  String _categoriaSeleccionada = 'TODOS';
  bool _mostrarInactivos = false;

  final TextEditingController _controladorBusqueda = TextEditingController();

  @override
  void initState() {
    super.initState();
    _cargarEquipos();
  }

  @override
  void dispose() {
    _controladorBusqueda.dispose();
    super.dispose();
  }

  Future<void> _cargarEquipos({bool forzarRed = false}) async {
    setState(() {
      _cargando = true;
      _error = null;
    });

    final hayToken = await Almacenamiento.haySesion();
    if (!hayToken) {
      if (mounted) {
        setState(() {
          _sesionIniciada = false;
          _cargando = false;
        });
      }
      return;
    }

    try {
      final res = await listarEquipos(
        activos: !_mostrarInactivos,
        forzarRed: forzarRed,
      );
      if (!mounted) return;
      setState(() {
        _equipos = res;
        _cargando = false;
        _sesionIniciada = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _cargando = false;
      });
    }
  }

  Future<void> _iniciarSesionDemo() async {
    setState(() => _conectandoDemo = true);
    try {
      await conectarSesionDemo();
      if (!mounted) return;
      setState(() => _sesionIniciada = true);
      await _cargarEquipos(forzarRed: true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Error de conexión demo: $e');
    } finally {
      if (mounted) setState(() => _conectandoDemo = false);
    }
  }

  List<String> get _categoriasDisponibles {
    final cats = <String>{'TODOS'};
    for (final eq in _equipos) {
      if (eq.categoria.isNotEmpty) cats.add(eq.categoria.toUpperCase());
    }
    return cats.toList();
  }

  List<Equipo> get _equiposFiltrados {
    return _equipos.where((e) {
      final coincideTexto = _busqueda.isEmpty ||
          e.nombre.toLowerCase().contains(_busqueda.toLowerCase()) ||
          e.categoria.toLowerCase().contains(_busqueda.toLowerCase()) ||
          e.temporada.toLowerCase().contains(_busqueda.toLowerCase());

      final coincideCat = _categoriaSeleccionada == 'TODOS' ||
          e.categoria.toUpperCase() == _categoriaSeleccionada;

      final coincideActivo = _mostrarInactivos || e.activo;

      return coincideTexto && coincideCat && coincideActivo;
    }).toList();
  }

  void _mostrarDetalleEquipo(Equipo eq) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final t = Theme.of(ctx);
        final esOscuro = t.brightness == Brightness.dark;
        final colorFondo =
            esOscuro ? const Color(0xFF14221C) : const Color(0xFFFFFFFF);
        final colorBorde =
            esOscuro ? const Color(0xFF62756A) : const Color(0xFF1E2D24);

        return Container(
          decoration: BoxDecoration(
            color: colorFondo,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            border: Border.all(color: colorBorde, width: 2.0),
          ),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: t.colorScheme.outline,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      eq.nombre,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.3,
                      ),
                    ),
                  ),
                  Text(
                    'EQ-${eq.id.toString().padLeft(2, '0')}',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      fontFamily: 'monospace',
                      color: verde,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Categoría: ${eq.categoria.isNotEmpty ? eq.categoria : "No especificada"}  ·  Temporada: ${eq.temporada.isNotEmpty ? eq.temporada : "2026"}',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Jugadores registrados: ${eq.jugadores}',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: t.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'COLORES DE INDUMENTARIA (CU-10)',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.0,
                ),
              ),
              const SizedBox(height: 10),
              _FilaColorDetalle(
                rol: 'Titular (Local)',
                color: eq.colorLocalParsed,
                hex: eq.colorLocal,
              ),
              const SizedBox(height: 8),
              _FilaColorDetalle(
                rol: 'Alternativa (Visita)',
                color: eq.colorVisitanteParsed,
                hex: eq.colorVisitante,
              ),
              const SizedBox(height: 8),
              _FilaColorDetalle(
                rol: 'Guardameta (Arquero)',
                color: eq.colorArqueroParsed,
                hex: eq.colorArquero,
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () => Navigator.pop(ctx),
                  style: FilledButton.styleFrom(
                    backgroundColor: verde,
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('CERRAR FICHA'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Gestión Deportiva',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/'),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              children: [
                _PestanaBoton(
                  titulo: 'Equipos',
                  codigo: 'CU-09',
                  activo: _pestanaSeleccionada == 0,
                  onTap: () => setState(() => _pestanaSeleccionada = 0),
                ),
                _PestanaBoton(
                  titulo: 'Plantel',
                  codigo: 'CU-11',
                  activo: _pestanaSeleccionada == 1,
                  onTap: () => setState(() => _pestanaSeleccionada = 1),
                ),
                _PestanaBoton(
                  titulo: 'Partidos',
                  codigo: 'CU-15',
                  activo: _pestanaSeleccionada == 2,
                  onTap: () => setState(() => _pestanaSeleccionada = 2),
                ),
                _PestanaBoton(
                  titulo: 'Alineación',
                  codigo: 'CU-17',
                  activo: _pestanaSeleccionada == 3,
                  onTap: () => setState(() => _pestanaSeleccionada = 3),
                ),
              ],
            ),
          ),
        ),
      ),
      body: _pestanaSeleccionada == 0
          ? _construirVistaEquipos(t, esOscuro)
          : _construirVistaCasosPendientes(_pestanaSeleccionada),
    );
  }

  Widget _construirVistaEquipos(ThemeData t, bool esOscuro) {
    return RefreshIndicator(
      onRefresh: () => _cargarEquipos(forzarRed: true),
      color: verde,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          // Banner de autenticación si no hay sesión
          if (!_sesionIniciada) ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: esOscuro
                    ? const Color(0xFF1E3528)
                    : const Color(0xFFE8F5E9),
                border: Border.all(color: verde, width: 2.0),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'SESIÓN REQUERIDA (CU-09)',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w900,
                      color: verde,
                      letterSpacing: 0.8,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Para consultar los equipos del club se requiere una sesión activa.',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _conectandoDemo ? null : _iniciarSesionDemo,
                      style: FilledButton.styleFrom(
                        backgroundColor: verde,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(
                        _conectandoDemo
                            ? 'CONECTANDO…'
                            : '⚡ CONECTAR SESIÓN DEMO',
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Banner de optimización y SLA (< 2s, legible al sol)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: esOscuro
                  ? const Color(0xFF182A22)
                  : const Color(0xFFF1F6F3),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: esOscuro
                    ? const Color(0xFF384B40)
                    : const Color(0xFFCCD7D0),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.wb_sunny_outlined, size: 18, color: verde),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Alto contraste para lectura al sol · Caché rápido (< 2s)',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: t.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Buscador rápido con botón para limpiar
          Container(
            decoration: BoxDecoration(
              color: t.colorScheme.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: esOscuro
                    ? const Color(0xFF62756A)
                    : const Color(0xFF1E2D24),
                width: 1.8,
              ),
            ),
            child: TextField(
              controller: _controladorBusqueda,
              onChanged: (val) => setState(() => _busqueda = val),
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
              decoration: InputDecoration(
                hintText: 'Buscar equipo o categoría…',
                hintStyle: TextStyle(
                  fontSize: 16,
                  color: t.colorScheme.outline,
                  fontWeight: FontWeight.w600,
                ),
                prefixIcon:
                    const Icon(Icons.search, size: 24, color: verde),
                suffixIcon: _busqueda.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _controladorBusqueda.clear();
                          setState(() => _busqueda = '');
                        },
                      )
                    : null,
                border: InputBorder.none,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Chips de categorías para filtrado rápido con una sola mano
          if (_categoriasDisponibles.length > 2) ...[
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final cat in _categoriasDisponibles)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: Text(
                          cat,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            color: _categoriaSeleccionada == cat
                                ? Colors.white
                                : (esOscuro ? Colors.white : Colors.black),
                          ),
                        ),
                        selected: _categoriaSeleccionada == cat,
                        selectedColor: verde,
                        backgroundColor: esOscuro
                            ? const Color(0xFF22332A)
                            : const Color(0xFFE8ECE9),
                        side: BorderSide(
                          color: _categoriaSeleccionada == cat
                              ? verde
                              : (esOscuro
                                  ? const Color(0xFF4C5C51)
                                  : const Color(0xFF9EACA2)),
                          width: 1.5,
                        ),
                        onSelected: (_) =>
                            setState(() => _categoriaSeleccionada = cat),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],

          // Cabecera con conteo de resultados
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${_equiposFiltrados.length} ${_equiposFiltrados.length == 1 ? "EQUIPO" : "EQUIPOS"} DEL CLUB',
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0.8,
                ),
              ),
              InkWell(
                onTap: () {
                  setState(() => _mostrarInactivos = !_mostrarInactivos);
                  _cargarEquipos();
                },
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(vertical: 4, horizontal: 4),
                  child: Row(
                    children: [
                      Icon(
                        _mostrarInactivos
                            ? Icons.check_box
                            : Icons.check_box_outline_blank,
                        size: 20,
                        color: verde,
                      ),
                      const SizedBox(width: 4),
                      const Text(
                        'Ver inactivos',
                        style: TextStyle(
                            fontSize: 14, fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Estado de carga inicial
          if (_cargando && _equipos.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Column(
                  children: [
                    CircularProgressIndicator(color: verde),
                    SizedBox(height: 16),
                    Text(
                      'Cargando equipos del club…',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            )
          else if (_error != null && _equipos.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFFA2372A).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFA2372A), width: 1.8),
              ),
              child: Column(
                children: [
                  const Icon(Icons.error_outline,
                      size: 36, color: Color(0xFFA2372A)),
                  const SizedBox(height: 10),
                  Text(
                    _error!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 14),
                  FilledButton(
                    onPressed: () => _cargarEquipos(forzarRed: true),
                    style: FilledButton.styleFrom(backgroundColor: verde),
                    child: const Text('REINTENTAR'),
                  ),
                ],
              ),
            )
          else if (_equiposFiltrados.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
              decoration: BoxDecoration(
                color: t.colorScheme.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: t.colorScheme.outlineVariant,
                  width: 1.5,
                ),
              ),
              child: Column(
                children: [
                  const Icon(Icons.shield_outlined,
                      size: 48, color: Color(0xFF74847A)),
                  const SizedBox(height: 12),
                  const Text(
                    'No se encontraron equipos',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _busqueda.isNotEmpty
                        ? 'Prueba modificando el texto de búsqueda.'
                        : 'No hay equipos registrados en el club.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 15,
                      color: t.colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            )
          else
            // Listado de equipos de alta legibilidad
            for (final eq in _equiposFiltrados)
              TarjetaEquipo(
                equipo: eq,
                onTap: () => _mostrarDetalleEquipo(eq),
              ),
        ],
      ),
    );
  }

  Widget _construirVistaCasosPendientes(int pestana) {
    final t = Theme.of(context);
    final datos = switch (pestana) {
      1 => (
          paquete: 'P2 · CU-11, CU-12',
          titulo: 'Consultar Plantel de Jugadores',
          responsable: 'Alex · Sprint 2',
          desc:
              'Consulta y búsqueda rápida de jugadores por dorsal, posición, altura antropométrica y pie hábil en campo.'
        ),
      2 => (
          paquete: 'P2 · CU-15',
          titulo: 'Agenda de Partidos',
          responsable: 'Susana · Sprint 2',
          desc:
              'Calendario de partidos programados con modo fuera de línea para consulta en cancha sin cobertura celular.'
        ),
      _ => (
          paquete: 'P2 · CU-17',
          titulo: 'Ver Alineación y Formación',
          responsable: 'Araceli · Sprint 2',
          desc:
              'Visualización táctica de los 11 titulares, suplentes y esquema de juego en la pizarra del encuentro.'
        ),
    };

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        Text(
          datos.paquete,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: verde,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          datos.titulo,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: verde.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: verde),
          ),
          child: Text(
            'Asignado a: ${datos.responsable}',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: verde,
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          datos.desc,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: t.colorScheme.onSurfaceVariant,
            height: 1.5,
          ),
        ),
      ],
    );
  }
}

class _PestanaBoton extends StatelessWidget {
  const _PestanaBoton({
    required this.titulo,
    required this.codigo,
    required this.activo,
    required this.onTap,
  });

  final String titulo;
  final String codigo;
  final bool activo;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: activo ? verde : Colors.transparent,
              width: 3.0,
            ),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              titulo,
              style: TextStyle(
                fontSize: 16,
                fontWeight: activo ? FontWeight.w900 : FontWeight.w600,
                color: activo ? verde : null,
              ),
            ),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: activo
                    ? verde.withValues(alpha: 0.15)
                    : Colors.grey.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(
                codigo,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  fontFamily: 'monospace',
                  color: activo ? verde : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilaColorDetalle extends StatelessWidget {
  const _FilaColorDetalle({
    required this.rol,
    required this.color,
    required this.hex,
  });

  final String rol;
  final Color color;
  final String hex;

  @override
  Widget build(BuildContext context) {
    final esClaro = Equipo.esColorClaro(color);
    final colorTexto = esClaro ? Colors.black : Colors.white;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: esClaro ? const Color(0xFF222222) : const Color(0xFFDDDDDD),
          width: 1.8,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            rol,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: colorTexto,
            ),
          ),
          Text(
            hex.toUpperCase(),
            style: TextStyle(
              fontSize: 14,
              fontFamily: 'monospace',
              fontWeight: FontWeight.w900,
              color: colorTexto,
            ),
          ),
        ],
      ),
    );
  }
}
