/// Pantalla de inicio: los seis paquetes y el estado de la conexión.
///
/// La comprobación de salud es el «walking skeleton» del Sprint 1: si esto
/// responde, la app y el backend están hablándose de verdad.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../shared/api/cliente.dart';
import 'tema.dart';

class Paquete {
  const Paquete(this.id, this.ruta, this.nombre, this.cus);
  final String id, ruta, nombre, cus;
}

const paquetes = [
  Paquete('P1', 'seguridad', 'Seguridad y Administración', 'CU-01 … CU-08'),
  Paquete('P2', 'deportivo', 'Gestión Deportiva', 'CU-09 … CU-17'),
  Paquete('P3', 'vision', 'Visión por Computadora', 'CU-18 … CU-29'),
  Paquete('P4', 'partido', 'Operación del Partido', 'CU-30 … CU-39'),
  Paquete('P5', 'analisis', 'Análisis Táctico', 'CU-40 … CU-48'),
  Paquete('P6', 'asistencia', 'Asistencia y Reportes', 'CU-49 … CU-58'),
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
        _estado = 'API conectada · v${r['version']}';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = true;
        _estado = 'Sin conexión — ¿está corriendo el backend?';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final colorEstado = _ok ? verde : (_error ? rojo : t.colorScheme.outline);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _verificarSalud,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 28, 20, 32),
            children: [
              Text('INGENIERÍA DE SOFTWARE · SCRUM',
                  style: t.textTheme.bodySmall?.copyWith(
                      fontSize: 11,
                      letterSpacing: 1.6,
                      fontWeight: FontWeight.w700,
                      color: t.colorScheme.outline)),
              const SizedBox(height: 10),
              Text.rich(
                TextSpan(children: [
                  const TextSpan(text: 'Área '),
                  TextSpan(text: 'Técnica', style: TextStyle(color: verde)),
                ]),
                style: t.textTheme.titleLarge?.copyWith(fontSize: 34),
              ),
              const SizedBox(height: 6),
              Text('Análisis táctico de fútbol por visión computacional',
                  style: t.textTheme.bodyMedium
                      ?.copyWith(color: t.colorScheme.onSurfaceVariant)),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                decoration: BoxDecoration(
                  border: Border.all(color: colorEstado),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(_estado,
                    style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: colorEstado)),
              ),
              const SizedBox(height: 26),
              for (final p in paquetes) ...[
                Card(
                  child: ListTile(
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                    title: Text(p.nombre, style: t.textTheme.titleMedium),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text('${p.id} · ${p.cus}',
                          style: TextStyle(
                              fontSize: 14, color: t.colorScheme.outline)),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.go('/${p.ruta}'),
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
