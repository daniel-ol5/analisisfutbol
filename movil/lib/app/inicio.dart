/// Pantalla de inicio: los seis paquetes y el estado de la conexión.
///
/// La comprobación de salud es el «walking skeleton» del Sprint 1: si esto
/// responde, la app y el backend están hablándose de verdad.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/seguridad/api.dart' as seguridad_api;
import '../shared/api/cliente.dart';
import 'tema.dart';

class Paquete {
  const Paquete(
    this.id,
    this.ruta,
    this.nombre,
    this.descripcion,
    this.cus,
    this.icono,
  );
  final String id, ruta, nombre, descripcion, cus;
  final IconData icono;
}

const paquetes = [
  Paquete(
    'P1',
    'seguridad',
    'Seguridad y Administración',
    'Control de acceso, perfil personal y sesiones activas.',
    'CU-01 … CU-08',
    Icons.person_outline,
  ),
  Paquete(
    'P2',
    'deportivo',
    'Gestión Deportiva',
    'Equipos, colores de indumentaria, plantel y alineación.',
    'CU-09 … CU-17',
    Icons.shield_outlined,
  ),
  Paquete(
    'P3',
    'vision',
    'Visión por Computadora',
    'Montaje de cámara, calibración de cancha y procesamiento óptico.',
    'CU-18 … CU-29',
    Icons.videocam_outlined,
  ),
  Paquete(
    'P4',
    'partido',
    'Operación del Partido',
    'Seguimiento en vivo del encuentro y eventos en tiempo real.',
    'CU-30 … CU-39',
    Icons.stadium_outlined,
  ),
  Paquete(
    'P5',
    'analisis',
    'Análisis Táctico',
    'Mapas de calor, distancias recorridas y métricas colectivas.',
    'CU-40 … CU-48',
    Icons.analytics_outlined,
  ),
  Paquete(
    'P6',
    'asistencia',
    'Asistencia y Reportes',
    'Informes post-partido y exportación ejecutiva.',
    'CU-49 … CU-58',
    Icons.description_outlined,
  ),
];

class Inicio extends StatefulWidget {
  const Inicio({super.key});
  @override
  State<Inicio> createState() => _InicioState();
}

class _InicioState extends State<Inicio> {
  String _estado = 'Conectando con la API…';
  bool _ok = false;
  bool _error = false;
  bool _cerrandoSesion = false;

  @override
  void initState() {
    super.initState();
    _verificarSalud();
  }

  Future<void> _verificarSalud() async {
    try {
      final r = await cliente.get('/salud');
      if (!mounted) return;
      setState(() {
        _ok = true;
        _error = false;
        _estado = 'API conectada · v${r['version']}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _ok = false;
        _error = true;
        _estado = 'Sin conexión — ¿está corriendo el backend?';
      });
    }
  }

  Future<void> _cerrarSesion() async {
    setState(() => _cerrandoSesion = true);
    try {
      await seguridad_api.cerrarSesion();
    } catch (_) {}
    if (!mounted) return;
    context.go('/seguridad');
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final esOscuro = t.brightness == Brightness.dark;
    final colorEstado = _ok ? verde : (_error ? rojo : t.colorScheme.outline);
    final fondoEstado = _ok
        ? (esOscuro ? verdeClaro.withValues(alpha: 0.14) : mentaSuave)
        : (_error
            ? rojo.withValues(alpha: 0.1)
            : t.colorScheme.surface);
    final modulos = paquetes.where((p) => p.id != 'P1');

    return Scaffold(
      appBar: AppBar(
        title: const Text('Panel de Inicio'),
        actions: [
          IconButton(
            tooltip: 'Actualizar estado de la API',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _verificarSalud,
          ),
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: _cerrandoSesion
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.logout_rounded),
            onPressed: _cerrandoSesion ? null : _cerrarSesion,
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _verificarSalud,
          color: verde,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            children: [
              // Tarjeta Hero con la nueva paleta Teal / Slate
              Container(
                padding: const EdgeInsets.all(22),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: esOscuro
                        ? [pizarra, const Color(0xFF134E4A)]
                        : [Colors.white, mentaSuave],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: esOscuro ? const Color(0xFF334155) : mentaBorde,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'INGENIERÍA DE SOFTWARE · SCRUM',
                      style: TextStyle(
                        fontSize: 11,
                        letterSpacing: 1.2,
                        fontWeight: FontWeight.w800,
                        color: verde,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text.rich(
                      const TextSpan(
                        children: [
                          TextSpan(text: 'Área '),
                          TextSpan(
                            text: 'Técnica',
                            style: TextStyle(color: verde),
                          ),
                        ],
                      ),
                      style: t.textTheme.titleLarge?.copyWith(
                        fontSize: 30,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Análisis táctico y telemetría de fútbol mediante visión por computadora.',
                      style: t.textTheme.bodyMedium?.copyWith(
                        color: t.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 7,
                      ),
                      decoration: BoxDecoration(
                        color: fondoEstado,
                        border: Border.all(
                          color: _ok ? mentaBorde : colorEstado,
                        ),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: colorEstado,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              _estado,
                              style: TextStyle(
                                fontSize: 13.5,
                                fontWeight: FontWeight.w700,
                                color: colorEstado,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'MÓDULOS DEL SISTEMA',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.9,
                    color: t.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              for (final p in modulos) ...[
                Card(
                  margin: EdgeInsets.zero,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: () => context.go('/${p.ruta}'),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 42,
                            height: 42,
                            decoration: BoxDecoration(
                              color: esOscuro
                                  ? verdeClaro.withValues(alpha: 0.14)
                                  : mentaSuave,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: esOscuro
                                    ? verdeClaro.withValues(alpha: 0.35)
                                    : mentaBorde,
                              ),
                            ),
                            child: Icon(p.icono, color: verde, size: 22),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        p.nombre,
                                        style: t.textTheme.titleMedium
                                            ?.copyWith(fontSize: 17),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 7,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: esOscuro
                                            ? verdeClaro.withValues(alpha: 0.14)
                                            : mentaSuave,
                                        borderRadius: BorderRadius.circular(6),
                                        border: Border.all(
                                          color: esOscuro
                                              ? verdeClaro.withValues(
                                                  alpha: 0.35,
                                                )
                                              : mentaBorde,
                                        ),
                                      ),
                                      child: Text(
                                        p.id,
                                        style: const TextStyle(
                                          fontSize: 11.5,
                                          fontFamily: 'monospace',
                                          fontWeight: FontWeight.w800,
                                          color: verde,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  p.descripcion,
                                  style: TextStyle(
                                    fontSize: 14,
                                    color: t.colorScheme.onSurfaceVariant,
                                    height: 1.35,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  p.cus,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontFamily: 'monospace',
                                    fontWeight: FontWeight.w600,
                                    color: t.colorScheme.outline,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Padding(
                            padding: const EdgeInsets.only(top: 10),
                            child: Icon(
                              Icons.chevron_right_rounded,
                              color: t.colorScheme.outline,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
